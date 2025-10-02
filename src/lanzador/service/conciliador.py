# src/lanzador/service/conciliador.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

from src.common.clients.aa_client import AutomationAnywhereClient
from src.common.database.sql_client import DatabaseConnector

logger = logging.getLogger(__name__)


class Conciliador:
    """
    Componente 'cerebro' responsable de la lógica de conciliación de estados
    de ejecuciones entre SAM y Automation Anywhere.
    """

    def __init__(self, db_connector: DatabaseConnector, aa_client: AutomationAnywhereClient, max_intentos_fallidos: int):
        """
        Inicializa el Conciliador con sus dependencias.

        Args:
            db_connector: Conector a la base de datos de SAM.
            aa_client: Cliente para la API de Automation Anywhere.
            max_intentos_fallidos: Umbral para marcar una ejecución como UNKNOWN.
        """
        self._db_connector = db_connector
        self._aa_client = aa_client
        self._max_intentos_fallidos = max_intentos_fallidos
        self.ESTADOS_VALIDOS_API = {
            "COMPLETED",
            "DEPLOYED",
            "DEPLOY_FAILED",
            "QUEUED",
            "PENDING_EXECUTION",
            "UPDATE",
            "RUNNING",
            "RUN_FAILED",
            "RUN_PAUSED",
            "RUN_ABORTED",
            "RUN_TIMED_OUT",
            "UNKNOWN",
        }

    async def conciliar_ejecuciones(self):
        """
        Orquesta un ciclo completo de conciliación de ejecuciones.
        """
        logger.info("Iniciando conciliación de ejecuciones en curso...")
        try:
            ejecuciones_en_curso = self._db_connector.obtener_ejecuciones_en_curso()
            if not ejecuciones_en_curso:
                logger.info("No hay ejecuciones activas para conciliar.")
                return

            mapa_deploy_a_ejecucion = {
                imp["DeploymentId"]: imp["EjecucionId"] for imp in ejecuciones_en_curso if imp.get("DeploymentId") and imp.get("EjecucionId")
            }
            deployment_ids = list(mapa_deploy_a_ejecucion.keys())

            if not deployment_ids:
                logger.info("No se encontraron DeploymentIds válidos en las ejecuciones activas.")
                return

            logger.info(f"Consultando estado de {len(deployment_ids)} deployment(s) en A360...")
            detalles_api = await self._aa_client.obtener_detalles_por_deployment_ids(deployment_ids)

            self._actualizar_estados_encontrados(detalles_api, mapa_deploy_a_ejecucion)
            self._gestionar_deployments_perdidos(deployment_ids, detalles_api, mapa_deploy_a_ejecucion)

        except Exception as e:
            logger.error(f"Error grave durante el ciclo de conciliación: {e}", exc_info=True)

    def _actualizar_estados_encontrados(self, detalles_api: list, mapa_deploy_a_ejecucion: dict):
        """Actualiza la BD con los estados de los deployments encontrados en la API."""
        if not detalles_api:
            return

        updates_params = []
        for detalle in detalles_api:
            dep_id = detalle.get("deploymentId")
            status_api = detalle.get("status")
            end_date_str = detalle.get("endDateTime")
            ejecucion_id = mapa_deploy_a_ejecucion.get(dep_id)

            if not all([dep_id, status_api, ejecucion_id]):
                continue

            final_status_db = "RUNNING" if status_api == "UPDATE" else status_api
            if final_status_db not in self.ESTADOS_VALIDOS_API:
                continue

            fecha_fin_dt = self._convertir_utc_a_local_sam(end_date_str)
            updates_params.append((final_status_db, fecha_fin_dt, ejecucion_id))

        if updates_params:
            query = """
                UPDATE dbo.Ejecuciones
                SET Estado = ?, FechaFin = ?, FechaActualizacion = GETDATE(), IntentosConciliadorFallidos = 0
                WHERE EjecucionId = ? AND CallbackInfo IS NULL;
            """
            affected_count = self._db_connector.ejecutar_consulta_multiple(query, updates_params)
            logger.info(f"Se actualizaron {affected_count} registros de ejecuciones desde la API.")

    def _gestionar_deployments_perdidos(self, deployment_ids_en_db: list, detalles_api: list, mapa_deploy_a_ejecucion: dict):
        """Gestiona los deployments que no fueron devueltos por la API de A360."""
        ids_encontrados_api = {item.get("deploymentId") for item in detalles_api}
        ids_perdidos = [dep_id for dep_id in deployment_ids_en_db if dep_id not in ids_encontrados_api]

        if not ids_perdidos:
            return

        ejecucion_ids_perdidos = [mapa_deploy_a_ejecucion[dep_id] for dep_id in ids_perdidos if dep_id in mapa_deploy_a_ejecucion]
        if not ejecucion_ids_perdidos:
            return

        placeholders = ",".join("?" * len(ejecucion_ids_perdidos))
        query_increment = f"UPDATE dbo.Ejecuciones SET IntentosConciliadorFallidos = IntentosConciliadorFallidos + 1, FechaActualizacion = GETDATE() WHERE EjecucionId IN ({placeholders}) AND CallbackInfo IS NULL;"
        self._db_connector.ejecutar_consulta(query_increment, tuple(ejecucion_ids_perdidos), es_select=False)
        logger.info(f"Incrementado contador de intentos para {len(ejecucion_ids_perdidos)} deployment(s) no encontrados en la API.")

        query_unknown = f"UPDATE dbo.Ejecuciones SET Estado = 'UNKNOWN', FechaFin = GETDATE(), FechaActualizacion = GETDATE() WHERE EjecucionId IN ({placeholders}) AND IntentosConciliadorFallidos >= ?;"
        params_unknown = tuple(ejecucion_ids_perdidos) + (self._max_intentos_fallidos,)
        count_unknown = self._db_connector.ejecutar_consulta(query_unknown, params_unknown, es_select=False)

        if count_unknown > 0:
            logger.warning(
                f"Se marcaron {count_unknown} deployment(s) como UNKNOWN tras superar el umbral de {self._max_intentos_fallidos} intentos."
            )

    def _convertir_utc_a_local_sam(self, fecha_utc_str: Optional[str]) -> Optional[datetime]:
        """Convierte una fecha en formato ISO UTC a la zona horaria local de SAM."""
        if not fecha_utc_str or fecha_utc_str.startswith("1970"):
            return None
        try:
            dt_utc = dateutil_parser.isoparse(fecha_utc_str)
            tz_local_sam = pytz.timezone("America/Argentina/Buenos_Aires")
            return dt_utc.astimezone(tz_local_sam)
        except Exception as e:
            logger.error(f"Error al convertir fecha UTC '{fecha_utc_str}': {e}", exc_info=True)
            return None
