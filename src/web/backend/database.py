# Agrega estas importaciones al inicio del archivo database.py
import asyncio
import logging
from typing import Dict, List, Optional

from common.clients.aa_client import AutomationAnywhereClient
from common.database.sql_client import DatabaseConnector
from common.utils.config_manager import ConfigManager

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


def update_asignaciones_robot(db: DatabaseConnector, robot_id: int, assign_ids: List[int], unassign_ids: List[int]) -> Dict:
    robot_info = db.ejecutar_consulta("SELECT EsOnline FROM dbo.Robots WHERE RobotId = ?", (robot_id,), es_select=True)
    if not robot_info:
        raise ValueError("Robot no encontrado")

    return db.actualizar_asignaciones_robot(robot_id, assign_ids, unassign_ids)


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
def get_schedules_for_robot(db: DatabaseConnector, robot_id: int) -> List[Dict]:
    query_schedules = "SELECT * FROM dbo.Programaciones WHERE RobotId = ? ORDER BY HoraInicio"
    schedules = db.ejecutar_consulta(query_schedules, (robot_id,), es_select=True)

    if not schedules:
        return []

    schedule_ids = [s["ProgramacionId"] for s in schedules]
    placeholders = ",".join("?" for _ in schedule_ids)

    query_teams = f"""
        SELECT a.ProgramacionId, e.EquipoId, e.Equipo
        FROM dbo.Asignaciones a
        JOIN dbo.Equipos e ON a.EquipoId = e.EquipoId
        WHERE a.ProgramacionId IN ({placeholders}) AND a.EsProgramado = 1
    """
    team_assignments = db.ejecutar_consulta(query_teams, tuple(schedule_ids), es_select=True)

    teams_map = {}
    for assignment in team_assignments:
        pid = assignment["ProgramacionId"]
        if pid not in teams_map:
            teams_map[pid] = []
        teams_map[pid].append({"EquipoId": assignment["EquipoId"], "Equipo": assignment["Equipo"]})

    for schedule in schedules:
        schedule["Equipos"] = teams_map.get(schedule["ProgramacionId"], [])

    return schedules


def delete_schedule_full(db: DatabaseConnector, programacion_id: int, robot_id: int):
    query = "EXEC dbo.EliminarProgramacionCompleta @ProgramacionId = ?, @RobotId = ?"
    db.ejecutar_consulta(query, (programacion_id, robot_id), es_select=False)


def create_new_schedule(db: DatabaseConnector, data: ScheduleData):
    """
    Crea una nueva programación llamando al Stored Procedure unificado y eficiente
    'CrearProgramacion'.
    """
    # 1. Obtener los nombres de los equipos a partir de sus IDs.
    #    STRING_AGG es una forma eficiente de hacer esto en la BD.
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

    # 2. Obtener el nombre del robot a partir de su ID.
    robot_nombre_result = db.ejecutar_consulta("SELECT Robot FROM dbo.Robots WHERE RobotId = ?", (data.RobotId,), es_select=True)
    if not robot_nombre_result:
        raise ValueError(f"No se encontró un robot con el ID {data.RobotId}")
    robot_str = robot_nombre_result[0]["Robot"]

    # 3. Preparar los parámetros para el SP 'CrearProgramacion'.
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

    # 4. Ejecutar el Stored Procedure.
    db.ejecutar_consulta(query, params, es_select=False)


