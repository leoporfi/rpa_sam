# SAM/src/balanceador/service/main.py

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import schedule

from src.balanceador.service.balanceo import Balanceo
from src.balanceador.service.proveedores import ProveedorCargaFactory
from src.common.database.sql_client import DatabaseConnector
from src.common.utils.config_manager import ConfigManager
from src.common.utils.mail_client import EmailAlertClient

logger = logging.getLogger(__name__)


class BalanceadorService:
    """
    Servicio de Balanceo de SAM, encapsulado en una clase para un control claro
    del ciclo de vida y los recursos.
    """

    def __init__(self):
        """Inicializa el servicio Balanceador."""
        logger.info("Inicializando componentes del BalanceadorService...")

        self.cfg_balanceador_specifics = ConfigManager.get_balanceador_config()
        self._validar_configuracion_critica()

        # --- Dependencias ---
        # Se crean todos los recursos compartidos primero.
        dependencias = self._inicializar_dependencias()
        self.db_sam = dependencias["db_sam"]
        self.db_rpa360 = dependencias["db_rpa360"]

        # --- Inicialización de Componentes ---
        nombres_proveedores = self.cfg_balanceador_specifics.get("proveedores_carga", [])
        self.proveedores_carga = ProveedorCargaFactory.crear_proveedores(nombres_proveedores, **dependencias)

        self.notificador = EmailAlertClient(service_name="Balanceador")
        self.balanceo_logic = Balanceo(self)  # Ahora 'self' está completo
        self._shutdown_event = threading.Event()
        self.scheduler = schedule.Scheduler()

        intervalo = self.cfg_balanceador_specifics["intervalo_ciclo_seg"]
        self.scheduler.every(intervalo).seconds.do(self._execute_cycle)
        logger.info(f"BalanceadorService inicializado. Ciclo configurado cada {intervalo} segundos.")

    def _inicializar_dependencias(self) -> Dict[str, Any]:
        """Crea y devuelve un diccionario con todas las dependencias compartidas."""
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
        db_sam = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
            db_config_prefix="SQL_SAM",
        )

        cfg_sql_rpa360 = ConfigManager.get_sql_server_config("SQL_RPA360")
        db_rpa360 = DatabaseConnector(
            servidor=cfg_sql_rpa360["servidor"],
            base_datos=cfg_sql_rpa360["base_datos"],
            usuario=cfg_sql_rpa360["usuario"],
            contrasena=cfg_sql_rpa360["contrasena"],
            db_config_prefix="SQL_RPA360",
        )

        mapa_robots = ConfigManager.get_mapa_robots()

        return {"db_sam": db_sam, "db_rpa360": db_rpa360, "mapa_robots": mapa_robots}

    def _validar_configuracion_critica(self):
        """Valida que todas las variables de entorno críticas existan."""
        logger.info("Validando configuración crítica para el servicio Balanceador...")
        required_keys = ["intervalo_ciclo_seg", "proveedores_carga", "cooling_period_seg"]
        missing_keys = [key for key in required_keys if key not in self.cfg_balanceador_specifics]
        if missing_keys:
            raise ValueError(f"Configuración crítica del Balanceador faltante: {', '.join(missing_keys).upper()}")
        logger.info("Validación de configuración completada.")

    def run(self):
        """Inicia la ejecución del servicio, con un primer ciclo inmediato."""
        logger.info("El servicio está activo.")
        logger.info("Ejecutando el primer ciclo de balanceo de forma inmediata...")
        self._execute_cycle()
        logger.info("Primer ciclo completado. Iniciando ciclos programados.")

        while not self._shutdown_event.is_set():
            self.scheduler.run_pending()
            self._shutdown_event.wait(1)

    def stop(self):
        """Detiene el servicio de forma ordenada."""
        logger.info("Señal de parada recibida para el Balanceador.")
        self._shutdown_event.set()

    def _execute_cycle(self):
        """Ejecuta un único ciclo completo del algoritmo de balanceo."""
        if self._shutdown_event.is_set():
            return

        logger.info("=" * 20 + " INICIANDO CICLO DE BALANCEO " + "=" * 20)
        try:
            carga_consolidada = self._obtener_carga_de_trabajo_consolidada()
            if self._shutdown_event.is_set():
                return

            pools_activos = self.obtener_pools_activos()
            if self._shutdown_event.is_set():
                return

            self.balanceo_logic.ejecutar_algoritmo_completo(carga_consolidada, pools_activos)

        except Exception as e:
            logger.critical(f"Error inesperado durante el ciclo de balanceo: {e}", exc_info=True)
            self.notificador.send_alert(
                "Error Crítico en Balanceador", f"Excepción no controlada: {e}\n\nTraceback:\n{logging.traceback.format_exc()}"
            )
        finally:
            logger.info("=" * 20 + " CICLO DE BALANCEO COMPLETADO " + "=" * 20)

    def _obtener_carga_de_trabajo_consolidada(self) -> Dict[int, int]:
        """Obtiene la carga de todos los proveedores en paralelo y la consolida."""
        carga_total: Dict[int, int] = {}

        with ThreadPoolExecutor(max_workers=len(self.proveedores_carga) or 1) as executor:
            future_to_provider = {executor.submit(p.obtener_carga): p for p in self.proveedores_carga}

            for future in future_to_provider:
                provider = future_to_provider[future]
                try:
                    carga_proveedor = future.result()
                    logger.info(f"Proveedor '{provider.get_nombre()}' retornó {len(carga_proveedor)} robots con carga.")
                    for robot_id, tickets in carga_proveedor.items():
                        carga_total[robot_id] = carga_total.get(robot_id, 0) + tickets
                except Exception as e:
                    logger.error(f"Error al obtener carga del proveedor '{provider.get_nombre()}': {e}", exc_info=True)

        logger.info(f"Carga consolidada final: {len(carga_total)} robots con demanda.")
        return carga_total

    def obtener_pools_activos(self) -> List[Dict[str, Any]]:
        """Obtiene la lista de pools de balanceo activos desde la BD."""
        logger.info("Obteniendo la lista de pools de balanceo activos...")
        try:
            query = "SELECT PoolId, Nombre FROM dbo.Pools WHERE Activo = 1;"
            pools = self.db_sam.ejecutar_consulta(query, es_select=True) or []
            logger.info(f"Se encontraron {len(pools)} pools activos.")
            return pools
        except Exception as e:
            logger.error(f"Error al obtener pools activos: {e}", exc_info=True)
            return []
