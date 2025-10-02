# /src/web/frontend/features/dashboard/dashboard_components.py

from typing import Callable, Dict, List

from backend.schemas import Robot
from reactpy import component, event, html, use_callback, use_context, use_effect, use_state

from ...api_client import get_api_client

# Sube 1 nivel (de dashboard -> features) para encontrar 'modals'
from ...hooks.use_debounced_value_hook import use_debounced_value
from ...hooks.use_robots_hook import use_robots
from ...shared.common_components import LoadingSpinner, Pagination
from ...shared.notifications import NotificationContext

# Sube 2 niveles (de dashboard -> features -> web) para encontrar 'hooks' y 'shared'
from ..modals.dashboard_modal_components import AssignmentsModal, RobotEditModal, SchedulesModal


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
    current_page = robots_state["current_page"]
    set_current_page = robots_state["set_current_page"]
    total_pages = robots_state["total_pages"]
    # Desempaquetamos los nuevos valores del hook
    sort_by = robots_state["sort_by"]
    sort_dir = robots_state["sort_dir"]
    handle_sort = robots_state["handle_sort"]

    # --- AÑADIR ESTO ---
    is_syncing, set_is_syncing = use_state(False)
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    api_client = get_api_client()

    @use_callback
    async def handle_sync(event=None):
        if is_syncing:
            return
        set_is_syncing(True)
        show_notification("Iniciando sincronización con A360...", "info")
        try:
            summary = await api_client.trigger_sync()
            show_notification(
                f"Sincronización completa. Robots: {summary['robots_sincronizados']}, Equipos: {summary['equipos_sincronizados']}.", "success"
            )
            await refresh_robots()  # Refresca la tabla
        except Exception as e:
            show_notification(f"Error en la sincronización: {e}", "error")
        finally:
            set_is_syncing(False)

    # ESTADO Y LÓGICA DE UI (SIN CAMBIOS)
    search_term, set_search_term = use_state(filters.get("name") or "")
    debounced_search = use_debounced_value(search_term, 300)

    @use_effect(dependencies=[debounced_search])
    def sync_search_with_hook(event=None):
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
    async def handle_robot_action(action: str, robot):
        if action in ["toggle_active", "toggle_online"]:
            status_key = "Activo" if action == "toggle_active" else "EsOnline"
            await update_robot_status(robot["RobotId"], {status_key: not robot[status_key]})

        set_selected_robot(robot)

        if action == "edit":
            set_selected_robot(robot)
            set_modal_view("edit")
        elif action == "assign":
            set_selected_robot(robot)
            set_modal_view("assign")
        elif action == "schedule":
            set_selected_robot(robot)
            set_modal_view("schedule")

    # LÓGICA DE RENDERIZADO
    if error:
        content = html.article({"aria_invalid": "true"}, f"Error al cargar datos: {error}")
    elif loading and not robots:
        content = LoadingSpinner()
    else:
        content = RobotTable(robots=robots, on_action=handle_robot_action, sort_by=sort_by, sort_dir=sort_dir, on_sort=handle_sort)

    return html._(
        html.section(
            {"aria-label": "Acciones Principales"},
            html.h1("Gestión de Robots"),
            html.div(
                {"className": "grid"},
                html.div(
                    {"style": {"textAlign": "left"}},
                    html.button(
                        {"onClick": handle_sync, "disabled": is_syncing, "aria-busy": str(is_syncing).lower()},
                        html.i({"className": "fa-solid fa-refresh", "aria-hidden": "true"}),
                        "Sincronizar con A360",
                    ),
                ),
                html.div(
                    {"style": {"textAlign": "right"}},
                    html.button(
                        {"onClick": handle_create_robot},
                        html.i({"className": "fa-solid fa-plus", "aria-hidden": "true"}),
                        " Añadir Robot",
                    ),
                ),
            ),
        ),
        html.section(
            {"aria-label": "Controles de Búsqueda y Filtros"},
            # Pasamos los props al componente de filtros, que también vamos a refactorizar.
            RobotFilters(
                search_term=search_term,
                active_filter="all" if filters.get("active") is None else str(filters.get("active")).lower(),
                online_filter="all" if filters.get("online") is None else str(filters.get("online")).lower(),
                on_search_change=set_search_term,
                on_active_change=handle_active_filter_change,
                on_online_change=handle_online_filter_change,
            ),
        ),
        # El contenido principal (tabla o spinner) y la paginación
        html._(
            content,
            Pagination(current_page=current_page, total_pages=total_pages, on_page_change=set_current_page) if total_pages > 1 else None,
        ),
        # Los modales se mantienen igual, su lógica es interna por ahora.
        RobotEditModal(robot=selected_robot if modal_view == "edit" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh),
        AssignmentsModal(
            robot=selected_robot if modal_view == "assign" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
        ),
        SchedulesModal(
            robot=selected_robot if modal_view == "schedule" else None, on_close=handle_modal_close, on_save_success=handle_save_and_refresh
        ),
    )