def create_new_schedule_old(db: DatabaseConnector, data: ScheduleData):
    equipos_nombres_result = db.ejecutar_consulta(
        f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({','.join('?' for _ in data.Equipos)})",
        tuple(data.Equipos),
        es_select=True,
    )
    equipos_str = equipos_nombres_result[0]["Nombres"] if equipos_nombres_result and equipos_nombres_result[0]["Nombres"] else ""

    robot_nombre_result = db.ejecutar_consulta("SELECT Robot FROM dbo.Robots WHERE RobotId = ?", (data.RobotId,), es_select=True)
    robot_str = robot_nombre_result[0]["Robot"] if robot_nombre_result else ""

    sp_map = {
        "Diaria": ("dbo.CargarProgramacionDiaria", ["@Robot", "@Equipos", "@HoraInicio", "@Tolerancia"]),
        "Semanal": ("dbo.CargarProgramacionSemanal", ["@Robot", "@Equipos", "@DiasSemana", "@HoraInicio", "@Tolerancia"]),
        "Mensual": ("dbo.CargarProgramacionMensual", ["@Robot", "@Equipos", "@DiaDelMes", "@HoraInicio", "@Tolerancia"]),
        "Especifica": ("dbo.CargarProgramacionEspecifica", ["@Robot", "@Equipos", "@FechaEspecifica", "@HoraInicio", "@Tolerancia"]),
    }
    if data.TipoProgramacion not in sp_map:
        raise ValueError("Tipo de programación no válido")

    sp_name, sp_param_names = sp_map[data.TipoProgramacion]
    params_dict = {
        "@Robot": robot_str,
        "@Equipos": equipos_str,
        "@HoraInicio": data.HoraInicio,
        "@Tolerancia": data.Tolerancia,
        "@DiasSemana": data.DiasSemana,
        "@DiaDelMes": data.DiaDelMes,
        "@FechaEspecifica": data.FechaEspecifica,
    }

    params_tuple = tuple(params_dict[p] for p in sp_param_names)
    placeholders = ", ".join("?" for _ in params_tuple)
    query = f"EXEC {sp_name} {placeholders}"

    db.ejecutar_consulta(query, params_tuple, es_select=False)


def update_existing_schedule(db: DatabaseConnector, programacion_id: int, data: ScheduleData):
    equipos_str = ""
    if data.Equipos:
        placeholders = ",".join("?" for _ in data.Equipos)
        equipos_nombres_result = db.ejecutar_consulta(
            f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
            tuple(data.Equipos),
            es_select=True,
        )
        equipos_str = equipos_nombres_result[0]["Nombres"] if equipos_nombres_result and equipos_nombres_result[0]["Nombres"] else ""

    query = "EXEC dbo.ActualizarProgramacionCompleta ?, ?, ?, ?, ?, ?, ?, ?, ?"
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
    """
    Obtiene la lista de todos los pools de recursos llamando al SP dbo.ListarPools.
    """
    sql = "EXEC dbo.ListarPools"
    try:
        pools = db.ejecutar_consulta(sql, es_select=True)
        return pools
    except Exception as e:
        raise


def create_pool(db: DatabaseConnector, nombre: str, descripcion: Optional[str]) -> Dict:
    """
    Crea un nuevo pool llamando al SP dbo.CrearPool.
    """
    sql = "EXEC dbo.CrearPool @Nombre = ?, @Descripcion = ?"
    params = (nombre, descripcion)
    try:
        new_pool_list = db.ejecutar_consulta(sql, params, es_select=True)
        if not new_pool_list:
            raise Exception("El Stored Procedure no devolvió el nuevo pool.")
        new_pool = new_pool_list[0]
        # Añadimos los contadores por defecto para consistencia con get_pools
        new_pool["CantidadRobots"] = 0
        new_pool["CantidadEquipos"] = 0
        return new_pool
    except Exception as e:
        # Re-lanzamos la excepción para que la capa de API la maneje
        raise


def update_pool(db: DatabaseConnector, pool_id: int, nombre: str, descripcion: Optional[str]):
    """
    Actualiza un pool existente llamando al SP dbo.ActualizarPool.
    El SP se encarga de la lógica y de lanzar errores si algo falla.
    """
    sql = "EXEC dbo.ActualizarPool @PoolId = ?, @Nombre = ?, @Descripcion = ?"
    params = (pool_id, nombre, descripcion)
    try:
        db.ejecutar_consulta(sql, params, es_select=False)
    except Exception as e:
        raise e


def delete_pool(db: DatabaseConnector, pool_id: int):
    """
    Elimina un pool existente llamando al SP dbo.EliminarPool.
    """
    sql = "EXEC dbo.EliminarPool @PoolId = ?"
    try:
        db.ejecutar_consulta(sql, (pool_id,), es_select=False)
    except Exception as e:
        raise e


