# Agrega estas importaciones al inicio del archivo database.py
import asyncio
import logging
from typing import Dict, List, Optional

from sam.common.a360_client import AutomationAnywhereClient
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector

# RFR-29: Se importa el nuevo sincronizador común
from sam.common.sincronizador_comun import SincronizadorComun

from .schemas import RobotCreateRequest, RobotUpdateRequest, ScheduleData

logger = logging.getLogger(__name__)


# Robots
def get_robots(
    db: DatabaseConnector,
    name: Optional[str] = None,
    active: Optional[bool] = None,
    online: Optional[bool] = None,
    page: int = 1,
    size: int = 20,
    sort_by: str = "Robot",
    sort_dir: str = "asc",
) -> Dict:
    sortable_columns = {
        "Robot": "r.Robot",
        "CantidadEquiposAsignados": "ISNULL(ea.Equipos, 0)",
        "Activo": "r.Activo",
        "EsOnline": "r.EsOnline",
        "TieneProgramacion": "(CASE WHEN EXISTS (SELECT 1 FROM dbo.Programaciones p WHERE p.RobotId = r.RobotId AND p.Activo = 1) THEN 1 ELSE 0 END)",
        "PrioridadBalanceo": "r.PrioridadBalanceo",
        "TicketsPorEquipoAdicional": "r.TicketsPorEquipoAdicional",
    }
    order_by_column = sortable_columns.get(sort_by, "r.Robot")
    order_by_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    select_from_clause = "FROM dbo.Robots r LEFT JOIN dbo.EquiposAsignados ea ON r.Robot = ea.Robot"
    conditions: List[str] = []
    params: List[any] = []

    if name:
        conditions.append("r.Robot LIKE ?")
        params.append(f"%{name}%")
    if active is not None:
        conditions.append("r.Activo = ?")
        params.append(active)
    if online is not None:
        conditions.append("r.EsOnline = ?")
        params.append(online)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    count_query = f"SELECT COUNT(*) as total_count {select_from_clause} {where_clause}"
    total_count_result = db.ejecutar_consulta(count_query, tuple(params), es_select=True)
    total_count = total_count_result[0]["total_count"] if total_count_result else 0

    offset = (page - 1) * size
    main_query = f"""
        SELECT
            r.RobotId, r.Robot, r.Descripcion, r.MinEquipos, r.MaxEquipos,
            r.EsOnline, r.Activo, r.PrioridadBalanceo,
            r.TicketsPorEquipoAdicional,
            ISNULL(ea.Equipos, 0) as CantidadEquiposAsignados,
            CAST(CASE WHEN EXISTS (SELECT 1 FROM dbo.Programaciones p WHERE p.RobotId = r.RobotId AND p.Activo = 1)
                 THEN 1 ELSE 0 END AS BIT) AS TieneProgramacion
        {select_from_clause}
        {where_clause}
        ORDER BY {order_by_column} {order_by_direction}
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    pagination_params = params + [offset, size]
    robots_data = db.ejecutar_consulta(main_query, tuple(pagination_params), es_select=True)

    return {"total_count": total_count, "page": page, "size": size, "robots": robots_data}


def update_robot_status(db: DatabaseConnector, robot_id: int, field: str, value: bool) -> bool:
    query = f"UPDATE dbo.Robots SET {field} = ? WHERE RobotId = ?"
    params = (value, robot_id)
    rows_affected = db.ejecutar_consulta(query, params, es_select=False)
    return rows_affected > 0


def update_robot_details(db: DatabaseConnector, robot_id: int, robot_data: RobotUpdateRequest) -> int:
    query = """
        UPDATE dbo.Robots SET
            Robot = ?, Descripcion = ?, MinEquipos = ?, MaxEquipos = ?,
            PrioridadBalanceo = ?, TicketsPorEquipoAdicional = ?
        WHERE RobotId = ?
    """
    params = (
        robot_data.Robot,
        robot_data.Descripcion,
        robot_data.MinEquipos,
        robot_data.MaxEquipos,
        robot_data.PrioridadBalanceo,
        robot_data.TicketsPorEquipoAdicional,
        robot_id,
    )
    return db.ejecutar_consulta(query, params, es_select=False)


def create_robot(db: DatabaseConnector, robot_data: RobotCreateRequest) -> Dict:
    query = """
        INSERT INTO dbo.Robots (RobotId, Robot, Descripcion, MinEquipos, MaxEquipos, PrioridadBalanceo, TicketsPorEquipoAdicional)
        OUTPUT INSERTED.*
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    params = (
        robot_data.RobotId,
        robot_data.Robot,
        robot_data.Descripcion,
        robot_data.MinEquipos,
        robot_data.MaxEquipos,
        robot_data.PrioridadBalanceo,
        robot_data.TicketsPorEquipoAdicional,
    )
    try:
        new_robot = db.ejecutar_consulta(query, params, es_select=True)
        if not new_robot:
            return None
        return new_robot[0]
    except Exception as e:
        if "Violation of PRIMARY KEY constraint" in str(e):
            raise ValueError(f"El RobotId {robot_data.RobotId} ya existe.")
        raise


