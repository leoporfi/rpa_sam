# src/lanzador/service/desplegador.py
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

import httpx
import pytz

from src.common.clients.aa_client import AutomationAnywhereClient
from src.common.clients.api_gateway_client import ApiGatewayClient
from src.common.database.sql_client import DatabaseConnector

logger = logging.getLogger(__name__)


class Desplegador:
    """
    Componente 'cerebro' responsable de la lógica de despliegue de robots.
    Recibe sus dependencias y configuración, y su única misión es ejecutar
    el ciclo de lanzamiento cuando se le indica.
    """

    def __init__(
        self,
        db_connector: DatabaseConnector,
        aa_client: AutomationAnywhereClient,
        api_gateway_client: ApiGatewayClient,
        lanzador_config: Dict[str, Any],
        callback_token: str,
    ):
        """
        Inicializa el Desplegador con sus dependencias.

        Args:
            db_connector: Conector a la base de datos de SAM.
            aa_client: Cliente para la API de Automation Anywhere.
            api_gateway_client: Cliente para el API Gateway.
            lanzador_config: Diccionario con la configuración específica del lanzador.
            callback_token: Token estático para la autenticación del callback.
        """
        self._db_connector = db_connector
        self._aa_client = aa_client
        self._api_gateway_client = api_gateway_client
        self._lanzador_cfg = lanzador_config
        self._static_callback_api_key = callback_token

    async def desplegar_robots_pendientes(self):
        """
        Orquesta un ciclo completo de despliegue de robots.
        """
        if self._esta_en_pausa():
            logger.info("El servicio se encuentra en la ventana de pausa operacional. No se lanzarán robots.")
            return

        logger.info("Buscando robots para ejecutar...")
        robots_a_ejecutar = self._db_connector.obtener_robots_ejecutables()

        if not robots_a_ejecutar:
            logger.info("No hay robots para ejecutar en este ciclo.")
            return

        bot_input = {"in_NumRepeticion": {"type": "NUMBER", "number": self._lanzador_cfg.get("repeticiones", 1)}}
        concurrency_limit = self._lanzador_cfg.get("max_workers_lanzador", 10)
        auth_headers = await self._preparar_cabeceras_callback()

        logger.info(f"{len(robots_a_ejecutar)} robots encontrados. Desplegando en paralelo (límite: {concurrency_limit})...")

        tasks = [asyncio.create_task(self._desplegar_y_registrar_robot(robot_info, bot_input, auth_headers)) for robot_info in robots_a_ejecutar]

        successful_deploys = 0
        failed_deploys = 0
        for i in range(0, len(tasks), concurrency_limit):
            batch = tasks[i : i + concurrency_limit]
            results = await asyncio.gather(*batch)
            successful_deploys += sum(1 for _, success in results if success)
            failed_deploys += sum(1 for _, success in results if not success)

        logger.info(f"Ciclo de despliegue completado. Exitosos: {successful_deploys}, Fallidos: {failed_deploys}.")

    async def _desplegar_y_registrar_robot(self, robot_info: Dict, bot_input: Dict, auth_headers: Dict) -> tuple[int, bool]:
        """
        Encapsula la lógica para desplegar un robot y registrar su ejecución,
        incluyendo reintentos para errores específicos.
        """
        robot_id = robot_info["RobotId"]
        max_attempts = 1 + self._lanzador_cfg.get("max_reintentos_deploy", 1)
        delay_seconds = self._lanzador_cfg.get("delay_reintento_deploy_seg", 15)

        for attempt in range(1, max_attempts + 1):
            try:
                deployment_result = await self._aa_client.desplegar_bot_v4(
                    file_id=robot_id, user_ids=[robot_info["UserId"]], bot_input=bot_input, callback_auth_headers=auth_headers
                )

                if deployment_result and "deploymentId" in deployment_result:
                    self._db_connector.insertar_registro_ejecucion(
                        id_despliegue=deployment_result["deploymentId"],
                        db_robot_id=robot_id,
                        db_equipo_id=robot_info.get("EquipoId"),
                        a360_user_id=robot_info["UserId"],
                        marca_tiempo_programada=robot_info.get("Hora"),
                        estado="DEPLOYED",
                    )
                    logger.info(f"Robot {robot_id} desplegado con ID: {deployment_result['deploymentId']} (Intento {attempt}/{max_attempts})")
                    return robot_id, True
                else:
                    error_msg = deployment_result.get("error", "Fallo al obtener deploymentId")
                    logger.error(f"Error de API al desplegar robot {robot_id}: {error_msg}")
                    return robot_id, False

            except httpx.HTTPStatusError as e:
                is_device_error = e.response.status_code == 400 and "are not active" in e.response.text

                if is_device_error and attempt < max_attempts:
                    logger.warning(
                        f"Fallo de despliegue para robot {robot_id} (Intento {attempt}/{max_attempts}): El dispositivo no está activo. Reintentando en {delay_seconds}s..."
                    )
                    await asyncio.sleep(delay_seconds)
                    continue
                else:
                    logger.error(
                        f"Fallo de despliegue definitivo para robot {robot_id} (Intento {attempt}/{max_attempts}): {e.response.status_code} - {e.response.text}"
                    )
                    return robot_id, False

            except Exception as e:
                logger.error(f"Excepción inesperada al desplegar robot {robot_id} (Intento {attempt}/{max_attempts}): {e}", exc_info=True)
                return robot_id, False

        logger.error(f"El despliegue del robot {robot_id} falló después de {max_attempts} intentos.")
        return robot_id, False

    async def _preparar_cabeceras_callback(self) -> Dict[str, str]:
        """Obtiene y combina las cabeceras de autorización para el callback."""
        combined_headers = {}
        try:
            logger.info("Obteniendo token dinámico del API Gateway...")
            gateway_headers = await self._api_gateway_client.get_auth_header()
            if gateway_headers:
                combined_headers.update(gateway_headers)
            else:
                logger.warning("No se pudo obtener token del API Gateway.")
        except Exception as token_error:
            logger.error(f"Excepción al obtener token del API Gateway: {token_error}.", exc_info=True)

        if self._static_callback_api_key:
            logger.info("Añadiendo ApiKey estática (X-Authorization) a las cabeceras del callback.")
            combined_headers["X-Authorization"] = self._static_callback_api_key
        else:
            logger.warning("La ApiKey estática (CALLBACK_TOKEN) no está configurada.")

        return combined_headers

    def _esta_en_pausa(self) -> bool:
        """Verifica si la hora actual está dentro de la ventana de pausa operacional."""
        start_str, end_str = self._lanzador_cfg.get("pausa_lanzamiento", (None, None))
        if not start_str or not end_str:
            return False
        try:
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            tz = pytz.timezone("America/Argentina/Buenos_Aires")
            current_time = datetime.now(tz).time()

            if start_time > end_time:
                return current_time >= start_time or current_time < end_time
            else:
                return start_time <= current_time < end_time
        except (ValueError, pytz.exceptions.UnknownTimeZoneError) as e:
            logger.error(f"Error al procesar la ventana de pausa. Verifique el formato HH:MM. Error: {e}")
            return False