def get_pool_assignments_and_available_resources(db: DatabaseConnector, pool_id: int) -> Dict:
    """
    Obtiene los recursos (robots/equipos) asignados a un pool y los que están disponibles.
    Utiliza un SP que devuelve dos conjuntos de resultados.
    """
    sql = "EXEC dbo.ObtenerRecursosParaPool @PoolId = ?"
    params = (pool_id,)

    assigned = []
    available = []

    try:
        with db.obtener_cursor() as cursor:
            cursor.execute(sql, params)

            # Procesar el primer conjunto de resultados (asignados)
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                assigned.append(dict(zip(columns, row)))

            # Mover al siguiente conjunto de resultados (disponibles)
            if cursor.nextset():
                columns = [column[0] for column in cursor.description]
                for row in cursor.fetchall():
                    available.append(dict(zip(columns, row)))

        return {"assigned": assigned, "available": available}

    except Exception as e:
        raise e


def assign_resources_to_pool(db: DatabaseConnector, pool_id: int, robot_ids: List[int], team_ids: List[int]):
    """
    Llama al SP para asignar recursos a un pool usando TVPs.
    """
    # pyodbc espera una lista de tuplas para los TVP
    robots_tvp = [(robot_id,) for robot_id in robot_ids]
    equipos_tvp = [(team_id,) for team_id in team_ids]

    sql = "EXEC dbo.AsignarRecursosAPool @PoolId = ?, @RobotIds = ?, @EquipoIds = ?"
    params = (pool_id, robots_tvp, equipos_tvp)

    try:
        db.ejecutar_consulta(sql, params, es_select=False)
    except Exception as e:
        raise e


# Sincronización con A360
async def sync_with_a360(db: DatabaseConnector) -> Dict:
    """
    Orquesta la sincronización de las tablas Robots y Equipos con A360.
    """
    print("Iniciando la sincronización con A360...")

    try:
        # --- BLOQUE 1: Llamadas a la API de Automation Anywhere ---
        print("Paso 1: Conectando con Automation Anywhere y obteniendo datos...")
        aa_config = ConfigManager.get_aa_config()
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_config["url_cr"],
            username=aa_config["usuario"],
            password=aa_config.get("pwd"),  # Usar .get() para la contraseña opcional
            **aa_config,  # Pasar el resto de la configuración
        )

        devices_task = aa_client.obtener_devices()
        users_task = aa_client.obtener_usuarios_detallados()
        robots_task = aa_client.obtener_robots()

        devices_list, users_list, robots_list = await asyncio.gather(devices_task, users_task, robots_task)
        print(f"Paso 2: Datos recibidos de A360. Robots: {len(robots_list)}, Dispositivos: {len(devices_list)}, Usuarios: {len(users_list)}")

        # --- BLOQUE 2: Procesamiento de datos ---
        print("Paso 3: Procesando y cruzando datos...")
        users_by_id = {user["UserId"]: user for user in users_list if isinstance(user, dict) and isinstance(user.get("UserId"), (int, str))}

        equipos_procesados = []
        for device in devices_list:
            user_id = device.get("UserId")
            if user_id in users_by_id:
                device["Licencia"] = users_by_id[user_id].get("Licencia")
            equipos_procesados.append(device)

        # La API de A360 puede devolver duplicados. Los eliminamos antes de enviar a la BD.
        equipos_unicos = {}
        for equipo in equipos_procesados:
            equipo_id = equipo.get("EquipoId")
            if equipo_id:
                if equipo_id in equipos_unicos:
                    logger.warning(f"Se encontró un EquipoId duplicado de la API de A360 y se ha eliminado: ID = {equipo_id}")
                equipos_unicos[equipo_id] = equipo

        equipos_finales = list(equipos_unicos.values())

        # --- BLOQUE 3: Actualización de la Base de Datos ---
        print(f"Paso 4: Actualizando la base de datos con {len(robots_list)} robots y {len(equipos_finales)} equipos...")
        db.merge_equipos(equipos_finales)
        db.merge_robots(robots_list)

        print("Paso 5: Sincronización completada exitosamente.")

        return {
            "robots_sincronizados": len(robots_list),
            "equipos_sincronizados": len(equipos_finales),
        }

    except Exception as e:
        # --- CAPTURA DE ERROR DETALLADA ---
        print(f"ERROR FATAL DURANTE LA SINCRONIZACIÓN: {type(e).__name__} - {e}")
        import traceback

        traceback.print_exc()
        # Relanzamos la excepción para que FastAPI devuelva el 500, pero ya habremos visto el detalle.
        raise e