# Asignaciones
def get_asignaciones_by_robot(db: DatabaseConnector, robot_id: int) -> List[Dict]:
    query = """
        SELECT A.RobotId, A.EquipoId, A.Equipo, A.EsProgramado, A.Reservado
        FROM dbo.AsignacionesView AS A
        WHERE A.RobotId = ?
    """
    return db.ejecutar_consulta(query, (robot_id,), es_select=True)


def update_asignaciones_robot(
    db: DatabaseConnector, robot_id: int, assign_ids: List[int], unassign_ids: List[int]
) -> Dict:
    robot_info = db.ejecutar_consulta("SELECT EsOnline FROM dbo.Robots WHERE RobotId = ?", (robot_id,), es_select=True)
    if not robot_info:
        raise ValueError("Robot no encontrado")

    try:
        with db.obtener_cursor() as cursor:
            # 1. Desasignar equipos
            if unassign_ids:
                unassign_placeholders = ",".join("?" for _ in unassign_ids)
                unassign_query = (
                    f"DELETE FROM dbo.Asignaciones WHERE RobotId = ? AND EquipoId IN ({unassign_placeholders})"
                )
                cursor.execute(unassign_query, robot_id, *unassign_ids)

            # 2. Asignar nuevos equipos
            if assign_ids:
                assign_query = """
                    INSERT INTO dbo.Asignaciones (RobotId, EquipoId, EsProgramado, Reservado, AsignadoPor)
                    VALUES (?, ?, 0, 1, 'WebApp')
                """
                assign_params = [(robot_id, equipo_id) for equipo_id in assign_ids]
                cursor.executemany(assign_query, assign_params)

            cursor.commit()
            return {"message": "Asignaciones actualizadas correctamente."}
    except Exception as e:
        logger.error(f"Error al actualizar asignaciones para el robot {robot_id}: {e}", exc_info=True)
        raise


def get_available_teams_for_robot(db: DatabaseConnector) -> List[Dict]:
    """
    Obtiene todos los equipos que no están asignados a ningún robot y tienen una licencia válida.
    Cumple con las reglas de negocio BR-05 y BR-06.
    """
    query = """
        SELECT EquipoId, Equipo FROM dbo.Equipos
        WHERE 
            Activo_SAM = 1 
            AND Licencia IN ('ATTENDEDRUNTIME', 'RUNTIME')
            AND EquipoId NOT IN (
                SELECT EquipoId FROM dbo.Asignaciones WHERE EquipoId IS NOT NULL
            )
        ORDER BY Equipo
    """
    return db.ejecutar_consulta(query, es_select=True)


# Programaciones
def get_all_schedules(db: DatabaseConnector) -> List[Dict]:
    query = "EXEC dbo.ListarProgramaciones"
    schedules = db.ejecutar_consulta(query, es_select=True)
    for schedule in schedules:
        equipos_str = schedule.pop("EquiposProgramados", "")
        schedule["Equipos"] = [{"Equipo": name.strip()} for name in equipos_str.split(",")] if equipos_str else []
    return schedules


def get_robot_schedules(db: DatabaseConnector, robot_id: int) -> List[Dict]:
    query = "EXEC dbo.ListarProgramacionesPorRobot @RobotId = ?"
    schedules = db.ejecutar_consulta(query, (robot_id,), es_select=True)
    for schedule in schedules:
        equipos_str = schedule.pop("EquiposProgramados", "")
        schedule["Equipos"] = [{"Equipo": name.strip()} for name in equipos_str.split(",")] if equipos_str else []
    return schedules


def delete_schedule(db: DatabaseConnector, programacion_id: int, robot_id: int):
    # RFR-25: Se utiliza el Stored Procedure para una eliminación segura.
    query = "EXEC dbo.EliminarProgramacionCompleta @ProgramacionId = ?, @RobotId = ?"
    db.ejecutar_consulta(query, (programacion_id, robot_id), es_select=False)


def create_schedule(db: DatabaseConnector, data: ScheduleData):
    # RFR-25: Se implementa la función para llamar al SP unificado.
    robot_nombre_result = db.ejecutar_consulta(
        "SELECT Robot FROM dbo.Robots WHERE RobotId = ?", (data.RobotId,), es_select=True
    )
    if not robot_nombre_result:
        raise ValueError(f"No se encontró un robot con el ID {data.RobotId}")
    robot_str = robot_nombre_result[0]["Robot"]

    equipos_str = ""
    if data.Equipos:
        placeholders = ",".join("?" for _ in data.Equipos)
        equipos_nombres_result = db.ejecutar_consulta(
            f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
            tuple(data.Equipos),
            es_select=True,
        )
        if equipos_nombres_result and equipos_nombres_result[0]["Nombres"]:
            equipos_str = equipos_nombres_result[0]["Nombres"]

    query = "EXEC dbo.CrearProgramacion @Robot=?, @Equipos=?, @TipoProgramacion=?, @HoraInicio=?, @Tolerancia=?, @DiasSemana=?, @DiaDelMes=?, @FechaEspecifica=?"
    params = (
        robot_str,
        equipos_str,
        data.TipoProgramacion,
        data.HoraInicio,
        data.Tolerancia,
        data.DiasSemana,
        data.DiaDelMes,
        data.FechaEspecifica,
    )
    db.ejecutar_consulta(query, params, es_select=False)


