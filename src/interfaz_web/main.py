# src/interfaz_web/main.py
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel
from reactpy import component, html, use_state
from reactpy.backend.fastapi import Options, configure
from starlette.staticfiles import StaticFiles

from common.database.sql_client import DatabaseConnector
from common.utils.config_manager import ConfigManager

from .components.dashboard import RobotDashboard
from .components.layout import AppLayout
from .components.notifications import NotificationContext, ToastContainer

CURRENT_DIR = Path(__file__).parent
app = FastAPI()

# ===== CONFIGURACIÓN DE BASE DE DATOS (se mantiene igual) =====
db_config = ConfigManager.get_sql_server_config("SQL_SAM")
db_connector = DatabaseConnector(
    servidor=db_config.get("server"), base_datos=db_config.get("database"), usuario=db_config.get("uid"), contrasena=db_config.get("pwd")
)


# -- modelos de datos --
class RobotCreateRequest(BaseModel):
    """Modelo para crear un robot, requiere RobotId."""

    RobotId: int
    Robot: str
    Descripcion: Optional[str] = None
    Activo: bool
    EsOnline: bool
    MinEquipos: int = -1
    MaxEquipos: int = 1
    PrioridadBalanceo: int = 100
    TicketsPorEquipoAdicional: Optional[int] = None


class RobotUpdateRequest(BaseModel):
    """Modelo de datos para la actualización de un robot."""

    Robot: str
    Descripcion: Optional[str] = None
    MinEquipos: int
    MaxEquipos: int
    PrioridadBalanceo: int
    TicketsPorEquipoAdicional: Optional[int] = None


class AssignmentUpdateRequest(BaseModel):
    """Modelo de datos para la actualización de un asignaciones."""

    assign_team_ids: List[int]
    unassign_team_ids: List[int]


class ScheduleData(BaseModel):
    RobotId: int
    TipoProgramacion: str
    HoraInicio: str
    Tolerancia: int
    Equipos: List[int]  # Lista de EquipoId
    DiasSemana: Optional[str] = None
    DiaDelMes: Optional[int] = None
    FechaEspecifica: Optional[str] = None


