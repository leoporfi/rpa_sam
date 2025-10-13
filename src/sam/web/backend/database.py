# Agrega estas importaciones al inicio del archivo database.py
import asyncio
import logging
from typing import Dict, List, Optional

from sam.common.a360_client import AutomationAnywhereClient
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector

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

    # Adaptado para que la lógica de negocio resida en el SP
    assign_tvp = [(id,) for id in assign_ids]
    unassign_tvp = [(id,) for id in unassign_ids]

    query = "EXEC dbo.ActualizarAsignacionesManuales @RobotId=?, @EquiposAsignar=?, @EquiposDesasignar=?"
    params = (robot_id, assign_tvp, unassign_tvp)

    # Suponiendo que el SP devuelve un resultado o simplemente se ejecuta
    db.ejecutar_consulta(query, params, es_select=False)

    return {"message": "Asignaciones actualizadas correctamente."}


def get_available_teams_for_robot(db: DatabaseConnector, robot_id: int) -> List[Dict]:
    """
    Obtiene equipos que no están asignados al robot especificado.
    """
    query = """
        SELECT EquipoId, Equipo FROM dbo.Equipos
        WHERE Activo_SAM = 1 AND PermiteBalanceoDinamico = 1
        AND EquipoId NOT IN (
            SELECT EquipoId FROM dbo.Asignaciones WHERE RobotId = ?
        )
        ORDER BY Equipo
    """
    return db.ejecutar_consulta(query, (robot_id,), es_select=True)


# Programaciones
def get_all_schedules(db: DatabaseConnector) -> List[Dict]:
    """Obtiene todas las programaciones."""
    return db.ejecutar_consulta("EXEC dbo.ListarProgramaciones", es_select=True)


def get_schedules_for_robot(db: DatabaseConnector, robot_id: int) -> List[Dict]:
    """Obtiene programaciones para un robot específico."""
    query_schedules = "EXEC dbo.ListarProgramacionesPorRobot @RobotId = ?"
    return db.ejecutar_consulta(query_schedules, (robot_id,), es_select=True)


def delete_schedule_full(db: DatabaseConnector, programacion_id: int):
    """Elimina una programación y sus asignaciones asociadas."""
    # Primero, obtenemos el RobotId para pasarlo al SP, manteniendo la lógica del SP intacta
    robot_id_result = db.ejecutar_consulta(
        "SELECT RobotId FROM dbo.Programaciones WHERE ProgramacionId = ?",
        (programacion_id,),
        es_select=True,
    )
    if not robot_id_result:
        raise ValueError(f"No se encontró la programación con ID {programacion_id}")

    robot_id = robot_id_result[0]["RobotId"]
    query = "EXEC dbo.EliminarProgramacionCompleta @ProgramacionId = ?, @RobotId = ?"
    db.ejecutar_consulta(query, (programacion_id, robot_id), es_select=False)


def create_new_schedule(db: DatabaseConnector, data: ScheduleData):
    """Crea una nueva programación llamando al SP unificado."""
    equipos_str = ""
    if data.Equipos:
        placeholders = ",".join("?" for _ in data.Equipos)
        nombres_result = db.ejecutar_consulta(
            f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
            tuple(data.Equipos),
            es_select=True,
        )
        if nombres_result and nombres_result[0]["Nombres"]:
            equipos_str = nombres_result[0]["Nombres"]

    robot_nombre_result = db.ejecutar_consulta(
        "SELECT Robot FROM dbo.Robots WHERE RobotId = ?", (data.RobotId,), es_select=True
    )
    if not robot_nombre_result:
        raise ValueError(f"No se encontró un robot con el ID {data.RobotId}")
    robot_str = robot_nombre_result[0]["Robot"]

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


