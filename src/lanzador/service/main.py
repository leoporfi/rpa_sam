# src/lanzador/service/main.py
import asyncio
import logging
from typing import List

from src.common.utils.mail_client import EmailAlertClient
from src.lanzador.service.conciliador import Conciliador
from src.lanzador.service.desplegador import Desplegador
from src.lanzador.service.sincronizador import Sincronizador

logger = logging.getLogger(__name__)


class LanzadorService:
    """
    Clase Orquestadora del servicio Lanzador.
    Su responsabilidad es gestionar el ciclo de vida del servicio y coordinar
    a los componentes de lógica ('cerebros'), pero no contiene la lógica de
    negocio en sí misma.
    """

    def __init__(
        self,
        sincronizador: Sincronizador,
        desplegador: Desplegador,
        conciliador: Conciliador,
        notificador: EmailAlertClient,
        lanzador_config: dict,
        sync_enabled: bool,
    ):
        """
        Inicializa el Orquestador con sus componentes de lógica ya creados (Inyección de Dependencias).
        """
        logger.info("Inicializando el orquestador del LanzadorService...")
        self._sincronizador = sincronizador
        self._desplegador = desplegador
        self._conciliador = conciliador
        self._notificador = notificador
        self._lanzador_cfg = lanzador_config
        self._sync_enabled = sync_enabled

        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

        self._validar_configuracion_critica()
        logger.info("Orquestador del LanzadorService inicializado correctamente.")

    def _validar_configuracion_critica(self):
        """Valida que la configuración esencial para el servicio esté presente."""
        logger.info("Validando configuración crítica para el servicio...")
        claves_criticas = [
            "intervalo_lanzamiento",
            "intervalo_sincronizacion",
            "intervalo_conciliacion",
            "conciliador_max_intentos_fallidos",
        ]
        faltantes = [clave for clave in claves_criticas if clave not in self._lanzador_cfg]
        if faltantes:
            raise ValueError(f"Configuración crítica faltante en LanzadorService: {', '.join(faltantes)}")
        logger.info("Validación de configuración completada.")

    async def run(self):
        """Crea y gestiona las tareas asíncronas de los ciclos del servicio."""
        logger.info("Creando tareas de ciclo del servicio...")

        if self._sync_enabled:
            self._tasks.append(asyncio.create_task(self._run_sync_cycle(self._lanzador_cfg["intervalo_sincronizacion"])))
        else:
            logger.warning("El ciclo de sincronización está DESHABILITADO por configuración.")

        self._tasks.append(asyncio.create_task(self._run_launcher_cycle(self._lanzador_cfg["intervalo_lanzamiento"])))
        self._tasks.append(asyncio.create_task(self._run_conciliador_cycle(self._lanzador_cfg["intervalo_conciliacion"])))

        # Espera a que todas las tareas finalicen
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def stop(self):
        """Activa el evento de cierre para detener los ciclos de forma ordenada."""
        logger.info("Iniciando la detención ordenada de los ciclos del servicio...")
        self._shutdown_event.set()

    async def _run_generic_cycle(self, logic_component, method_name: str, interval: int, cycle_name: str):
        """Plantilla genérica para ejecutar un ciclo de lógica."""
        while not self._shutdown_event.is_set():
            try:
                logger.info(f"Iniciando ciclo de {cycle_name}...")
                await getattr(logic_component, method_name)()
                logger.info(f"Ciclo de {cycle_name} completado.")
            except Exception as e:
                logger.critical(f"Error fatal en el ciclo de {cycle_name}: {e}", exc_info=True)
                self._notificador.send_alert(
                    subject=f"Error Crítico en Ciclo de {cycle_name}",
                    message=f"Se ha producido un error irrecuperable en el ciclo de {cycle_name}.\n\nError: {e}",
                )
            try:
                # Espera el intervalo o hasta que se active el evento de cierre
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass  # Es el comportamiento esperado, continuar al siguiente ciclo

    async def _run_sync_cycle(self, interval: int):
        await self._run_generic_cycle(self._sincronizador, "sincronizar_entidades", interval, "Sincronización")

    async def _run_launcher_cycle(self, interval: int):
        await self._run_generic_cycle(self._desplegador, "desplegar_robots_pendientes", interval, "Lanzamiento")

    async def _run_conciliador_cycle(self, interval: int):
        await self._run_generic_cycle(self._conciliador, "conciliar_ejecuciones", interval, "Conciliación")