# ===== API ENDPOINTS (se mantienen igual, sin 'async') =====
# -- Robots --
@app.get("/api/robots")
def get_robots_with_assignments(
    # Parámetros de filtrado
    name: Optional[str] = None,
    active: Optional[bool] = None,
    online: Optional[bool] = None,
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(20, ge=1, le=100, description="Tamaño de la página"),
    sort_by: Optional[str] = Query("Robot", description="Columna por la cual ordenar"),
    sort_dir: Optional[str] = Query("asc", description="Dirección de ordenación (asc o desc)"),
):
    # --- LÓGICA DE ORDENACIÓN SEGURA ---
    sortable_columns = {
        "Robot": "r.Robot",
        "CantidadEquiposAsignados": "ISNULL(ea.Equipos, 0)",
        "Activo": "r.Activo",
        "EsOnline": "r.EsOnline",
        "TieneProgramacion": "(CASE WHEN EXISTS (SELECT 1 FROM dbo.Programaciones p WHERE p.RobotId = r.RobotId AND p.Activo = 1) THEN 1 ELSE 0 END)",
        "PrioridadBalanceo": "r.PrioridadBalanceo",
        "TicketsPorEquipoAdicional": "r.TicketsPorEquipoAdicional",
    }
    # Validamos para evitar inyección SQL
    order_by_column = sortable_columns.get(sort_by, "r.Robot")
    order_by_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    # --- LÓGICA DE PAGINACIÓN Y FILTROS MEJORADA ---
    # Partes reutilizables de la consulta
    select_from_clause = """
        FROM dbo.Robots r
        LEFT JOIN dbo.EquiposAsignados ea ON r.Robot = ea.Robot
    """
    conditions = []
    params = []

    if name:
        conditions.append("r.Robot LIKE ?")
        params.append(f"%{name}%")
    if active is not None:
        conditions.append("r.Activo = ?")
        params.append(active)
    if online is not None:
        conditions.append("r.EsOnline = ?")
        params.append(online)

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    try:
        # 1. PRIMERA CONSULTA: Obtener el conteo total de filas que coinciden con los filtros
        count_query = f"SELECT COUNT(*) as total_count {select_from_clause} {where_clause}"
        total_count_result = db_connector.ejecutar_consulta(count_query, tuple(params), es_select=True)
        total_count = total_count_result[0]["total_count"] if total_count_result else 0

        # 2. SEGUNDA CONSULTA: Obtener la página de datos solicitada

        # Calcular el OFFSET
        offset = (page - 1) * size

        main_query = f"""
            SELECT
                r.RobotId, r.Robot, r.Descripcion, r.MinEquipos, r.MaxEquipos,
                r.EsOnline, r.Activo, r.PrioridadBalanceo,
                r.TicketsPorEquipoAdicional, ISNULL(ea.Equipos, 0) as CantidadEquiposAsignados
            {select_from_clause}
            {where_clause}
            ORDER BY r.Robot
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        # --- CONSULTA PRINCIPAL CON ORDENACIÓN DINÁMICA ---
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
            ORDER BY {order_by_column} {order_by_direction} -- Se añade la cláusula ORDER BY
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """

        pagination_params = params + [offset, size]
        robots_data = db_connector.ejecutar_consulta(main_query, tuple(pagination_params), es_select=True)
        return {"total_count": total_count, "page": page, "size": size, "robots": robots_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener robots: {str(e)}")


@app.patch("/api/robots/{robot_id}")
def update_robot_status(robot_id: int, updates: Dict[str, bool] = Body(...)):
    field_to_update = next(iter(updates))
    if field_to_update not in ["Activo", "EsOnline"]:
        raise HTTPException(status_code=400, detail="Campo no válido")
    new_value = updates[field_to_update]
    query = f"UPDATE dbo.Robots SET {field_to_update} = ? WHERE RobotId = ?"
    params = (new_value, robot_id)
    try:
        rows_affected = db_connector.ejecutar_consulta(query, params, es_select=False)
        if rows_affected > 0:
            return {"message": "Actualizado"}
        else:
            raise HTTPException(status_code=404, detail="Robot no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/robots/{robot_id}")
def update_robot_details(robot_id: int, robot_data: RobotUpdateRequest):
    """Endpoint para actualizar todas las propiedades de un robot."""
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
    try:
        rows_affected = db_connector.ejecutar_consulta(query, params, es_select=False)
        if rows_affected > 0:
            return {"message": f"Robot {robot_id} actualizado con éxito."}
        else:
            raise HTTPException(status_code=404, detail="Robot no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/robots/{robot_id}", status_code=204)
def delete_robot(robot_id: int):
    """
    Elimina un robot y sus asignaciones asociadas.
    """
    try:
        # Primero, eliminar asignaciones para evitar conflictos de clave externa
        db_connector.ejecutar_consulta("DELETE FROM dbo.Asignaciones WHERE RobotId = ?", (robot_id,), es_select=False)
        # Luego, eliminar el robot
        rows_affected = db_connector.ejecutar_consulta("DELETE FROM dbo.Robots WHERE RobotId = ?", (robot_id,), es_select=False)
        if rows_affected == 0:
            raise HTTPException(status_code=404, detail="Robot no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar el robot: {str(e)}")


@app.post("/api/robots", status_code=201)
def create_robot(robot_data: RobotCreateRequest):
    """
    Crea un nuevo robot en la base de datos.
    Devuelve el robot recién creado, incluyendo su nuevo ID.
    """
    query = """
        INSERT INTO dbo.Robots (RobotId, Robot, Descripcion, MinEquipos, MaxEquipos, PrioridadBalanceo, TicketsPorEquipoAdicional)
        OUTPUT INSERTED.*
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    params = (
        robot_data.RobotId,  # <-- Usa el ID del request
        robot_data.Robot,
        robot_data.Descripcion,
        robot_data.MinEquipos,
        robot_data.MaxEquipos,
        robot_data.PrioridadBalanceo,
        robot_data.TicketsPorEquipoAdicional,
    )
    try:
        new_robot = db_connector.ejecutar_consulta(query, params, es_select=True)
        if not new_robot:
            raise HTTPException(status_code=500, detail="No se pudo crear el robot.")
        return new_robot[0]
    except Exception as e:
        # Captura errores de Llave Primaria Duplicada
        if "Violation of PRIMARY KEY constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"El RobotId {robot_data.RobotId} ya existe.")
        raise


# -- Asignaciones --
@app.get("/api/robots/{robot_id}/asignaciones")
def get_robot_asignaciones(robot_id: int):
    """
    Obtiene la lista de equipos asignados a un robot específico.
    Utiliza la vista AsignacionesView para obtener los nombres y estados.
    """
    # Esta vista ya une las tablas Asignaciones, Equipos y Robots.
    query = """
        SELECT
            A.RobotId,
            A.EquipoId,
            A.Equipo,
            A.EsProgramado,
            A.Reservado
        FROM
            dbo.AsignacionesView AS A
        WHERE
            A.RobotId = ?
    """
    try:
        return db_connector.ejecutar_consulta(query, (robot_id,), es_select=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener asignaciones: {str(e)}")


@app.get("/api/equipos/disponibles/{robot_id}")
def get_available_teams(robot_id: int):
    """
    Obtiene la lista de equipos disponibles, EXCLUYENDO los que ya
    están asignados al robot_id actual.
    """
    query = """
        SELECT EquipoId, Equipo FROM dbo.Equipos
        WHERE Activo_SAM = 1 AND PermiteBalanceoDinamico = 1
        AND EquipoId NOT IN (
            SELECT EquipoId FROM dbo.Asignaciones WHERE RobotId = ?
        )
    """
    try:
        # Pasamos el robot_id como parámetro a la consulta
        return db_connector.ejecutar_consulta(query, (robot_id,), es_select=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/robots/{robot_id}/asignaciones")
def update_robot_asignaciones(robot_id: int, update_data: AssignmentUpdateRequest):
    """
    Endpoint para aplicar los cambios de asignación y desasignación.
    """
    try:
        # Necesitamos saber si el robot es online para marcar las asignaciones como 'Reservado'
        robot_info = db_connector.ejecutar_consulta("SELECT EsOnline FROM dbo.Robots WHERE RobotId = ?", (robot_id,), es_select=True)
        if not robot_info:
            raise HTTPException(status_code=404, detail="Robot no encontrado")

        es_online = robot_info[0].get("EsOnline", False)

        # Usamos el nuevo método transaccional del cliente SQL
        return db_connector.actualizar_asignaciones_robot(robot_id, update_data.assign_team_ids, update_data.unassign_team_ids)
        # return db_connector.actualizar_asignaciones_robot_old(robot_id, es_online, update_data.assign_team_ids, update_data.unassign_team_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar asignaciones: {str(e)}")


@app.get("/api/robots/{robot_id}/programaciones")
def get_robot_schedules(robot_id: int):
    """
    Versión robusta para obtener programaciones y sus equipos asignados de forma estructurada.
    """
    try:
        # 1. Obtener todas las programaciones para el robot
        query_schedules = "SELECT * FROM dbo.Programaciones WHERE RobotId = ? ORDER BY HoraInicio"
        schedules = db_connector.ejecutar_consulta(query_schedules, (robot_id,), es_select=True)

        if schedules:
            schedule_ids = [s["ProgramacionId"] for s in schedules]
            placeholders = ",".join("?" for _ in schedule_ids)

            # --- Obtenemos ID y Nombre del equipo ---
            query_teams = f"""
                SELECT a.ProgramacionId, e.EquipoId, e.Equipo
                FROM dbo.Asignaciones a
                JOIN dbo.Equipos e ON a.EquipoId = e.EquipoId
                WHERE a.ProgramacionId IN ({placeholders}) AND a.EsProgramado = 1
            """
            team_assignments = db_connector.ejecutar_consulta(query_teams, tuple(schedule_ids), es_select=True)

            teams_map = {}
            for assignment in team_assignments:
                pid = assignment["ProgramacionId"]
                if pid not in teams_map:
                    teams_map[pid] = []
                # --- Guardamos el objeto completo del equipo ---
                teams_map[pid].append({"EquipoId": assignment["EquipoId"], "Equipo": assignment["Equipo"]})

            for schedule in schedules:
                # --- Asignamos la lista de objetos, no un string ---
                schedule["Equipos"] = teams_map.get(schedule["ProgramacionId"], [])

        return schedules
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener programaciones: {str(e)}")


@app.delete("/api/robots/{robot_id}/programaciones/{programacion_id}", status_code=204)
def delete_schedule(robot_id: int, programacion_id: int):
    """
    Llama al Stored Procedure robusto para eliminar una programación y limpiar sus asignaciones.
    """
    try:
        query = "EXEC dbo.EliminarProgramacionCompleta @ProgramacionId = ?, @RobotId = ?"
        db_connector.ejecutar_consulta(query, (programacion_id, robot_id), es_select=False)
        # No se devuelve contenido en un DELETE exitoso (código 204)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la programación: {str(e)}")


@app.post("/api/programaciones")
def create_schedule(data: ScheduleData):
    """
    Crea una nueva programación. Llama al Stored Procedure correspondiente
    según el TipoProgramacion.
    """
    # El SP necesita los nombres de los equipos como un string separado por comas
    equipos_nombres_result = db_connector.ejecutar_consulta(
        f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({','.join('?' for _ in data.Equipos)})",
        tuple(data.Equipos),
        es_select=True,
    )
    equipos_str = equipos_nombres_result[0]["Nombres"] if equipos_nombres_result and equipos_nombres_result[0]["Nombres"] else ""

    robot_nombre_result = db_connector.ejecutar_consulta("SELECT Robot FROM dbo.Robots WHERE RobotId = ?", (data.RobotId,), es_select=True)
    robot_str = robot_nombre_result[0]["Robot"] if robot_nombre_result else ""
    # Mapeo de SP a sus parámetros requeridos
    sp_map = {
        "Diaria": ("dbo.CargarProgramacionDiaria", ["@Robot", "@Equipos", "@HoraInicio", "@Tolerancia"]),
        "Semanal": ("dbo.CargarProgramacionSemanal", ["@Robot", "@Equipos", "@DiasSemana", "@HoraInicio", "@Tolerancia"]),
        "Mensual": ("dbo.CargarProgramacionMensual", ["@Robot", "@Equipos", "@DiaDelMes", "@HoraInicio", "@Tolerancia"]),
        "Especifica": ("dbo.CargarProgramacionEspecifica", ["@Robot", "@Equipos", "@FechaEspecifica", "@HoraInicio", "@Tolerancia"]),
    }
    if data.TipoProgramacion not in sp_map:
        raise HTTPException(status_code=400, detail="Tipo de programación no válido")

    sp_name, sp_param_names = sp_map[data.TipoProgramacion]
    # Construcción dinámica de parámetros para el SP
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

    # Construcción de la llamada al SP
    placeholders = ", ".join("?" for _ in params_tuple)
    query = f"EXEC {sp_name} {placeholders}"

    try:
        db_connector.ejecutar_consulta(query, params_tuple, es_select=False)
        return {"message": "Programación creada con éxito."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la programación: {str(e)}")


@app.put("/api/programaciones/{programacion_id}")
def update_schedule(programacion_id: int, data: ScheduleData):
    """
    Actualiza una programación existente usando el SP ActualizarProgramacionCompleta.
    """
    try:
        equipos_str = ""
        if data.Equipos:
            # Obtenemos los nombres de los equipos como un string separado por comas
            placeholders = ",".join("?" for _ in data.Equipos)
            equipos_nombres_result = db_connector.ejecutar_consulta(
                f"SELECT STRING_AGG(Equipo, ',') AS Nombres FROM dbo.Equipos WHERE EquipoId IN ({placeholders})",
                tuple(data.Equipos),
                es_select=True,
            )
            equipos_str = equipos_nombres_result[0]["Nombres"] if equipos_nombres_result and equipos_nombres_result[0]["Nombres"] else ""

        # --- CORRECCIÓN: Llamada al SP sin nombrar los parámetros ---
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

        db_connector.ejecutar_consulta(query, params, es_select=False)
        return {"message": "Programación actualizada con éxito"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la programación: {str(e)}")


@component
def App():
    notifications, set_notifications = use_state([])

    def show_notification(message, style="success"):
        new_id = str(uuid.uuid4())
        set_notifications(lambda old: old + [{"id": new_id, "message": message, "style": style}])

    def dismiss_notification(notification_id):
        set_notifications(lambda old: [n for n in old if n["id"] != notification_id])

    context_value = {"notifications": notifications, "show_notification": show_notification, "dismiss_notification": dismiss_notification}

    return NotificationContext(
        AppLayout(RobotDashboard()),
        ToastContainer(),
        value=context_value,
    )


# --- Elementos que inyectaremos en el <head> de la página ---
# Aquí definimos todos nuestros estilos y scripts externos
head = html.head(
    html.title("SAM"),
    html.meta({"charset": "utf-8"}),
    html.meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
    # --- CORRECCIÓN: Rutas locales ---
    # html.link({"rel": "stylesheet", "href": "/static/css/bulma.min.css"}), # tema oscuro
    html.link({"rel": "stylesheet", "href": "/static/css/bulma-no-dark-mode.css"}),  # Tema claro
    html.link({"rel": "stylesheet", "href": "/static/css/bulma-switch.min.css"}),
    html.link({"rel": "stylesheet", "href": "/static/css/all.min.css"}),  # Font Awesome
    html.link({"rel": "stylesheet", "href": "/static/custom.css"}),
)

# --- Montamos la carpeta 'static' para que /static/custom.css sea accesible ---
# Esta línea es importante y se queda.
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# --- Le decimos a ReactPy que configure la app, pasando nuestro <head> personalizado ---
# ReactPy se encargará de la ruta raíz ("/") y de servir su propio JS.
configure(
    app,
    App,
    options=Options(head=head),
)
