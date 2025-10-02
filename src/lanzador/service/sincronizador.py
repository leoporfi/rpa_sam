# src/lanzador/service/sincronizador.py
import asyncio
import logging
from typing import Any, Dict

from src.common.clients.aa_client import AutomationAnywhereClient
from src.common.database.sql_client import DatabaseConnector

logger = logging.getLogger(__name__)


class Sincronizador:
    """
    Componente 'cerebro' responsable de la lógica de sincronización de
    entidades (robots y equipos) entre SAM y Automation Anywhere.
    """

    def __init__(self, db_connector: DatabaseConnector, aa_client: AutomationAnywhereClient):
        """
        Inicializa el Sincronizador con sus dependencias.

        Args:
            db_connector: Conector a la base de datos de SAM.
            aa_client: Cliente para la API de Automation Anywhere.
        """
        self._db_connector = db_connector
        self._aa_client = aa_client

    async def sincronizar_entidades(self):
        """
        Orquesta un ciclo completo de sincronización de entidades.
        Obtiene los datos de A360 y los persiste en la base de datos de SAM.
        """
        logger.info("Iniciando obtención de entidades desde A360 en paralelo...")
        try:
            robots_task = self._aa_client.obtener_robots()
            devices_task = self._aa_client.obtener_devices()
            users_task = self._aa_client.obtener_usuarios_detallados()

            robots, devices, users = await asyncio.gather(robots_task, devices_task, users_task)

            logger.info("Datos obtenidos de A360. Procesando y enriqueciendo información de equipos...")
            devices_procesados = self._procesar_y_enriquecer_devices(devices, users)

            logger.info("Actualizando base de datos de SAM...")
            self._db_connector.merge_robots(robots)
            self._db_connector.merge_equipos(devices_procesados)

            logger.info(f"Sincronización completada. {len(robots)} robots y {len(devices_procesados)} equipos procesados.")

        except Exception as e:
            logger.error(f"Error grave durante el ciclo de sincronización: {e}", exc_info=True)

    def _procesar_y_enriquecer_devices(self, devices: list, users: list) -> list:
        """
        Combina la información de usuarios y dispositivos para añadir la licencia
        a cada dispositivo.
        """
        if not devices or not users:
            logger.warning("La lista de dispositivos o usuarios está vacía. No se puede enriquecer la información.")
            return devices

        users_by_id = {user["UserId"]: user for user in users if isinstance(user, dict) and "UserId" in user}
        devices_enriquecidos = []

        for device in devices:
            if isinstance(device, dict):
                user_id = device.get("UserId")
                if user_id in users_by_id:
                    device["Licencia"] = users_by_id[user_id].get("Licencia", "SIN_LICENCIA")
                else:
                    device["Licencia"] = "USUARIO_NO_ENCONTRADO"
                devices_enriquecidos.append(device)

        return devices_enriquecidos
