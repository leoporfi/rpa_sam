# src/sam/common/database.py
# MODIFICADO: Se añade el método `cerrar_conexiones_pool` para el cierre limpio en FastAPI.

import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from datetime import time as time_obj
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pyodbc

from .config_manager import ConfigManager

if TYPE_CHECKING:
    from sam.common.a360_client import AutomationAnywhereClient

logger = logging.getLogger(__name__)


class UpdateStatus(Enum):
    UPDATED = 1
    ALREADY_PROCESSED = 2
    NOT_FOUND = 3
    ERROR = 4


class DatabaseConnector:
    def __init__(
        self, servidor: str, base_datos: str, usuario: str, contrasena: str, db_config_prefix: str = "SQL_SAM"
    ):
        self.db_config_prefix = db_config_prefix
        sql_config = ConfigManager.get_sql_server_config(db_config_prefix)
        self.max_retries = sql_config["max_retries"]
        self.initial_delay = sql_config["initial_delay"]
        self.retryable_sqlstates = set(sql_config["retryable_sqlstates"])

        self.connection_string = (
            f"DRIVER={sql_config['driver']};"
            f"SERVER={servidor};"
            f"DATABASE={base_datos};"
            f"UID={usuario};"
            f"PWD={contrasena};"
            "TrustServerCertificate=yes;"
            f"Timeout={sql_config['timeout']};"
        )
        self._thread_local = threading.local()
        self._pool = []
        self._pool_lock = threading.Lock()

    def _obtener_conexion_del_pool(self):
        with self._pool_lock:
            if not self._pool:
                logger.info(f"Pool de conexiones vacío. Creando nueva conexión para {self.db_config_prefix}...")
                return self.conectar_base_datos()
            return self._pool.pop()

    def _devolver_conexion_al_pool(self, conn):
        with self._pool_lock:
            self._pool.append(conn)

    @contextmanager
    def obtener_cursor(self):
        conn = self._obtener_conexion_del_pool()
        cursor = None
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            logger.error(f"Error de base de datos (SQLSTATE: {sqlstate}): {ex}")
            if conn:
                try:
                    conn.rollback()
                except pyodbc.Error as rb_ex:
                    logger.error(f"Error durante el rollback: {rb_ex}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self._devolver_conexion_al_pool(conn)

    def conectar_base_datos(self) -> pyodbc.Connection:
        try:
            conn = pyodbc.connect(self.connection_string)
            return conn
        except pyodbc.Error as ex:
            logger.critical(f"No se pudo conectar a la base de datos {self.db_config_prefix}. Error: {ex}")
            raise

    def cerrar_conexion_hilo_actual(self):
        if hasattr(self._thread_local, "connection") and self._thread_local.connection:
            try:
                self._thread_local.connection.close()
                logger.info(f"Conexión a BD ({self.db_config_prefix}) cerrada para el hilo actual.")
            except pyodbc.Error as e:
                logger.error(f"Error al cerrar la conexión a la BD: {e}")
            self._thread_local.connection = None

    def cerrar_conexiones_pool(self):
        with self._pool_lock:
            for conn in self._pool:
                try:
                    conn.close()
                except pyodbc.Error as e:
                    logger.error(f"Error al cerrar una conexión del pool: {e}")
            self._pool = []
            logger.info(f"Todas las conexiones en el pool para {self.db_config_prefix} han sido cerradas.")

    def ejecutar_consulta(self, query: str, params: tuple = None, es_select: bool = True) -> Any:
        retries = self.max_retries
        delay = self.initial_delay

        while retries > 0:
            try:
                with self.obtener_cursor() as cursor:
                    cursor.execute(query, params or ())
                    if es_select:
                        columns = [column[0] for column in cursor.description]
                        return [dict(zip(columns, row)) for row in cursor.fetchall()]
                    else:
                        return cursor.rowcount
            except pyodbc.Error as e:
                sqlstate = e.args[0]
                if sqlstate in self.retryable_sqlstates and retries > 1:
                    logger.warning(
                        f"Error reintentable (SQLSTATE: {sqlstate}) detectado. Reintentando en {delay}s... ({self.max_retries - retries + 1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                    retries -= 1
                    delay *= 2
                else:
                    raise
        return None

    # ... (el resto de los métodos de la clase permanecen igual) ...
    def ejecutar_consulta_multiple(self, query: str, params_list: List[tuple]) -> int:
        if not params_list:
            return 0
        total_affected = 0
        try:
            with self.obtener_cursor() as cursor:
                cursor.fast_executemany = True
                cursor.executemany(query, params_list)
                total_affected = cursor.rowcount
            return total_affected
        except pyodbc.Error as e:
            logger.error(f"Error en ejecución múltiple: {e}")
            # Fallback a ejecución individual si fast_executemany falla
            logger.warning("Fallback a ejecución individual de queries...")
            for params in params_list:
                try:
                    total_affected += self.ejecutar_consulta(query, params, es_select=False)
                except pyodbc.Error as inner_e:
                    logger.error(f"Error en query individual (fallback): {inner_e} con params {params}")
            return total_affected

    def obtener_robots_ejecutables(self) -> List[Dict]:
        return self.ejecutar_consulta("{CALL dbo.ObtenerRobotsEjecutables}", es_select=True) or []

    def insertar_registro_ejecucion(
        self, id_despliegue, db_robot_id, db_equipo_id, a360_user_id, marca_tiempo_programada, estado
    ):
        query = """
            INSERT INTO dbo.Ejecuciones (DeploymentId, RobotId, EquipoId, UserId, Hora, Estado)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        params = (id_despliegue, db_robot_id, db_equipo_id, a360_user_id, marca_tiempo_programada, estado)
        self.ejecutar_consulta(query, params, es_select=False)

    def obtener_ejecuciones_en_curso(self) -> List[Dict]:
        return (
            self.ejecutar_consulta(
                "SELECT EjecucionId, DeploymentId FROM dbo.Ejecuciones WHERE Estado NOT IN ('COMPLETED', 'RUN_COMPLETED', 'RUN_FAILED', 'DEPLOY_FAILED', 'RUN_ABORTED', 'UNKNOWN')",
                es_select=True,
            )
            or []
        )

    def actualizar_ejecucion_desde_callback(
        self, deployment_id: str, estado_callback: str, callback_payload_str: str
    ) -> UpdateStatus:
        try:
            with self.obtener_cursor() as cursor:
                # 1. Verificar el estado actual
                cursor.execute("SELECT Estado FROM dbo.Ejecuciones WHERE DeploymentId = ?", (deployment_id,))
                row = cursor.fetchone()
                if not row:
                    return UpdateStatus.NOT_FOUND

                current_status = row[0]
                if current_status in (
                    "COMPLETED",
                    "RUN_COMPLETED",
                    "RUN_FAILED",
                    "DEPLOY_FAILED",
                    "RUN_ABORTED",
                    "UNKNOWN",
                ):
                    return UpdateStatus.ALREADY_PROCESSED

                # 2. Si no es un estado final, actualizar
                query = "UPDATE dbo.Ejecuciones SET Estado = ?, FechaFin = GETDATE(), FechaActualizacion = GETDATE(), CallbackInfo = ? WHERE DeploymentId = ?;"
                params = (estado_callback, callback_payload_str, deployment_id)
                cursor.execute(query, params)
                return UpdateStatus.UPDATED
        except Exception as e:
            logger.error(f"Error en DB al actualizar callback para {deployment_id}: {e}", exc_info=True)
            return UpdateStatus.ERROR

    def merge_robots(self, lista_robots: List[Dict]):
        if not lista_robots:
            return 0
        try:
            datos_para_sp = [
                (r.get("RobotId"), r.get("Robot"), r.get("Descripcion")) for r in lista_robots if r.get("RobotId")
            ]
            if not datos_para_sp:
                return 0
            self.ejecutar_consulta("{CALL dbo.MergeRobots(?)}", (datos_para_sp,), es_select=False)
            return len(datos_para_sp)
        except Exception as e:
            logger.error(f"Error en merge_robots: {e}", exc_info=True)
            return -1

    def merge_equipos(self, lista_equipos_procesados: List[Dict]):
        if not lista_equipos_procesados:
            return 0
        try:
            datos_para_sp = [
                (
                    eq.get("EquipoId"),
                    eq.get("Equipo"),
                    eq.get("UserId"),
                    eq.get("UserName"),
                    eq.get("Licencia"),
                    eq.get("Activo_SAM", True),
                )
                for eq in lista_equipos_procesados
                if eq.get("EquipoId") is not None and eq.get("UserId") is not None
            ]
            if not datos_para_sp:
                return 0
            self.ejecutar_consulta("{CALL dbo.MergeEquipos(?)}", (datos_para_sp,), es_select=False)
            return len(datos_para_sp)
        except Exception as e:
            logger.error(f"Error en merge_equipos: {e}", exc_info=True)
            return -1