def update_existing_schedule(db: DatabaseConnector, programacion_id: int, data: ScheduleData):
    equipos_str = ""
    if data.Equipos:
        placeholders = ",".join("?" for _ in data.Equipos)
        equipos_nombres_result = db.ejecutar_consulta(
            f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
            tuple(data.Equipos),
            es_select=True,
        )
        equipos_str = (
            equipos_nombres_result[0]["Nombres"]
            if equipos_nombres_result and equipos_nombres_result[0]["Nombres"]
            else ""
        )

    query = "EXEC dbo.ActualizarProgramacionCompleta @ProgramacionId=?, @RobotId=?, @TipoProgramacion=?, @HoraInicio=?, @DiaSemana=?, @DiaDelMes=?, @FechaEspecifica=?, @Tolerancia=?, @Equipos=?"
    params = (
        programacion_id,
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
    """Obtiene la lista de pools llamando al SP."""
    return db.ejecutar_consulta("EXEC dbo.ListarPools", es_select=True)


def create_pool(db: DatabaseConnector, nombre: str, descripcion: Optional[str]) -> Dict:
    """Crea un nuevo pool llamando al SP."""
    sql = "EXEC dbo.CrearPool @Nombre = ?, @Descripcion = ?"
    params = (nombre, descripcion)
    new_pool_list = db.ejecutar_consulta(sql, params, es_select=True)
    if not new_pool_list:
        raise Exception("El Stored Procedure no devolvió el nuevo pool.")
    new_pool = new_pool_list[0]
    new_pool["CantidadRobots"] = 0
    new_pool["CantidadEquipos"] = 0
    return new_pool


def update_pool(db: DatabaseConnector, pool_id: int, nombre: str, descripcion: Optional[str]):
    """Actualiza un pool existente llamando al SP."""
    sql = "EXEC dbo.ActualizarPool @PoolId = ?, @Nombre = ?, @Descripcion = ?"
    params = (pool_id, nombre, descripcion)
    db.ejecutar_consulta(sql, params, es_select=False)


def delete_pool(db: DatabaseConnector, pool_id: int):
    """Elimina un pool existente llamando al SP."""
    sql = "EXEC dbo.EliminarPool @PoolId = ?"
    db.ejecutar_consulta(sql, (pool_id,), es_select=False)


def get_pool_assignments_and_available_resources(db: DatabaseConnector, pool_id: int) -> Dict:
    """Obtiene los recursos asignados y disponibles para un pool."""
    sql = "EXEC dbo.ObtenerRecursosParaPool @PoolId = ?"
    params = (pool_id,)
    assigned, available = [], []
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


def assign_resources_to_pool(db: DatabaseConnector, pool_id: int, robot_ids: List[int], equipo_ids: List[int]):
    """Llama al SP para asignar recursos a un pool usando TVPs."""
    robots_tvp = [(robot_id,) for robot_id in robot_ids]
    equipos_tvp = [(equipo_id,) for equipo_id in equipo_ids]
    sql = "EXEC dbo.AsignarRecursosAPool @PoolId = ?, @RobotIds = ?, @EquipoIds = ?"
    params = (pool_id, robots_tvp, equipos_tvp)
    db.ejecutar_consulta(sql, params, es_select=False, es_tvp=True)


# Sincronización con A360
async def sync_with_a360(db: DatabaseConnector) -> Dict:
    """
    Orquesta la sincronización de las tablas Robots y Equipos con A360.
    """
    logger.info("Iniciando la sincronización con A360...")
    try:
        aa_config = ConfigManager.get_aa_config()
        # RFR-04: Corregido el TypeError por argumentos duplicados.
        # Se pasan los argumentos explícitamente en lugar de usar **aa_config,
        # que creaba conflictos al pasar 'api_key' y otros valores dos veces.
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_config["url_cr"],
            username=aa_config["usuario"],
            password=aa_config.get("pwd"),
            api_key=aa_config.get("api_key"),
        )
        devices_task = aa_client.obtener_devices()
        users_task = aa_client.obtener_usuarios_detallados()
        robots_task = aa_client.obtener_robots()
        devices_list, users_list, robots_list = await asyncio.gather(devices_task, users_task, robots_task)
        logger.info(
            f"Datos recibidos de A360: {len(robots_list)} robots, {len(devices_list)} dispositivos, {len(users_list)} users."
        )

        users_by_id = {user["id"]: user for user in users_list if isinstance(user, dict) and "id" in user}

        equipos_procesados = []
        for device in devices_list:
            user_id = device.get("userId")
            if user_id in users_by_id:
                # El campo correcto de la licencia parece ser 'licenseFeatures'
                device["Licencia"] = ", ".join(users_by_id[user_id].get("licenseFeatures", []))
            equipos_procesados.append(device)

        # La API de A360 puede devolver duplicados. Los eliminamos antes de enviar a la BD.
        equipos_unicos = {}
        for equipo in equipos_procesados:
            equipo_id = equipo.get("id")
            if equipo_id:
                if equipo_id in equipos_unicos:
                    logger.warning(f"Se encontró un EquipoId duplicado de A360 y se ha omitido: ID = {equipo_id}")
                else:
                    equipos_unicos[equipo_id] = equipo

        equipos_finales = list(equipos_unicos.values())

        db.merge_equipos(equipos_finales)
        db.merge_robots(robots_list)
        logger.info("Sincronización con base de datos completada.")

        return {"robots_sincronizados": len(robots_list), "equipos_sincronizados": len(equipos_finales)}
    except Exception as e:
        logger.critical(f"Error fatal durante la sincronización: {type(e).__name__} - {e}", exc_info=True)
        raise
