# sam/common/sincronizador_comun.py
import asyncio
import logging
from typing import Dict, List

from .a360_client import AutomationAnywhereClient
from .database import DatabaseConnector

logger = logging.getLogger(__name__)


class SincronizadorComun:
    """
    Componente 'cerebro' centralizado y reutilizable, responsable de la lógica
    de sincronización de entidades entre SAM y Automation Anywhere.
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
        self._valid_licenses = {"ATTENDEDRUNTIME", "RUNTIME"}

    async def sincronizar_entidades(self) -> Dict[str, int]:
        """
        Orquesta un ciclo completo de sincronización. Obtiene los datos de A360,
        los procesa y los persiste en la base de datos de SAM.
        """
        logger.info("Iniciando obtención de entidades desde A360 en paralelo...")
        try:
            robots_task = self._aa_client.obtener_robots()
            devices_task = self._aa_client.obtener_devices()
            users_task = self._aa_client.obtener_usuarios_detallados()

            robots_api, devices_api, users_api = await asyncio.gather(robots_task, devices_task, users_task)
            logger.info(
                f"Datos recibidos de A360: {len(robots_api)} robots, {len(devices_api)} dispositivos, {len(users_api)} usuarios."
            )

            equipos_finales = self._procesar_y_mapear_equipos(devices_api, users_api)

            logger.info("Actualizando base de datos de SAM...")
            self._db_connector.merge_robots(robots_api)
            self._db_connector.merge_equipos(equipos_finales)

            logger.info(
                f"Sincronización completada. {len(robots_api)} robots y {len(equipos_finales)} equipos procesados."
            )
            return {"robots_sincronizados": len(robots_api), "equipos_sincronizados": len(equipos_finales)}

        except Exception as e:
            logger.error(f"Error grave durante el ciclo de sincronización centralizado: {e}", exc_info=True)
            raise

    def _procesar_y_mapear_equipos(self, devices_list: List[Dict], users_list: List[Dict]) -> List[Dict]:
        """
        Toma los datos en bruto de las APIs y los transforma al formato que
        el Stored Procedure MergeEquipos espera.
        """
        if not devices_list:
            logger.warning("La lista de dispositivos de la API está vacía.")
            return []

        # users_by_id = {user["id"]: user for user in users_list if isinstance(user, dict) and "id" in user}
        # 1. Filtrar usuarios que tengan al menos una de las licencias válidas.
        users_by_id = {
            user["id"]: user
            for user in users_list
            if isinstance(user, dict)
            and "id" in user
            and any(lic in self._valid_licenses for lic in user.get("licenseFeatures", []))
        }
        logger.info(f"Se filtraron {len(users_by_id)} usuarios (de {len(users_list)}) con licencias válidas.")

        equipos_procesados = []
        for device in devices_list:
            default_users = device.get("defaultUsers", [])
            valid_user_info = None

            # 1. Iterar sobre la lista de usuarios del dispositivo.
            if isinstance(default_users, list):
                for user_ref in default_users:
                    user_id = user_ref.get("id")
                    # 2. Comprobar si este usuario está en nuestro diccionario de usuarios válidos.
                    if user_id in users_by_id:
                        # 3. Si se encuentra, guardamos su información y rompemos el bucle.
                        valid_user_info = users_by_id[user_id]
                        break  # Nos quedamos con el primero que encontramos.

            if valid_user_info:
                equipo_mapeado = {
                    "EquipoId": device.get("id"),
                    "Equipo": device.get("hostName"),
                    "UserId": valid_user_info.get("id"),
                    "UserName": valid_user_info.get("username"),
                    "Licencia": ", ".join(valid_user_info.get("licenseFeatures", [])),
                    "Activo_SAM": device.get("status") == "CONNECTED",
                }
                equipos_procesados.append(equipo_mapeado)
            else:
                logger.debug(
                    f"Omitiendo dispositivo '{device.get('hostName')}' (ID: {device.get('id')}) porque ninguno de sus usuarios asociados tiene una licencia válida."
                )

        equipos_unicos = {}
        for equipo in equipos_procesados:
            equipo_id = equipo.get("EquipoId")
            if equipo_id:
                if equipo_id not in equipos_unicos:
                    equipos_unicos[equipo_id] = equipo
                else:
                    logger.warning(f"Se encontró un EquipoId duplicado de A360 y se ha omitido: ID = {equipo_id}")

        return list(equipos_unicos.values())
