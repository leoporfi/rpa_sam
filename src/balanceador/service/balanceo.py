# SAM/src/balanceador/service/balanceo.py

import logging
import math
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from balanceador.database.historico_client import HistoricoBalanceoClient
from balanceador.service.cooling_manager import CoolingManager

logger = logging.getLogger(__name__)


class Balanceo:
    """
    Contiene la lógica central y el algoritmo para el balanceo de cargas.
    Esta clase toma decisiones sobre cuándo y cómo asignar o desasignar equipos
    a los robots basándose en la carga de trabajo y las reglas de negocio.
    """

    def __init__(self, balanceador_instance):
        """
        Inicializa la clase de lógica de balanceo.
        """
        self.balanceador = balanceador_instance
        # Inyección de dependencias desde la instancia principal.
        for attr_name in ["db_sam", "notificador", "cfg_balanceador_specifics"]:
            # for attr_name in ["db_sam", "db_rpa360", "clouders_client", "cfg_balanceador_specifics", "notificador"]:
            if hasattr(balanceador_instance, attr_name):
                setattr(self, attr_name, getattr(balanceador_instance, attr_name))
            else:
                raise AttributeError(f"La instancia del Balanceador no tiene el atributo '{attr_name}'")

        self.historico_client = HistoricoBalanceoClient(self.db_sam)
        cooling_period = self.cfg_balanceador_specifics.get("cooling_period_seg", 300)
        self.cooling_manager = CoolingManager(cooling_period_seconds=cooling_period)
        self.aislamiento_estricto_pool = self.cfg_balanceador_specifics.get("aislamiento_estricto_pool", True)
        self._lock = threading.RLock()
        logger.info(f"Modo de aislamiento estricto de pools: {'Activado' if self.aislamiento_estricto_pool else 'Desactivado'}")

    def ejecutar_algoritmo_completo(self, carga_consolidada: Dict[int, int], pools_activos: List[Dict[str, Any]]):
        """
        Orquesta todas las fases del algoritmo de balanceo.
        """
        with self._lock:
            # Etapa 0: Obtener la fotografía completa del estado del sistema UNA SOLA VEZ
            estado_global = self._obtener_estado_inicial_global(carga_consolidada)

            # Etapa 1: Limpieza Global
            self.ejecutar_limpieza_global(estado_global)

            # Etapa 2: Balanceo Interno de cada Pool
            pool_ids = [p["PoolId"] for p in pools_activos]
            if None not in pool_ids:
                pool_ids.append(None)  # Asegurar que el Pool General siempre se procese

            for pool_id in pool_ids:
                self.ejecutar_balanceo_interno_de_pool(pool_id, estado_global)

            # Etapa 3: Desborde y Demanda Adicional Global
            self.ejecutar_fase_de_desborde_global(estado_global)

    def _obtener_estado_inicial_global(self, carga_consolidada: Dict[int, int]) -> Dict[str, Any]:
        """
        Recopila toda la información necesaria de la base de datos para tomar decisiones.
        """
        logger.info("Obteniendo estado inicial global del sistema...")
        # Lógica para obtener robots, equipos, asignaciones, etc.
        # Esto centraliza todas las lecturas de la BD al inicio del ciclo.

        robots_activos_query = "SELECT RobotId, Robot, EsOnline, MinEquipos, MaxEquipos, PrioridadBalanceo, TicketsPorEquipoAdicional, PoolId FROM dbo.Robots WHERE Activo = 1"
        mapa_config_robots = {r["RobotId"]: r for r in self.db_sam.ejecutar_consulta(robots_activos_query, es_select=True) or []}

        equipos_validos_query = "SELECT EquipoId, PoolId FROM dbo.Equipos WHERE Activo_SAM = 1 AND PermiteBalanceoDinamico = 1"
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

    def _obtener_estado_inicial_global_old(self):
        """
        Recopila toda la información necesaria de la base de datos para tomar decisiones.
        """
        logger.debug("Obteniendo estado inicial global del sistema...")
        query_equipos = "SELECT EquipoId, PoolId FROM dbo.Equipos WHERE PermiteBalanceoDinamico = 1 AND Activo_SAM = 1;"
        equipos_dinamicos_list = self.db_sam.ejecutar_consulta(query_equipos, es_select=True) or []

        mapa_equipos_validos_por_pool: Dict[Optional[int], Set[int]] = {None: set()}
        for eq in equipos_dinamicos_list:
            mapa_equipos_validos_por_pool.setdefault(eq["PoolId"], set()).add(eq["EquipoId"])

        query_asignaciones = "SELECT RobotId, EquipoId, Reservado, EsProgramado FROM dbo.Asignaciones;"
        asignaciones_list = self.db_sam.ejecutar_consulta(query_asignaciones, es_select=True) or []

        mapa_asignaciones_dinamicas: Dict[int, List[int]] = {}
        asignaciones_fijas_equipos: Set[int] = set()

        for a in asignaciones_list:
            if a.get("Reservado") or a.get("EsProgramado"):
                if a.get("EquipoId"):
                    asignaciones_fijas_equipos.add(a["EquipoId"])
            else:
                if a.get("RobotId") and a.get("EquipoId"):
                    mapa_asignaciones_dinamicas.setdefault(a["RobotId"], []).append(a["EquipoId"])

        query_ejecuciones = "SELECT RobotId, EquipoId FROM dbo.Ejecuciones WHERE Estado IN ('PENDING_EXECUTION', 'DEPLOYED', 'RUNNING', 'UPDATE', 'RUN_PAUSED', 'QUEUED');"
        ejecuciones_list = self.db_sam.ejecutar_consulta(query_ejecuciones, es_select=True) or []

        equipos_en_uso_por_robot: Dict[int, Set[int]] = {}
        for e in ejecuciones_list:
            if e.get("RobotId") and e.get("EquipoId"):
                equipos_en_uso_por_robot.setdefault(e["RobotId"], set()).add(e["EquipoId"])

        carga_trabajo_por_robot = self.balanceador._obtener_carga_de_trabajo_consolidada()

        return {
            "mapa_equipos_validos_por_pool": mapa_equipos_validos_por_pool,
            "carga_trabajo_por_robot": carga_trabajo_por_robot,
            "mapa_asignaciones_dinamicas": mapa_asignaciones_dinamicas,
            "asignaciones_fijas_equipos": asignaciones_fijas_equipos,
            "equipos_en_uso_por_robot": equipos_en_uso_por_robot,
        }

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

        equipos_actualmente_asignados_en_pool = {eq for rid in robots_del_pool for eq in estado_global["mapa_asignaciones_dinamicas"].get(rid, [])}
        equipos_libres_del_pool = list(
            estado_global["mapa_equipos_validos_por_pool"].get(pool_id, set())
            - equipos_actualmente_asignados_en_pool
            - estado_global["equipos_con_asignacion_fija"]
        )

        # 1. Calcular necesidades y excedentes
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

        # 2. Asignar para cubrir necesidades
        robots_por_prioridad = sorted(necesidades.keys(), key=lambda r: estado_global["mapa_config_robots"][r].get("PrioridadBalanceo", 100))
        for rid in robots_por_prioridad:
            necesidad = necesidades[rid]
            while necesidad > 0 and equipos_libres_del_pool:
                equipo_a_asignar = equipos_libres_del_pool.pop(0)
                if self._realizar_asignacion_db(rid, equipo_a_asignar, "ASIGNAR_DEMANDA_POOL", estado_global):
                    necesidad -= 1

        # 3. Desasignar excedentes
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

        equipos_asignados_globalmente = {eq for subl in estado_global["mapa_asignaciones_dinamicas"].values() for eq in subl}
        equipos_libres_general = list(
            estado_global["mapa_equipos_validos_por_pool"].get(None, set())
            - equipos_asignados_globalmente
            - estado_global["equipos_con_asignacion_fija"]
        )

        if not equipos_libres_general:
            logger.info("No hay equipos libres en el Pool General para desborde.")
            return

        # Calcular necesidades restantes de TODOS los robots
        necesidades_globales = {}
        for rid, rcfg in estado_global["mapa_config_robots"].items():
            if rid in estado_global["carga_trabajo_por_robot"]:
                tickets = estado_global["carga_trabajo_por_robot"].get(rid, 0)
                equipos_necesarios = self._calcular_equipos_necesarios_para_robot(rid, tickets, rcfg)
                equipos_actuales = len(estado_global["mapa_asignaciones_dinamicas"].get(rid, []))
                diferencia = equipos_necesarios - equipos_actuales
                if diferencia > 0:
                    necesidades_globales[rid] = diferencia

        robots_por_prioridad = sorted(necesidades_globales.keys(), key=lambda r: estado_global["mapa_config_robots"][r].get("PrioridadBalanceo", 100))
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

        logger.warning(f"RobotId {robot_id} ya no es candidato para balanceo. Liberando sus {len(equipos_a_liberar)} equipos.")
        for equipo_id in equipos_a_liberar:
            self._realizar_desasignacion_db(robot_id, equipo_id, motivo, estado_global)

    def _realizar_asignacion_db(self, robot_id: int, equipo_id: int, motivo: str, estado_global: Dict[str, Any]) -> bool:
        """Maneja la lógica de asignación, incluyendo CoolingManager y actualización de estado."""
        puede_asignar, justificacion = self.cooling_manager.puede_ampliar(robot_id)
        if not puede_asignar:
            logger.debug(f"Asignación para RobotId {robot_id} omitida por CoolingManager. Justificación: {justificacion}")
            return False

        query = "INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, Reservado, AsignadoPor) VALUES (?, ?, 0, 0, ?)"
        try:
            self.db_sam.ejecutar_consulta(query, (robot_id, equipo_id, motivo), es_select=False)

            # Actualizar estado en memoria
            if robot_id not in estado_global["mapa_asignaciones_dinamicas"]:
                estado_global["mapa_asignaciones_dinamicas"][robot_id] = []
            estado_global["mapa_asignaciones_dinamicas"][robot_id].append(equipo_id)

            self.cooling_manager.registrar_ampliacion(robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0), 1)
            # Registrar en histórico
            return True
        except Exception as e:
            logger.error(f"Error al asignar RobotId {robot_id} a EquipoId {equipo_id}: {e}")
            return False

    def _realizar_desasignacion_db(self, robot_id: int, equipo_id: int, motivo: str, estado_global: Dict[str, Any]) -> bool:
        """Maneja la lógica de desasignación, incluyendo CoolingManager y actualización de estado."""
        puede_desasignar, justificacion = self.cooling_manager.puede_reducir(robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0))
        if not puede_desasignar:
            logger.info(f"Desasignación de RobotId {robot_id} omitida por CoolingManager. Just: {justificacion}")
            return False

        query = "DELETE FROM dbo.Asignaciones WHERE RobotId = ? AND EquipoId = ? AND (EsProgramado = 0 OR EsProgramado IS NULL) AND (Reservado = 0 OR Reservado IS NULL)"
        try:
            self.db_sam.ejecutar_consulta(query, (robot_id, equipo_id), es_select=False)

            # Actualizar estado en memoria
            if robot_id in estado_global["mapa_asignaciones_dinamicas"] and equipo_id in estado_global["mapa_asignaciones_dinamicas"][robot_id]:
                estado_global["mapa_asignaciones_dinamicas"][robot_id].remove(equipo_id)

            self.cooling_manager.registrar_reduccion(robot_id, estado_global["carga_trabajo_por_robot"].get(robot_id, 0), 1)
            # Registrar en histórico
            return True
        except Exception as e:
            logger.error(f"Error al desasignar RobotId {robot_id} de EquipoId {equipo_id}: {e}")
            return False

    def _realizar_asignacion_db_old(self, robot_id: int, equipo_id: int, motivo: str = "Balanceador") -> bool:
        """
        Ejecuta la operación de INSERT en la base de datos para asignar un equipo a un robot.
        """
        try:
            query_insert = """
            INSERT INTO dbo.Asignaciones
            (RobotId, EquipoId, EsProgramado, Reservado, AsignadoPor, FechaAsignacion)
            VALUES (?, ?, 0, 0, ?, GETDATE());
            """
            self.db_sam.ejecutar_consulta(query_insert, (robot_id, equipo_id, motivo[:50]), es_select=False)
            logger.info(f"RobotId {robot_id}: Asignado dinámicamente a EquipoId {equipo_id} (Motivo: {motivo}).")
            return True
        except Exception as e_assign:
            logger.error(f"RobotId {robot_id}: Error al asignar EquipoId {equipo_id}: {e_assign}", exc_info=True)
            return False

    def _realizar_desasignacion_db_old(self, robot_id: int, equipo_id: int) -> bool:
        """
        Ejecuta la operación de DELETE en la base de datos para desasignar un equipo.
        Importante: Solo borra asignaciones dinámicas (Reservado=0 y EsProgramado=0).
        """
        logger.debug(f"_realizar_desasignacion_db: Intentando DELETE para RobotId {robot_id}, EquipoId {equipo_id}")
        try:
            query_delete = """
            DELETE FROM dbo.Asignaciones
            WHERE RobotId = ? AND EquipoId = ? AND Reservado = 0 AND EsProgramado = 0;
            """
            rowcount = self.db_sam.ejecutar_consulta(query_delete, (robot_id, equipo_id), es_select=False)
            if rowcount is not None and rowcount > 0:
                logger.info(f"_realizar_desasignacion_db: ÉXITO. RobotId {robot_id}, EquipoId {equipo_id} desasignado...")
                return True
            else:
                logger.warning(f"_realizar_desasignacion_db: NINGUNA FILA BORRADA. RobotId {robot_id}, EquipoId {equipo_id}...")
                return False
        except Exception as e_deassign:
            logger.error(f"_realizar_desasignacion_db: EXCEPCIÓN ...: {e_deassign}", exc_info=True)
            return False

    def _get_min_requerido_funcional(self, config_robot: Dict[str, Any], tickets_robot: int) -> int:
        """
        Calcula el número mínimo de equipos que un robot necesita en este momento.
        """
        min_equipos_db = config_robot.get("MinEquipos", 1)
        return max(1, min_equipos_db) if tickets_robot > 0 else min_equipos_db

    def _validar_y_limpiar_asignaciones_por_coherencia_pool(
        self,
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
        mapa_config_robots: Dict[int, Dict[str, Any]],
        mapa_equipos_validos_por_pool: Dict[Optional[int], Set[int]],
        robot_state: Dict[str, Any],
    ):
        """
        Paso de saneamiento: Valida que cada asignación dinámica sea coherente.
        """
        logger.info("Pre-Fase: Validando coherencia de Pools en asignaciones dinámicas existentes...")
        carga_trabajo_por_robot = robot_state["carga_trabajo_por_robot"]
        robots_con_asignaciones = list(mapa_equipos_asignados_dinamicamente.keys())

        for robot_id in robots_con_asignaciones:
            config_robot = mapa_config_robots.get(robot_id)
            if not config_robot:
                continue  # El robot ya no es candidato, se limpiará en Fase 0

            robot_pool_id = config_robot.get("PoolId")  # Puede ser None para el Pool General
            equipos_validos_para_este_robot = mapa_equipos_validos_por_pool.get(robot_pool_id, set())

            equipos_originalmente_asignados = list(mapa_equipos_asignados_dinamicamente.get(robot_id, []))
            equipos_coherentes_a_mantener = []

            for equipo_id in equipos_originalmente_asignados:
                if equipo_id in equipos_validos_para_este_robot:
                    equipos_coherentes_a_mantener.append(equipo_id)
                else:
                    logger.warning(
                        f"Pre-Fase: INCOHERENCIA DETECTADA. RobotId {robot_id} (PoolId: {robot_pool_id}) "
                        f"está asignado a EquipoId {equipo_id}, que no pertenece a su pool. Intentando desasignar."
                    )
                    num_actual_din = len(mapa_equipos_asignados_dinamicamente.get(robot_id, []))
                    tickets_robot = carga_trabajo_por_robot.get(robot_id, 0)
                    can_reduce, reason = self.cooling_manager.puede_reducirse(robot_id, tickets_robot, num_actual_din)

                    if can_reduce:
                        if self._realizar_desasignacion_db(robot_id, equipo_id):
                            self.historico_client.registrar_decision_balanceo(
                                robot_id,
                                robot_pool_id,
                                tickets_robot,
                                num_actual_din,
                                num_actual_din - 1,
                                "DESASIGNAR_INCOHERENCIA_POOL",
                                f"Equipo {equipo_id} no pertenece al pool del robot.",
                            )
                        else:
                            logger.error(f"Pre-Fase: Fallo al desasignar EquipoId {equipo_id} (incoherente) de RobotId {robot_id}.")
                            equipos_coherentes_a_mantener.append(equipo_id)
                    else:
                        logger.info(f"Pre-Fase: Desasignación de EquipoId {equipo_id} (incoherente) en espera por CoolingManager: {reason}")
                        equipos_coherentes_a_mantener.append(equipo_id)

            mapa_equipos_asignados_dinamicamente[robot_id] = equipos_coherentes_a_mantener

        logger.info("Pre-Fase: Validación de coherencia de Pools completada.")

    def _liberar_equipos_robot_no_candidato(
        self,
        robot_id: int,
        config_robot: Dict[str, Any],
        equipos_asignados: List[int],
        equipos_en_uso: Set[int],
        carga_trabajo: int,
        mapa_asignaciones: Dict[int, List[int]],
    ) -> int:
        """Libera los equipos asignados a un robot que ya no es candidato."""
        num_actual_din = len(equipos_asignados)
        can_sd, just_sd = self.cooling_manager.puede_reducirse(robot_id, carga_trabajo, num_actual_din)
        if not can_sd:
            logger.info(f"Fase 0: Desasignación de RobotId {robot_id} (no candidato) en espera por CoolingManager. Just: {just_sd}")
            return 0

        a_liberar_no_en_uso: List[int] = [eq_id for eq_id in equipos_asignados if eq_id not in equipos_en_uso]
        equipos_a_intentar_liberar: List[int] = a_liberar_no_en_uso + [eq_id for eq_id in equipos_asignados if eq_id in equipos_en_uso]

        liberados_count = 0
        for equipo_id in equipos_a_intentar_liberar:
            if self._realizar_desasignacion_db(robot_id, equipo_id):
                if robot_id in mapa_asignaciones and equipo_id in mapa_asignaciones[robot_id]:
                    mapa_asignaciones[robot_id].remove(equipo_id)
                liberados_count += 1

        if liberados_count > 0:
            self.cooling_manager.registrar_reduccion(robot_id, carga_trabajo, liberados_count)
            self.historico_client.registrar_decision_balanceo(
                robot_id,
                config_robot.get("PoolId"),
                carga_trabajo,
                num_actual_din,
                num_actual_din - liberados_count,
                "DESASIGNAR_INACTIVO_OFFLINE",
                f"Robot no Act/On. Liberados:{liberados_count}. JustCool:{just_sd}",
            )
        return liberados_count

    def _limpiar_asignaciones_robots_no_candidatos(
        self,
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
        carga_trabajo_por_robot: Dict[int, int],
        equipos_en_uso_por_robot: Dict[int, Set[int]],
        mapa_config_robots: Dict[int, Dict[str, Any]],
    ):
        logger.info("Fase 0: Limpieza de Asignaciones a Robots Inactivos/Offline...")

        for robot_id in list(mapa_equipos_asignados_dinamicamente.keys()):
            # La condición es simple: si un robot tiene asignaciones dinámicas pero
            # NO está en la lista de candidatos válidos para este ciclo, se le quitan.
            if robot_id not in mapa_config_robots:
                equipos_asignados = list(mapa_equipos_asignados_dinamicamente.get(robot_id, []))
                if not equipos_asignados:
                    continue

                logger.warning(f"Fase 0: RobotId {robot_id} ya no es candidato para balanceo. Liberando sus {len(equipos_asignados)} equipos.")

                self._liberar_equipos_robot_no_candidato(
                    robot_id,
                    {},  # Se pasa un dict vacío porque la config no existe
                    equipos_asignados,
                    equipos_en_uso_por_robot.get(robot_id, set()),
                    carga_trabajo_por_robot.get(robot_id, 0),
                    mapa_equipos_asignados_dinamicamente,
                )

            if not mapa_equipos_asignados_dinamicamente.get(robot_id):
                del mapa_equipos_asignados_dinamicamente[robot_id]

        logger.info("Fase 0: Limpieza de Asignaciones por Robot Inactivo/Offline completada.")

    def _obtener_robots_candidatos(self) -> Dict[int, Dict[str, Any]]:
        """Obtiene la configuración de todos los robots elegibles para balanceo."""
        query = """
        SELECT RobotId, Robot, MinEquipos, MaxEquipos, PrioridadBalanceo, TicketsPorEquipoAdicional, PoolId
        FROM dbo.Robots 
        WHERE Activo = 1 AND EsOnline = 1
        ORDER BY PrioridadBalanceo DESC, RobotId;
        """
        robots_candidatos_config_list = self.db_sam.ejecutar_consulta(query, es_select=True) or []
        return {r["RobotId"]: r for r in robots_candidatos_config_list}

    def _procesar_fase_satisfaccion_minimos(
        self,
        mapa_config_robots: Dict[int, Dict[str, Any]],
        carga_trabajo_por_robot: Dict[int, int],
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
    ) -> List[Tuple[int, int, int, Optional[int], Dict[str, Any], int, int]]:
        logger.info("Fase 1: Satisfacción de Mínimos...")
        min_needs_list = []
        for r_id, r_cfg in mapa_config_robots.items():
            if self.balanceador._is_shutting_down:
                break
            tickets = carga_trabajo_por_robot.get(r_id, 0)
            if tickets <= 0:
                continue

            min_req = self._get_min_requerido_funcional(r_cfg, tickets)
            num_actual_din = len(mapa_equipos_asignados_dinamicamente.get(r_id, []))

            if num_actual_din < min_req:
                faltante = min_req - num_actual_din
                can_add, just_add = self.cooling_manager.puede_ampliarse(r_id, tickets, num_actual_din)
                if can_add:
                    min_needs_list.append((r_id, faltante, r_cfg.get("PrioridadBalanceo", 100), r_cfg.get("PoolId"), r_cfg, tickets, num_actual_din))
                else:
                    logger.info(f"Fase 1: RobotId {r_id} necesita {faltante} para min, pero CoolingManager impide. Just: {just_add}")

        return sorted(min_needs_list, key=lambda x: (x[2], x[1]), reverse=True)

    def _procesar_fase_desasignacion_excedentes(
        self,
        mapa_config_robots: Dict[int, Dict[str, Any]],
        carga_trabajo_por_robot: Dict[int, int],
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
        equipos_en_uso_por_robot: Dict[int, Set[int]],
    ):
        logger.info("Fase 2: Desasignación de Excedentes...")
        for r_id, r_cfg in mapa_config_robots.items():
            if self.balanceador._is_shutting_down:
                break
            tickets = carga_trabajo_por_robot.get(r_id, 0)
            equipos_nec = self.balanceador._calcular_equipos_necesarios_para_robot(tickets, r_cfg)
            min_req = self._get_min_requerido_funcional(r_cfg, tickets)
            target = max(equipos_nec, min_req if tickets > 0 else 0)
            num_actual = len(mapa_equipos_asignados_dinamicamente.get(r_id, []))

            if num_actual > target:
                can_reduce, just_reduce = self.cooling_manager.puede_reducirse(r_id, tickets, num_actual)
                if can_reduce:
                    a_liberar = num_actual - target
                    equipos_del_robot = list(mapa_equipos_asignados_dinamicamente.get(r_id, []))
                    equipos_en_uso = equipos_en_uso_por_robot.get(r_id, set())
                    candidatos = [e for e in equipos_del_robot if e not in equipos_en_uso] + [e for e in equipos_del_robot if e in equipos_en_uso]

                    liberados_count = 0
                    for eq_id in candidatos[:a_liberar]:
                        if self._realizar_desasignacion_db(r_id, eq_id):
                            mapa_equipos_asignados_dinamicamente[r_id].remove(eq_id)
                            liberados_count += 1

                    if liberados_count > 0:
                        self.cooling_manager.registrar_reduccion(r_id, tickets, liberados_count)
                        self.historico_client.registrar_decision_balanceo(
                            r_id, r_cfg.get("PoolId"), tickets, num_actual, num_actual - liberados_count, "DESASIGNAR_EXCEDENTE", just_reduce
                        )
                else:
                    logger.info(f"Fase 2: Desasignación excedente RobotId {r_id} en espera por CoolingManager: {just_reduce}")

    def _obtener_necesidades_adicionales(
        self,
        mapa_config_robots: Dict[int, Dict[str, Any]],
        carga_trabajo_por_robot: Dict[int, int],
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
        # NUEVO PARÁMETRO PARA CONTROLAR EL COMPORTAMIENTO
        es_fase_desborde_global: bool = False,
    ) -> List[Tuple[int, int, int, Optional[int], Dict[str, Any], int, int]]:
        necesidades_adicionales_final = []
        for r_id, r_cfg in mapa_config_robots.items():
            if self.balanceador._is_shutting_down:
                break
            tickets = carga_trabajo_por_robot.get(r_id, 0)
            if tickets <= 0:
                continue

            equipos_nec = self.balanceador._calcular_equipos_necesarios_para_robot(tickets, r_cfg)
            num_actual = len(mapa_equipos_asignados_dinamicamente.get(r_id, []))
            max_cfg = r_cfg.get("MaxEquipos", -1)
            limite = equipos_nec if max_cfg == -1 else min(equipos_nec, max_cfg)

            if num_actual < limite:
                necesidad = limite - num_actual
                can_add, just_add = self.cooling_manager.puede_ampliarse(r_id, tickets, num_actual)
                if can_add:
                    # LÓGICA DE AISLAMIENTO: Se aplica solo si estamos en la fase de desborde global
                    if es_fase_desborde_global and self.aislamiento_estricto_pool and r_cfg.get("PoolId") is not None:
                        logger.info(
                            f"Fase 3: RobotId {r_id} (PoolId: {r_cfg.get('PoolId')}) tiene necesidad adicional pero NO participará en desborde (aislamiento estricto activado)."
                        )
                    else:
                        necesidades_adicionales_final.append(
                            (r_id, necesidad, r_cfg.get("PrioridadBalanceo", 100), r_cfg.get("PoolId"), r_cfg, tickets, num_actual)
                        )
                else:
                    logger.info(f"Fase 3: RobotId {r_id} necesita {necesidad} adic, pero CoolingManager impide. Just: {just_add}")

        return sorted(necesidades_adicionales_final, key=lambda x: (x[2], x[1]), reverse=True)

    def _asignar_equipos_adicionales(
        self,
        necesidades_adicionales: List[Tuple[int, int, int, Optional[int], Dict[str, Any], int, int]],
        equipos_libres: List[int],
        mapa_equipos_asignados_dinamicamente: Dict[int, List[int]],
        motivo_asignacion: str,
    ):
        for r_id, nec, prio, pool_id, _, tks, num_antes in necesidades_adicionales:
            if self.balanceador._is_shutting_down or not equipos_libres:
                break
            a_asignar = min(nec, len(equipos_libres))
            asignados_count = 0
            for _ in range(a_asignar):
                if not equipos_libres:
                    break
                eq_id = equipos_libres.pop(0)
                if self._realizar_asignacion_db(r_id, eq_id, motivo_asignacion):
                    mapa_equipos_asignados_dinamicamente.setdefault(r_id, []).append(eq_id)
                    asignados_count += 1
                else:
                    equipos_libres.insert(0, eq_id)

            if asignados_count > 0:
                self.cooling_manager.registrar_ampliacion(r_id, tks, asignados_count)
                self.historico_client.registrar_decision_balanceo(
                    r_id, pool_id, tks, num_antes, num_antes + asignados_count, motivo_asignacion, f"Prio:{prio}"
                )

    def _calcular_equipos_necesarios_para_robot_old(self, robot_id: int, tickets: int, config: Dict) -> int:
        """
        Calcula los equipos necesarios para un robot basado en su carga y configuración.
        """
        if tickets <= 0:
            return 0
        min_equipos = config.get("MinEquipos", 1)
        max_equipos = config.get("MaxEquipos", -1)
        ratio = config.get("TicketsPorEquipoAdicional", 10)  # Default a 10 si no está
        if ratio <= 0:
            ratio = 1  # Evitar división por cero

        equipos_necesarios = min_equipos + math.floor(max(0, tickets) / ratio)

        if max_equipos != -1:
            return min(equipos_necesarios, max_equipos)

        return equipos_necesarios
