# src/interfaz_web/components/dashboard.py

from reactpy import component, html, use_callback, use_context, use_effect, use_state

from ..hooks.use_debounced_value import use_debounced_value
from ..hooks.use_robots import use_robots
from .notifications import NotificationContext
from .assignments_modal import AssignmentsModal
from .common.confirmation_modal import ConfirmationModal
from .common.loading_spinner import LoadingSpinner
from .common.pagination import Pagination
from .robot_filters import RobotFilters as RobotFiltersComponent
from .robot_modal import RobotEditModal
from .robot_table import RobotTable
from .schedules_modal import SchedulesModal


@component
def RobotDashboard():
    # ESTADO Y LÓGICA DE DATOS (SIN CAMBIOS)
    robots_state = use_robots()
    robots = robots_state["robots"]
    loading = robots_state["loading"]
    error = robots_state["error"]
    filters = robots_state["filters"]
    set_filters = robots_state["set_filters"]
    refresh_robots = robots_state["refresh"]
    update_robot_status = robots_state["update_robot_status"]
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    current_page = robots_state["current_page"]
    set_current_page = robots_state["set_current_page"]
    total_pages = robots_state["total_pages"]
    # Desempaquetamos los nuevos valores del hook
    sort_by = robots_state["sort_by"]
    sort_dir = robots_state["sort_dir"]
    handle_sort = robots_state["handle_sort"]

    # ESTADO Y LÓGICA DE UI (SIN CAMBIOS)
    search_term, set_search_term = use_state(filters.get("name") or "")
    debounced_search = use_debounced_value(search_term, 300)

    @use_effect(dependencies=[debounced_search])
    def sync_search_with_hook():
        set_filters(lambda prev_filters: {**prev_filters, "name": debounced_search or None})

    def handle_active_filter_change(value):
        active_value = None if value == "all" else value == "true"
        set_filters(lambda prev_filters: {**prev_filters, "active": active_value})

    def handle_online_filter_change(value):
        online_value = None if value == "all" else value == "true"
        set_filters(lambda prev_filters: {**prev_filters, "online": online_value})

    selected_robot, set_selected_robot = use_state(None)
    modal_view, set_modal_view = use_state(None)

    def handle_modal_close(event=None):
        set_selected_robot(None)
        set_modal_view(None)

    async def handle_save_and_refresh():
        await refresh_robots()
        handle_modal_close()

    def handle_create_robot(event=None):
        set_selected_robot({})
        set_modal_view("edit")

    @use_callback
    confirmation_modal_state, set_confirmation_modal_state = use_state(
        {"is_active": False, "title": "", "message": "", "on_confirm": None}
    )

    async def handle_robot_action(action: str, robot):
        if action in ["toggle_active", "toggle_online"]:
            status_key = "Activo" if action == "toggle_active" else "EsOnline"
            await update_robot_status(robot["RobotId"], {status_key: not robot[status_key]}, show_notification)
            return

        set_selected_robot(robot)

        if action == "edit":
            set_modal_view("edit")
        elif action == "assign":
            set_modal_view("assign")
        elif action == "schedule":
            set_modal_view("schedule")
        elif action == "delete":
            set_confirmation_modal_state(
                {
                    "is_active": True,
                    "title": "Confirmar Eliminación",
                    "message": f"¿Estás seguro de que quieres eliminar el robot '{robot['Robot']}'?",
                    "on_confirm": lambda: handle_delete_robot(robot["RobotId"]),
                }
            )

    delete_robot_mutation = robots_state["delete_robot"]

    async def handle_delete_robot(robot_id):
        await delete_robot_mutation(robot_id, show_notification)
        close_confirmation_modal()

    def close_confirmation_modal():
        set_confirmation_modal_state({"is_active": False, "title": "", "message": "", "on_confirm": None})

    # LÓGICA DE RENDERIZADO
    # --- LÓGICA DE RENDERIZADO (CON CORRECCIÓN) ---
    if error:
        # --- CORRECCIÓN: Usamos el componente 'notification' de Bulma para errores ---
        content = html.div({"className": "notification is-danger is-light"}, f"Error al cargar datos: {error}")
    elif loading and not robots:
        content = LoadingSpinner()
    else:
        content = RobotTable(robots=robots, on_action=handle_robot_action, sort_by=sort_by, sort_dir=sort_dir, on_sort=handle_sort)

    return html._(
        # La cabecera con el 'level' ya estaba bien.
        html.div(
            {"className": "level mb-5"},
            html.div(
                {"className": "level-left"},
                html.div({"className": "level-item"}, html.h1({"className": "title is-2"}, "Gestión de Robots")),
            ),
            html.div(
                {"className": "level-right"},
                html.div(
                    {"className": "level-item"},
                    html.button(
                        {"className": "button is-link", "onClick": handle_create_robot},
                        html.span({"className": "icon"}, html.i({"className": "fas fa-plus"})),
                        html.span("Añadir Robot"),
                    ),
                ),
            ),
        ),
        # El componente de filtros ya estaba bien.
        RobotFiltersComponent(
            search_term=search_term,
            active_filter="all" if filters.get("active") is None else str(filters.get("active")).lower(),
            online_filter="all" if filters.get("online") is None else str(filters.get("online")).lower(),
            on_search_change=set_search_term,
            on_active_change=handle_active_filter_change,
            on_online_change=handle_online_filter_change,
        ),
        # --- CORRECCIÓN ---
        html.div(
            content,
            Pagination(current_page=current_page, total_pages=total_pages, on_page_change=set_current_page) if total_pages > 1 else None,
        ),
        # Los modales no cambian, su lógica es interna.
        RobotEditModal(robot=selected_robot if modal_view == "edit" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh),
        AssignmentsModal(
            robot=selected_robot if modal_view == "assign" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
        ),
        SchedulesModal(
            robot=selected_robot if modal_view == "schedule" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
        ),
        ConfirmationModal(
            is_active=confirmation_modal_state["is_active"],
            on_close=close_confirmation_modal,
            on_confirm=confirmation_modal_state["on_confirm"],
            title=confirmation_modal_state["title"],
            message=confirmation_modal_state["message"],
        ),
    )