@component
def RobotTable(robots: List[Robot], on_action: Callable, sort_by: str, sort_dir: str, on_sort: Callable):
    table_headers = [
        {"key": "Robot", "label": "Robot"},
        {"key": "CantidadEquiposAsignados", "label": "Equipos"},
        {"key": "Activo", "label": "Activo"},
        {"key": "EsOnline", "label": "Online"},
        {"key": "TieneProgramacion", "label": "Tipo Ejecución"},
        {"key": "PrioridadBalanceo", "label": "Prioridad"},
        {"key": "TicketsPorEquipoAdicional", "label": "Tickets/Equipo"},
        {"key": "Acciones", "label": "Acciones", "sortable": False},
    ]

    def render_header(header_info: Dict):
        is_sortable = header_info.get("sortable", True)
        if not is_sortable:
            return html.th(header_info["label"])

        sort_indicator = ""
        is_current_sort_col = sort_by == header_info["key"]
        if is_current_sort_col:
            sort_indicator = " ▲" if sort_dir == "asc" else " ▼"

        return html.th(
            {"scope": "col"},
            html.a(
                {"href": "#", "onClick": event(lambda e: on_sort(header_info["key"]), prevent_default=True)},
                header_info["label"],
                sort_indicator,
            ),
        )

    return html.article(
        html.div(
            {"className": "table-container"},  # Para que la tabla sea responsive en pantallas pequeñas
            html.table(
                html.thead(html.tr(*[render_header(h) for h in table_headers])),
                html.tbody(
                    *[RobotRow(robot=robot, on_action=on_action) for robot in robots]
                    if robots
                    else html.tr(html.td({"colSpan": len(table_headers), "className": "text-center p-8"}, "No se encontraron robots.")),
                ),
            ),
        ),
    )


@component
def RobotFilters(
    search_term: str,
    active_filter: str,
    online_filter: str,
    on_search_change: Callable,
    on_active_change: Callable,
    on_online_change: Callable,
):
    """Componente que encapsula la UI de los filtros."""
    return html.div(
        {"className": "grid"},
        html.input(
            {
                "type": "search",
                "placeholder": "Buscar robots por nombre...",
                "value": search_term,
                "onChange": lambda event: on_search_change(event["target"]["value"]),
            }
        ),
        html.select(
            {
                "value": active_filter,
                "onChange": lambda event: on_active_change(event["target"]["value"]),
            },
            html.option({"value": "all"}, "Activo: Todos"),
            html.option({"value": "true"}, "Solo Activos"),
            html.option({"value": "false"}, "Solo Inactivos"),
        ),
        html.select(
            {
                "value": online_filter,
                "onChange": lambda event: on_online_change(event["target"]["value"]),
            },
            html.option({"value": "all"}, "Online: Todos"),
            html.option({"value": "true"}, "Solo Online"),
            html.option({"value": "false"}, "Solo No Online"),
        ),
    )


@component
def RobotRow(robot: Robot, on_action: Callable):
    """
    Renderiza una única fila para la tabla de robots con manejadores de eventos asíncronos corregidos.
    """

    async def handle_action(action_name: str, event_data=None):
        """Maneja las acciones del robot de forma asíncrona"""
        await on_action(action_name, robot)

    # Funciones auxiliares para los manejadores de eventos
    async def handle_edit(event_data):
        await handle_action("edit")

    async def handle_assign(event_data):
        await handle_action("assign")

    async def handle_schedule(event_data):
        await handle_action("schedule")

    async def handle_toggle_active(event_data):
        await handle_action("toggle_active")

    async def handle_toggle_online(event_data):
        await handle_action("toggle_online")

    # Definición de acciones para el menú
    actions = [
        {"label": "Editar", "on_click": handle_edit},
        {"label": "Asignar", "on_click": handle_assign},
        {"label": "Programar", "on_click": handle_schedule},
    ]

    return html.tr(
        {"key": robot["RobotId"]},
        html.td(robot["Robot"]),
        html.td(robot.get("CantidadEquiposAsignados", 0)),
        html.td(
            html.fieldset(
                html.label(
                    html.input(
                        {
                            "type": "checkbox",
                            "role": "switch",
                            "checked": robot["Activo"],
                            "onChange": handle_toggle_active,
                        }
                    )
                )
            )
        ),
        html.td(
            html.fieldset(
                html.label(
                    html.input(
                        {
                            "type": "checkbox",
                            "role": "switch",
                            "checked": robot["EsOnline"],
                            "onChange": handle_toggle_online,
                        }
                    )
                )
            )
        ),
        html.td("Programado" if robot.get("TieneProgramacion") else "A Demanda"),
        html.td(str(robot["PrioridadBalanceo"])),
        html.td(str(robot.get("TicketsPorEquipoAdicional", "N/A"))),
        # html.td(ActionMenu(actions=actions)),
        html.td(
            # Usamos un div con la clase grid para alinear los íconos horizontalmente
            html.div(
                {"className": "grid"},
                # Botón/Icono para Editar
                html.a(
                    {
                        "href": "#",
                        "onClick": event(handle_edit, prevent_default=True),
                        "data-tooltip": "Editar Robot",  # Tooltip de Pico.css
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-pencil"}),
                ),
                # Botón/Icono para Asignar
                html.a(
                    {
                        "href": "#",
                        "onClick": event(handle_assign, prevent_default=True),
                        "data-tooltip": "Asignar Equipos",  # Tooltip de Pico.css
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-users"}),
                ),
                # Botón/Icono para Programar
                html.a(
                    {
                        "href": "#",
                        "onClick": event(handle_schedule, prevent_default=True),
                        "data-tooltip": "Programar Tareas",
                        "data-placement": "left",  # Tooltip de Pico.css
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-clock"}),
                ),
            )
        ),
    )
