# SAM/src/sam/balanceador/service/cooling_manager.py

import logging
import time
from threading import RLock
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class CoolingManager:
    """
    Gestor de períodos de enfriamiento para evitar thrashing en las asignaciones/desasignaciones.

    Esta clase mantiene un registro de las operaciones recientes de asignación/desasignación
    y previene cambios frecuentes en la misma dirección para un mismo robot.
    """

    def __init__(self, cooling_period_seconds: int = 300):
        """
        Inicializa el gestor de enfriamiento.

        Args:
            cooling_period_seconds: Período de enfriamiento en segundos (default: 5 minutos)
        """
        self.cooling_period = cooling_period_seconds
        self._lock = RLock()

        # Mapas para registrar las últimas operaciones
        # {robot_id: (timestamp, operación, cantidad)}
        self._ultima_ampliacion: Dict[int, Tuple[float, str, int]] = {}
        self._ultima_reduccion: Dict[int, Tuple[float, str, int]] = {}

        # Umbrales para considerar un cambio significativo
        self.umbral_de_ampliacion = 0.3  # 30% más tickets justifica escalar
        self.umbral_de_reduccion = 0.4  # 40% menos tickets justifica desescalar

    def puede_ampliar(self, robot_id: int) -> Tuple[bool, str]:
        with self._lock:
            if robot_id in self._ultima_ampliacion:
                last_time, _, _ = self._ultima_ampliacion[robot_id]
                time_elapsed = time.time() - last_time
                if time_elapsed < self.cooling_period:
                    return False, f"En período de enfriamiento tras asignación reciente ({int(time_elapsed)}s < {self.cooling_period}s)"
            return True, "Fuera de período de enfriamiento"

    def puede_reducir(self, robot_id: int, tickets_actuales: int) -> Tuple[bool, str]:
        """
        Verifica si se puede desasignar un equipo a un robot.
        """
        with self._lock:
            if robot_id in self._ultima_reduccion:
                last_time, _, tickets_anteriores = self._ultima_reduccion[robot_id]
                time_elapsed = time.time() - last_time

                if time_elapsed < self.cooling_period:
                    # Comprobar si la caída de tickets es drástica
                    if tickets_anteriores > 0:
                        cambio_porcentual = (tickets_anteriores - tickets_actuales) / tickets_anteriores
                        if cambio_porcentual >= self.umbral_de_reduccion:
                            return True, f"Enfriamiento ignorado por caída drástica de tickets ({cambio_porcentual:.0%})"

                    return False, f"En período de enfriamiento tras desasignación reciente ({int(time_elapsed)}s < {self.cooling_period}s)"

            return True, "Fuera de período de enfriamiento"

    def registrar_ampliacion(self, robot_id: int, tickets: int, equipos_asignados: int) -> None:
        """
        Registra una operación de escalado hacia arriba.

        Args: robot_id: ID del robot
            tickets: Cantidad de tickets en el momento de la asignación
            equipos_asignados: Cantidad de equipos asignados
        """
        with self._lock:
            self._ultima_ampliacion[robot_id] = (time.time(), "ASIGNAR", tickets)
            logger.debug(f"Registrada operación de ampliación para RobotId {robot_id}: {tickets} tickets, {equipos_asignados} equipos")

    def registrar_reduccion(self, robot_id: int, tickets: int, equipos_desasignados: int) -> None:
        """
        Registra una operación de escalado hacia abajo.

        Args: robot_id: ID del robot
            tickets: Cantidad de tickets en el momento de la desasignación
            equipos_desasignados: Cantidad de equipos desasignados
        """
        with self._lock:
            self._ultima_reduccion[robot_id] = (time.time(), "DESASIGNAR", tickets)
            logger.debug(f"Registrada operación de reducción para RobotId {robot_id}: {tickets} tickets, {equipos_desasignados} equipos")
