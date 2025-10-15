# sam/lanzador/service/sincronizador.py
import logging

from sam.common.a360_client import AutomationAnywhereClient
from sam.common.database import DatabaseConnector
# RFR-29: Se importa el nuevo sincronizador común
from sam.common.sincronizador_comun import SincronizadorComun

logger = logging.getLogger(__name__)


class Sincronizador:
    """
    Componente 'cerebro' del servicio Lanzador. Su única responsabilidad
    es invocar al componente de sincronización común.
    """

    def __init__(self, db_connector: DatabaseConnector, aa_client: AutomationAnywhereClient):
        """
        Inicializa el Sincronizador con sus dependencias.
        """
        # RFR-29: Se instancia el sincronizador común aquí
        self._sincronizador_comun = SincronizadorComun(db_connector=db_connector, aa_client=aa_client)

    async def sincronizar_entidades(self):
        """
        Orquesta un ciclo completo de sincronización de entidades llamando
        a la lógica centralizada.
        """
        logger.info("Iniciando ciclo de sincronización desde el servicio Lanzador...")
        try:
            # RFR-29: Se delega toda la lógica al componente común
            await self._sincronizador_comun.sincronizar_entidades()
        except Exception as e:
            logger.error(f"Error grave durante el ciclo de sincronización del lanzador: {e}", exc_info=True)
            # La gestión de errores y notificaciones se maneja en el orquestador principal
            raise
