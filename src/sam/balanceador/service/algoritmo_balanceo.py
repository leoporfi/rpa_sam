# SAM/src/balanceador/service/algoritmo_balanceo.py
# MODIFICADO: El constructor ahora sigue el patrón de Inyección de Dependencias.

import logging
import math
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from sam.common.database import DatabaseConnector
from sam.common.mail_client import EmailAlertClient

from .cooling_manager import CoolingManager
from .historico_client import HistoricoBalanceoClient

logger = logging.getLogger(__name__)


class Balanceo:
    """
    Contiene la lógica central y el algoritmo para el balanceo de cargas.
    """

    def __init__(
        self, db_connector: DatabaseConnector, notificador: EmailAlertClient, config_balanceador: Dict[str, Any]
    ):
        """
        Inicializa la clase de lógica de balanceo con sus dependencias inyectadas.
        """
        self.db_sam = db_connector
        self.notificador = notificador
        self.cfg_balanceador_specifics = config_balanceador

        self.historico_client = HistoricoBalanceoClient(self.db_sam)
        cooling_period = self.cfg_balanceador_specifics.get("cooling_period_seg", 300)
        self.cooling_manager = CoolingManager(cooling_period_seconds=cooling_period)
        self.aislamiento_estricto_pool = self.cfg_balanceador_specifics.get("aislamiento_estricto_pool", True)
        self._lock = threading.RLock()
        logger.info(
            f"Modo de aislamiento estricto de pools: {'Activado' if self.aislamiento_estricto_pool else 'Desactivado'}"
        )

    def ejecutar_algoritmo_completo(self, carga_consolidada: Dict[int, int], pools_activos: List[Dict[str, Any]]):
        """
        Orquesta todas las fases del algoritmo de balanceo.
        """
        with self._lock:
            estado_global = self._obtener_estado_inicial_global(carga_consolidada)
            self.ejecutar_limpieza_global(estado_global)

            pool_ids = [p["PoolId"] for p in pools_activos]
            if None not in pool_ids:
                pool_ids.append(None)

            for pool_id in pool_ids:
                self.ejecutar_balanceo_interno_de_pool(pool_id, estado_global)

            self.ejecutar_fase_de_desborde_global(estado_global)

    def _obtener_estado_inicial_global(self, carga_consolidada: Dict[int, int]) -> Dict[str, Any]:
        """
        Recopila toda la información necesaria de la base de datos para tomar decisiones.
        """
        logger.info("Obteniendo estado inicial global del sistema...")

        robots_activos_query = "SELECT RobotId, Robot, EsOnline, MinEquipos, MaxEquipos, PrioridadBalanceo, TicketsPorEquipoAdicional, PoolId FROM dbo.Robots WHERE Activo = 1"
        mapa_config_robots = {
            r["RobotId"]: r for r in self.db_sam.ejecutar_consulta(robots_activos_query, es_select=True) or []
        }

        equipos_validos_query = (
            "SELECT EquipoId, PoolId FROM dbo.Equipos WHERE Activo_SAM = 1 AND PermiteBalanceoDinamico = 1"
        )
        equipos_validos = self.db_sam.ejecutar_consulta(equipos_validos_query, es_select=True) or []
        mapa_equipos_validos_por_pool = {}
        for eq in equipos_validos:
            pool_id = eq.get("PoolId")
            if pool_id not in mapa_equipos_validos_por_pool:
                mapa_equipos_validos_por_pool[pool_id] = set()
            mapa_equipos_validos_por_pool[pool_id].add(eq["EquipoId"])

        asignaciones_query = "SELECT RobotId, EquipoId, EsProgramado, Reservado FROM dbo.Asignaciones"
        asignaciones = self.db_sam.ejecutar_consulta(asignaciones_query, es_select=True) or []

        mapa_asignaciones_dinamicas = {}
        equipos_con_asignacion_fija = set()
        for a in asignaciones:
            robot_id = a.get("RobotId")
            equipo_id = a.get("EquipoId")
            if not robot_id or not equipo_id:
                continue

            if not a.get("EsProgramado") and not a.get("Reservado"):
                if robot_id not in mapa_asignaciones_dinamicas:
                    mapa_asignaciones_dinamicas[robot_id] = []
                mapa_asignaciones_dinamicas[robot_id].append(equipo_id)
            else:
                equipos_con_asignacion_fija.add(equipo_id)

        estado = {
            "mapa_config_robots": mapa_config_robots,
            "mapa_equipos_validos_por_pool": mapa_equipos_validos_por_pool,
            "mapa_asignaciones_dinamicas": mapa_asignaciones_dinamicas,
            "equipos_con_asignacion_fija": equipos_con_asignacion_fija,
            "carga_trabajo_por_robot": carga_consolidada,
        }
        logger.info("Estado inicial global obtenido.")
        return estado

    def ejecutar_limpieza_global(self, estado_global: Dict[str, Any]):
        """
        Libera recursos de robots que ya no son candidatos para el balanceo.
        """
        logger.info("Iniciando ETAPA DE LIMPIZA GLOBAL...")
        robots_a_limpiar = []
        mapa_config = estado_global["mapa_config_robots"]

        for robot_id, equipos_asignados in list(estado_global["mapa_asignaciones_dinamicas"].items()):
            config_robot = mapa_config.get(robot_id)
            tiene_carga = estado_global["carga_trabajo_por_robot"].get(robot_id, 0) > 0

            if not config_robot or not config_robot.get("EsOnline") or not tiene_carga:
                robots_a_limpiar.append(robot_id)

        for robot_id in robots_a_limpiar:
            self._liberar_equipos_de_robot(robot_id, "DESASIGNAR_ROBOT_NO_CANDIDATO", estado_global)

        logger.info("ETAPA DE LIMPIZA GLOBAL completada.")

    def ejecutar_balanceo_interno_de_pool(self, pool_id: Optional[int], estado_global: Dict[str, Any]):
        """
        Ejecuta el balanceo para un pool específico, usando solo sus propios recursos.
        """
        pool_nombre = f"PoolId {pool_id}" if pool_id is not None else "Pool General"
        logger.info(f"Iniciando ETAPA DE BALANCEO INTERNO para {pool_nombre}...")

        robots_del_pool = {
            rid: rcfg
            for rid, rcfg in estado_global["mapa_config_robots"].items()
            if rcfg.get("PoolId") == pool_id and rid in estado_global["carga_trabajo_por_robot"]
        }

        if not robots_del_pool:
            logger.info(f"No hay robots candidatos con carga en {pool_nombre}. Saltando.")
            return

        equipos_actualmente_asignados_en_pool = {
            eq for rid in robots_del_pool for eq in estado_global["mapa_asignaciones_dinamicas"].get(rid, [])
        }
        equipos_libres_del_pool = list(
            estado_global["mapa_equipos_validos_por_pool"].get(pool_id, set())
            - equipos_actualmente_asignados_en_pool
            - estado_global["equipos_con_asignacion_fija"]
        )

        necesidades = {}
        excedentes = {}
        for rid, rcfg in robots_del_pool.items():
            tickets = estado_global["carga_trabajo_por_robot"].get(rid, 0)
            equipos_necesarios = self._calcular_equipos_necesarios_para_robot(rid, tickets, rcfg)
            equipos_actuales = len(estado_global["mapa_asignaciones_dinamicas"].get(rid, []))

            diferencia = equipos_necesarios - equipos_actuales
            if diferencia > 0:
                necesidades[rid] = diferencia
            elif diferencia < 0:
                excedentes[rid] = -diferencia

        robots_por_prioridad = sorted(
            necesidades.keys(), key=lambda r: estado_global["mapa_config_robots"][r].get("PrioridadBalanceo", 100)
        )
        for rid in robots_por_prioridad:
            necesidad = necesidades[rid]
            while necesidad > 0 and equipos_libres_del_pool:
                equipo_a_asignar = equipos_libres_del_pool.pop(0)
                if self._realizar_asignacion_db(rid, equipo_a_asignar, "ASIGNAR_DEMANDA_POOL", estado_global):
                    necesidad -= 1

        for rid, cantidad_a_quitar in excedentes.items():
            equipos_del_robot = estado_global["mapa_asignaciones_dinamicas"].get(rid, [])
            for _ in range(min(cantidad_a_quitar, len(equipos_del_robot))):
                equipo_a_quitar = equipos_del_robot.pop()
                self._realizar_desasignacion_db(rid, equipo_a_quitar, "DESASIGNAR_EXCEDENTE_POOL", estado_global)

        logger.info(f"ETAPA DE BALANCEO INTERNO para {pool_nombre} completada.")

    def ejecutar_fase_de_desborde_global(self, estado_global: Dict[str, Any]):
        """
        Asigna equipos del Pool General a robots con necesidades no cubiertas.
        """
        logger.info("Iniciando ETAPA DE DESBORDE Y DEMANDA ADICIONAL GLOBAL...")
        if self.aislamiento_estricto_pool:
            logger.info("Aislamiento estricto activado, no se realizará desborde.")
            return

        equipos_asignados_globalmente = {
            eq for subl in estado_global["mapa_asignaciones_dinamicas"].values() for eq in subl
        }
        equipos_libres_general = list(
            estado_global["mapa_equipos_validos_por_pool"].get(None, set())
            - equipos_asignados_globalmente
            - estado_global["equipos_con_asignacion_fija"]
        )

        if not equipos_libres_general:
            logger.info("No hay equipos libres en el Pool General para desborde.")
            return

        necesidades_globales = {}
        for rid, rcfg in estado_global["mapa_config_robots"].items():
            if rid in estado_global["carga_trabajo_por_robot"]:
                tickets = estado_global["carga_trabajo_por_robot"].get(rid, 0)
                equipos_necesarios = self._calcular_equipos_necesarios_para_robot(rid, tickets, rcfg)
                equipos_actuales = len(estado_global["mapa_asignaciones_dinamicas"].get(rid, []))
                diferencia = equipos_necesarios - equipos_actuales
                if diferencia > 0:
                    necesidades_globales[rid] = diferencia

        robots_por_prioridad = sorted(
            necesidades_globales.keys(),
            key=lambda r: estado_global["mapa_config_robots"][r].get("PrioridadBalanceo", 100),
        )
        for rid in robots_por_prioridad:
            necesidad = necesidades_globales[rid]
            while necesidad > 0 and equipos_libres_general:
                equipo_a_asignar = equipos_libres_general.pop(0)
                if self._realizar_asignacion_db(rid, equipo_a_asignar, "ASIGNAR_DESBORDE_GLOBAL", estado_global):
                    necesidad -= 1
        logger.info("ETAPA DE DESBORDE Y DEMANDA ADICIONAL GLOBAL completada.")

    def _calcular_equipos_necesarios_para_robot(self, robot_id: int, tickets: int, config: Dict) -> int:
        if tickets <= 0:
            return config.get("MinEquipos", 1) if config.get("EsOnline") else 0
        min_eq = config.get("MinEquipos", 1)
        max_eq = config.get("MaxEquipos", -1)
        ratio = config.get("TicketsPorEquipoAdicional", 10)
        ratio = ratio if ratio > 0 else 1
        needed = min_eq + math.floor(tickets / ratio)
        return min(needed, max_eq) if max_eq != -1 else needed

    def _liberar_equipos_de_robot(self, robot_id: int, motivo: str, estado_global: Dict[str, Any]):
        equipos_a_liberar = list(estado_global["mapa_asignaciones_dinamicas"].get(robot_id, []))
        if not equipos_a_liberar:
            return
        logger.warning(f"RobotId {robot_id} ya no es candidato. Liberando sus {len(equipos_a_liberar)} equipos.")
        for equipo_id in equipos_a_liberar:
            self._realizar_desasignacion_db(robot_id, equipo_id, motivo, estado_global)

    def _realizar_asignacion_db(
        self, robot_id: int, equipo_id: int, motivo: str, estado_global: Dict[str, Any]
    ) -> bool:
        puede_asignar, justificacion = self.cooling_manager.puede_ampliar(robot_id)
        if not puede_asignar:
            logger.debug(f"Asignación omitida por CoolingManager para RobotId {robot_id}. Just: {justificacion}")
            return False
        query = "INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, Reservado, AsignadoPor) VALUES (?, ?, 0, 0, ?)"
        try:
            self.db_sam.ejecutar_consulta(query, (robot_id, equipo_id, motivo), es_select=False)
            estado_global["mapa_asignaciones_dinamicas"].setdefault(robot_id, []).append(equipo_id)
            self.cooling_manager.registrar_ampliacion(
                robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0), 1
            )
            return True
        except Exception as e:
            logger.error(f"Error al asignar RobotId {robot_id} a EquipoId {equipo_id}: {e}")
            return False

    def _realizar_desasignacion_db(
        self, robot_id: int, equipo_id: int, motivo: str, estado_global: Dict[str, Any]
    ) -> bool:
        puede_desasignar, justificacion = self.cooling_manager.puede_reducir(
            robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0)
        )
        if not puede_desasignar:
            logger.info(f"Desasignación omitida por CoolingManager para RobotId {robot_id}. Just: {justificacion}")
            return False
        query = "DELETE FROM dbo.Asignaciones WHERE RobotId = ? AND EquipoId = ? AND (EsProgramado = 0 OR EsProgramado IS NULL) AND (Reservado = 0 OR Reservado IS NULL)"
        try:
            self.db_sam.ejecutar_consulta(query, (robot_id, equipo_id), es_select=False)
            if (
                robot_id in estado_global["mapa_asignaciones_dinamicas"]
                and equipo_id in estado_global["mapa_asignaciones_dinamicas"][robot_id]
            ):
                estado_global["mapa_asignaciones_dinamicas"][robot_id].remove(equipo_id)
            self.cooling_manager.registrar_reduccion(
                robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0), 1
            )
            return True
        except Exception as e:
            logger.error(f"Error al desasignar RobotId {robot_id} de EquipoId {equipo_id}: {e}")
            return False
