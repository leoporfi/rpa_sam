# SAM/src/balanceador/service/main.py (Refactorizado con Inyección de Dependencias)

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import schedule

from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.mail_client import EmailAlertClient

from .algoritmo_balanceo import Balanceo
from .proveedores import ProveedorCargaFactory

logger = logging.getLogger(__name__)


class BalanceadorService:
    """
    Servicio de Balanceo de SAM, que recibe sus dependencias para un control claro
    del ciclo de vida y los recursos.
    """

    def __init__(self, db_sam: DatabaseConnector, db_rpa360: DatabaseConnector, notificador: EmailAlertClient):
        """Inicializa el servicio Balanceador con sus dependencias inyectadas."""
        logger.info("Inicializando componentes del BalanceadorService...")

        # --- 1. Recibir y almacenar dependencias ---
        self.db_sam = db_sam
        self.db_rpa360 = db_rpa360
        self.notificador = notificador

        # --- 2. Cargar configuración específica ---
        self.cfg_balanceador_specifics = ConfigManager.get_balanceador_config()
        self._validar_configuracion_critica()

        # --- 3. Inicializar componentes de lógica ---
        nombres_proveedores = self.cfg_balanceador_specifics.get("proveedores_carga", [])
        mapa_robots = ConfigManager.get_mapa_robots()

        # Inyectar las dependencias en la fábrica de proveedores
        self.proveedores_carga = ProveedorCargaFactory.crear_proveedores(
            config_proveedores=nombres_proveedores,
            db_sam=self.db_sam,
            db_rpa360=self.db_rpa360,
            mapa_robots=mapa_robots,
        )

        # Inyectar las dependencias en la clase de algoritmo
        self.algoritmo = Balanceo(
            db_connector=self.db_sam, notificador=self.notificador, config_balanceador=self.cfg_balanceador_specifics
        )

        # --- 4. Configuración del ciclo de vida ---
        self._shutdown_event = threading.Event()
        self._is_shutting_down = False
        self.intervalo_ciclo = self.cfg_balanceador_specifics.get("intervalo_ciclo_seg", 120)
        schedule.every(self.intervalo_ciclo).seconds.do(self.ejecutar_ciclo_balanceo)
        logger.info(f"Servicio configurado para ejecutarse cada {self.intervalo_ciclo} segundos.")

    def _validar_configuracion_critica(self):
        """Valida que la configuración esencial esté presente."""
        if not self.cfg_balanceador_specifics.get("proveedores_carga"):
            raise ValueError("La variable de entorno 'BALANCEADOR_PROVEEDORES_CARGA' es obligatoria.")

    def run(self):
        """Inicia el bucle principal del servicio."""
        logger.info("El servicio Balanceador ha iniciado. Esperando la primera ejecución programada...")
        while not self._shutdown_event.is_set():
            schedule.run_pending()
            time.sleep(1)
        logger.info("Bucle principal del Balanceador finalizado.")

    def stop(self):
        """Detiene el servicio de forma ordenada."""
        if not self._is_shutting_down:
            logger.info("Recibida señal de parada. Finalizando el ciclo actual y deteniendo el servicio...")
            self._is_shutting_down = True
            self._shutdown_event.set()

    def ejecutar_ciclo_balanceo(self):
        """Ejecuta un único ciclo completo del algoritmo de balanceo."""
        if self._is_shutting_down:
            logger.info("Omitiendo ciclo de balanceo debido a una señal de parada.")
            return

        logger.info("*" * 20 + " INICIANDO NUEVO CICLO DE BALANCEO " + "*" * 20)
        try:
            carga_consolidada = self._obtener_carga_de_trabajo_consolidada()
            pools_activos = self.obtener_pools_activos()
            self.algoritmo.ejecutar_algoritmo_completo(carga_consolidada, pools_activos)
        except Exception as e:
            logger.error(f"Error inesperado en el ciclo de balanceo: {e}", exc_info=True)
            self.notificador.send_alert(
                subject="Error Crítico en Ciclo de Balanceo",
                message=f"Se produjo un error no controlado en el ciclo principal.\n\nError: {e}",
            )
        finally:
            logger.info("*" * 22 + " FIN DEL CICLO DE BALANCEO " + "*" * 23 + "\n")

    def _obtener_carga_de_trabajo_consolidada(self) -> Dict[int, int]:
        """Obtiene y consolida la carga de trabajo de todos los proveedores activos."""
        if not self.proveedores_carga:
            logger.warning("No hay proveedores de carga configurados.")
            return {}

        carga_total: Dict[int, int] = {}
        max_workers = max(len(self.proveedores_carga), 1)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