def update_schedule(db: DatabaseConnector, schedule_id: int, data: ScheduleData):
    # RFR-25: Se implementa la función para llamar al SP de actualización.
    equipos_str = ""
    if data.Equipos:
        placeholders = ",".join("?" for _ in data.Equipos)
        equipos_nombres_result = db.ejecutar_consulta(
            f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
            tuple(data.Equipos),
            es_select=True,
        )
        if equipos_nombres_result and equipos_nombres_result[0]["Nombres"]:
            equipos_str = equipos_nombres_result[0]["Nombres"]

    query = "EXEC dbo.ActualizarProgramacionCompleta @ProgramacionId=?, @RobotId=?, @TipoProgramacion=?, @HoraInicio=?, @DiaSemana=?, @DiaDelMes=?, @FechaEspecifica=?, @Tolerancia=?, @Equipos=?"
    params = (
        schedule_id,
        data.RobotId,
        data.TipoProgramacion,
        data.HoraInicio,
        data.DiasSemana,
        data.DiaDelMes,
        data.FechaEspecifica,
        data.Tolerancia,
        equipos_str,
    )
    db.ejecutar_consulta(query, params, es_select=False)


# Pool
def get_pools(db: DatabaseConnector) -> List[Dict]:
    sql = "EXEC dbo.ListarPools"
    try:
        return db.ejecutar_consulta(sql, es_select=True)
    except Exception:
        raise


def create_pool(db: DatabaseConnector, nombre: str, descripcion: Optional[str]) -> Dict:
    sql = "EXEC dbo.CrearPool @Nombre = ?, @Descripcion = ?"
    params = (nombre, descripcion)
    try:
        new_pool_list = db.ejecutar_consulta(sql, params, es_select=True)
        if not new_pool_list:
            raise Exception("El Stored Procedure no devolvió el nuevo pool.")
        new_pool = new_pool_list[0]
        new_pool["CantidadRobots"] = 0
        new_pool["CantidadEquipos"] = 0
        return new_pool
    except Exception as e:
        raise


def update_pool(db: DatabaseConnector, pool_id: int, nombre: str, descripcion: Optional[str]):
    sql = "EXEC dbo.ActualizarPool @PoolId = ?, @Nombre = ?, @Descripcion = ?"
    params = (pool_id, nombre, descripcion)
    try:
        db.ejecutar_consulta(sql, params, es_select=False)
    except Exception as e:
        raise e


def delete_pool(db: DatabaseConnector, pool_id: int):
    sql = "EXEC dbo.EliminarPool @PoolId = ?"
    try:
        db.ejecutar_consulta(sql, (pool_id,), es_select=False)
    except Exception as e:
        raise e


def get_pool_assignments_and_available_resources(db: DatabaseConnector, pool_id: int) -> Dict:
    sql = "EXEC dbo.ObtenerRecursosParaPool @PoolId = ?"
    params = (pool_id,)
    assigned, available = [], []
    try:
        with db.obtener_cursor() as cursor:
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                assigned.append(dict(zip(columns, row)))
            if cursor.nextset():
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    available.append(dict(zip(columns, row)))
        return {"assigned": assigned, "available": available}
    except Exception as e:
        raise e


def assign_resources_to_pool(db: DatabaseConnector, pool_id: int, robot_ids: List[int], equipo_ids: List[int]):
    robots_tvp = [(robot_id,) for robot_id in robot_ids]
    equipos_tvp = [(equipo_id,) for equipo_id in equipo_ids]
    sql = "EXEC dbo.AsignarRecursosAPool @PoolId = ?, @RobotIds = ?, @EquipoIds = ?"
    params = (pool_id, robots_tvp, equipos_tvp)
    try:
        db.ejecutar_consulta(sql, params, es_select=False, es_tvp=True)
    except Exception as e:
        raise e


# Sincronización con A360
async def sync_with_a360(db: DatabaseConnector) -> Dict:
    """
    Orquesta la sincronización de las tablas Robots y Equipos con A360
    utilizando el nuevo componente centralizado.
    """
    logger.info("Iniciando la sincronización con A360 desde el servicio WEB...")
    try:
        aa_config = ConfigManager.get_aa_config()
        # Se crea el cliente de A360 como siempre
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_config["url_cr"],
            username=aa_config["usuario"],
            password=aa_config.get("pwd"),
            api_key=aa_config.get("api_key"),
        )
        # Se instancia el sincronizador común, inyectando las dependencias
        sincronizador = SincronizadorComun(db_connector=db, aa_client=aa_client)

        # Se ejecuta la lógica centralizada
        summary = await sincronizador.sincronizar_entidades()

        # Se asegura el cierre del cliente http
        await aa_client.close()

        return summary
    except Exception as e:
        logger.critical(f"Error fatal durante la sincronización web: {type(e).__name__} - {e}", exc_info=True)
        raise
