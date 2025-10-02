# SAM/src/balanceador/service/proveedores.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.balanceador.clients.clouders_client import CloudersClient
from src.common.database.sql_client import DatabaseConnector

logger = logging.getLogger(__name__)


class CargaProveedorBase(ABC):
    """Interfaz para todos los proveedores de carga."""

    @abstractmethod
    def obtener_carga(self) -> Dict[int, int]:
        raise NotImplementedError

    @staticmethod
    def get_nombre() -> str:
        raise NotImplementedError


class CloudersProveedor(CargaProveedorBase):
    """Proveedor de carga que obtiene datos desde la API de Clouders."""

    def __init__(self, db_sam: DatabaseConnector, mapa_robots: Dict[str, str], **kwargs):
        self.clouders_client = CloudersClient()
        self.mapa_robots_config = mapa_robots
        self.mapa_completo_robots_sam = self._obtener_mapa_completo_robots(db_sam)

    @staticmethod
    def get_nombre() -> str:
        return "clouders"

    def _obtener_mapa_completo_robots(self, db_sam: DatabaseConnector) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene un mapa de TODOS los robots en SAM con su estado.
        Esto permite un diagnóstico y logging mucho más precisos.
        """
        query = "SELECT RobotId, Robot, Activo, EsOnline FROM dbo.Robots;"
        try:
            robots_db = db_sam.ejecutar_consulta(query, es_select=True) or []
            # Se usa strip() para limpiar posibles espacios en blanco en los nombres
            return {r["Robot"].strip(): {"id": r["RobotId"], "activo": r["Activo"], "es_online": r["EsOnline"]} for r in robots_db}
        except Exception as e:
            logger.error(f"Error fatal al construir el mapa de robots de SAM: {e}", exc_info=True)
            return {}

    def obtener_carga(self) -> Dict[int, int]:
        """
        Obtiene la carga desde Clouders, la mapea y la valida contra el estado en SAM.
        """
        logger.info(f"Proveedor '{self.get_nombre()}': Obteniendo carga de trabajo...")
        carga_cruda = self.clouders_client.obtener_tickets_pendientes()
        carga_final = {}

        for item in carga_cruda:
            nombre_original = item.get("robot_name", "").strip()
            if not nombre_original:
                continue

            cantidad_tickets = item.get("CantidadTickets", 0)
            nombre_mapeado = self.mapa_robots_config.get(nombre_original, nombre_original).strip()

            robot_info = self.mapa_completo_robots_sam.get(nombre_mapeado)

            # --- LÓGICA DE VALIDACIÓN EXPLÍCITA ---
            if not robot_info:
                logger.warning(
                    f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (mapeado desde '{nombre_original}') "
                    f"NO EXISTE en la tabla dbo.Robots y será ignorado."
                )
                continue

            if not robot_info.get("activo"):
                logger.warning(
                    f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (RobotId: {robot_info['id']}) "
                    f"existe pero está INACTIVO (Activo=0) y será ignorado."
                )
                continue

            if not robot_info.get("es_online"):
                logger.warning(
                    f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (RobotId: {robot_info['id']}) "
                    f"existe pero NO ES ONLINE (EsOnline=0) y será ignorado."
                )
                continue

            # Si todas las validaciones pasan, el robot es un candidato válido.
            robot_id = robot_info["id"]
            carga_final[robot_id] = carga_final.get(robot_id, 0) + cantidad_tickets

        return carga_final


class Rpa360Proveedor(CargaProveedorBase):
    """
    Proveedor de carga que obtiene datos desde una tabla en la BD de RPA360.
    """

    def __init__(self, db_sam: DatabaseConnector, db_rpa360: DatabaseConnector, mapa_robots: Dict[str, str], **kwargs):
        self.db_rpa360 = db_rpa360
        self.mapa_completo_robots_sam = self._obtener_mapa_completo_robots(db_sam)
        self.mapa_robots_config = mapa_robots

    @staticmethod
    def get_nombre() -> str:
        return "rpa360"

    # Reutiliza el mismo método que Clouders para obtener el mapa completo.
    _obtener_mapa_completo_robots = CloudersProveedor._obtener_mapa_completo_robots

    def obtener_carga(self) -> Dict[int, int]:
        logger.info(f"Proveedor '{self.get_nombre()}': Obteniendo carga de trabajo ejecutando SP...")
        # Llama al Stored Procedure en lugar de una consulta directa.
        query = "EXEC dbo.usp_obtener_tickets_pendientes_por_robot;"
        carga_final = {}
        try:
            resultados_db = self.db_rpa360.ejecutar_consulta(query, es_select=True) or []

            for item in resultados_db:
                nombre_original = item.get("Robot", "").strip()
                if not nombre_original:
                    continue

                cantidad_tickets = item.get("CantidadTickets", 0)
                nombre_mapeado = self.mapa_robots_config.get(nombre_original, nombre_original).strip()
                robot_info = self.mapa_completo_robots_sam.get(nombre_mapeado)

                # --- LÓGICA DE VALIDACIÓN EXPLÍCITA (replicada de Clouders) ---
                if not robot_info:
                    logger.warning(
                        f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (mapeado desde '{nombre_original}') "
                        f"NO EXISTE en la tabla dbo.Robots y será ignorado."
                    )
                    continue

                if not robot_info.get("activo"):
                    logger.warning(
                        f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (RobotId: {robot_info['id']}) "
                        f"existe pero está INACTIVO (Activo=0) y será ignorado."
                    )
                    continue

                if not robot_info.get("es_online"):
                    logger.warning(
                        f"Proveedor '{self.get_nombre()}': Robot '{nombre_mapeado}' (RobotId: {robot_info['id']}) "
                        f"existe pero NO ES ONLINE (EsOnline=0) y será ignorado."
                    )
                    continue

                robot_id = robot_info["id"]
                carga_final[robot_id] = carga_final.get(robot_id, 0) + cantidad_tickets

            return carga_final

        except Exception as e:
            logger.error(f"Proveedor '{self.get_nombre()}': Error al ejecutar la consulta de carga: {e}", exc_info=True)
            return {}


class ProveedorCargaFactory:
    _proveedores_registrados = {
        "clouders": CloudersProveedor,
        "rpa360": Rpa360Proveedor,
    }

    @staticmethod
    def crear_proveedores(config_proveedores: List[str], **kwargs) -> List[CargaProveedorBase]:
        proveedores_activos = []
        for nombre in config_proveedores:
            clase_proveedor = ProveedorCargaFactory._proveedores_registrados.get(nombre.strip())
            if clase_proveedor:
                try:
                    instancia = clase_proveedor(**kwargs)
                    proveedores_activos.append(instancia)
                except Exception as e:
                    logger.error(f"No se pudo inicializar el proveedor '{nombre}'. Error: {e}", exc_info=True)
            else:
                logger.warning(f"Proveedor '{nombre}' no está registrado. Será ignorado.")
        return proveedores_activos
