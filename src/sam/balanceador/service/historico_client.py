# SAM/src/sam/balanceador/service/historico_client.py

import logging
from typing import Optional

from sam.common.database import DatabaseConnector

logger = logging.getLogger(__name__)


class HistoricoBalanceoClient:
    """Cliente para registrar el histórico de decisiones de balanceo."""

    def __init__(self, db_connector: DatabaseConnector):
        """
        Inicializa el cliente con un conector de base de datos.

        Args: db_connector: Conector a la base de datos SAM
        """
        self.db = db_connector

    # En historico_client.py, dentro de la clase HistoricoBalanceoClient

    def registrar_decision_balanceo(
        self,
        robot_id: int,
        pool_id: Optional[int],
        tickets_pendientes: int,
        equipos_antes: int,
        equipos_despues: int,
        accion: str,
        justificacion: Optional[str] = None,
    ) -> bool:
        """
        Registra una decisión de balanceo en la tabla HistoricoBalanceo.
        """
        try:
            # La query ahora incluye la nueva columna PoolId
            query = """
            INSERT INTO dbo.HistoricoBalanceo 
            (RobotId, PoolId, TicketsPendientes, EquiposAsignadosAntes, EquiposAsignadosDespues, AccionTomada, Justificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """

            # El tuple de parámetros ahora incluye pool_id
            params = (robot_id, pool_id, tickets_pendientes, equipos_antes, equipos_despues, accion, justificacion)

            self.db.ejecutar_consulta(query, params, es_select=False)

            logger.info(f"Registrada decisión de balanceo para RobotId {robot_id} en PoolId {pool_id or 'General'}: {accion}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar decisión de balanceo: {e}", exc_info=True)
            return False

    def obtener_historico_robot(self, robot_id: int, limite: int = 10) -> list:
        """
        Obtiene el histórico de decisiones de balanceo para un robot específico.

        Args: robot_id: ID del robot
            limite: Cantidad máxima de registros a retornar

        Returns: list: Lista de registros históricos
        """
        try:
            query = """
            SELECT TOP (?) HistoricoId, FechaBalanceo, TicketsPendientes, 
                   EquiposAsignadosAntes, EquiposAsignadosDespues, AccionTomada, Justificacion
            FROM dbo.HistoricoBalanceo
            WHERE RobotId = ?
            ORDER BY FechaBalanceo DESC;
            """  # noqa: W291

            return self.db.ejecutar_consulta(query, (limite, robot_id), es_select=True) or []
        except Exception as e:
            logger.error(f"Error al obtener histórico de balanceo: {e}", exc_info=True)
            return []
