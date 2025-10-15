# /src/web/features/dashboard/dashboard_components.py

from typing import Callable, Dict, List

from reactpy import component, event, html, use_state

# Corregimos la importación para que sea absoluta desde la raíz 'src'
from sam.web.backend.schemas import Robot

from ...shared.common_components import LoadingSpinner, Pagination


@component
def DashboardControls(
    is_syncing: bool,
    on_sync: Callable,
    on_create_robot: Callable,
    search_term: str,
    on_search_change: Callable,
    active_filter: str,
    on_active_change: Callable,
    online_filter: str,
    on_online_change: Callable,
    is_searching: bool,
):
    """Controles para el dashboard de Robots (título, botones, filtros)."""
    is_expanded, set_is_expanded = use_state(False)

    collapsible_panel_class = "collapsible-panel"
    if is_expanded:
        collapsible_panel_class += " is-expanded"

    return html.div(
        {"class_name": "dashboard-controls"},
        html.div(
            {"class_name": "controls-header"},
            html.h2("Gestión de Robots"),
            html.button(
                {
                    "class_name": "mobile-controls-toggle outline secondary",
                    "on_click": lambda e: set_is_expanded(not is_expanded),
                },
                html.i({"class_name": f"fa-solid fa-chevron-{'up' if is_expanded else 'down'}"}),
                " Controles",
            ),
        ),
        html.div(
            {"class_name": collapsible_panel_class},
            # Simplificamos la estructura para el CSS Grid
            html.div(
                {"class_name": "master-controls-grid"},
                html.input(
                    {
                        "type": "search",
                        "placeholder": "Buscar robots por nombre...",
                        "value": search_term,
                        "on_change": lambda event: on_search_change(event["target"]["value"]),
                        "aria-busy": str(is_searching).lower(),
                        "class_name": "search-input",  # Clase específica para el buscador
                    }
                ),
                html.select(
                    {
                        "value": active_filter,
                        "on_change": lambda event: on_active_change(event["target"]["value"]),
                    },
                    html.option({"value": "all"}, "Activo: Todos"),
                    html.option({"value": "true"}, "Solo Activos"),
                    html.option({"value": "false"}, "Solo Inactivos"),
                ),
                html.select(
                    {
                        "value": online_filter,
                        "on_change": lambda event: on_online_change(event["target"]["value"]),
                    },
                    html.option({"value": "all"}, "Online: Todos"),
                    html.option({"value": "true"}, "Solo Online"),
                    html.option({"value": "false"}, "Solo No Online"),
                ),
                html.button(
                    {
                        "on_click": on_sync,
                        "disabled": is_syncing,
                        "aria-busy": str(is_syncing).lower(),
                        "class_name": "secondary-ghost",
                    },
                    html.i({"class_name": "fa-solid fa-refresh"}),
                    " Sincronizar",
                ),
                html.button(
                    {"on_click": on_create_robot},
                    html.i({"class_name": "fa-solid fa-plus"}),
                    " Añadir Robot",
                ),
            ),
        ),
    )


@component
def RobotDashboard(robots: List[Robot], on_action: Callable, robots_state: Dict, set_current_page: Callable):
    """Componente principal que ahora solo renderiza la tabla/tarjetas y la paginación."""
    loading = robots_state["loading"]
    error = robots_state["error"]
    current_page = robots_state["current_page"]
    total_pages = robots_state["total_pages"]
    total_count = robots_state["total_count"]
    page_size = robots_state["page_size"]

    if error:
        return html.article({"aria_invalid": "true"}, f"Error al cargar datos: {error}")
    if loading and not robots:
        return LoadingSpinner()

    pagination_component = (
        Pagination(
            current_page=current_page,
            total_pages=total_pages,
            total_items=total_count,
            items_per_page=page_size,
            on_page_change=set_current_page,
        )
        if total_pages > 1
        else None
    )

    return html._(
        html.div(
            {"class_name": "cards-container robot-cards"},
            *[RobotCard(robot=robot, on_action=on_action) for robot in robots],
        ),
        html.div(
            {"class_name": "table-container"},
            RobotTable(
                robots=robots,
                on_action=on_action,
                sort_by=robots_state["sort_by"],
                sort_dir=robots_state["sort_dir"],
                on_sort=robots_state["handle_sort"],
            ),
        ),
        pagination_component,
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
                {"href": "#", "on_click": event(lambda e: on_sort(header_info["key"]), prevent_default=True)},
                header_info["label"],
                sort_indicator,
            ),
        )

    return html.article(
        html.table(
            html.thead(html.tr(*[render_header(h) for h in table_headers])),
            html.tbody(
                *[RobotRow(robot=robot, on_action=on_action) for robot in robots]
                if robots
                else html.tr(
                    # RFR-17: Mensaje descriptivo cuando no hay datos.
                    html.td(
                        {"colSpan": len(table_headers), "style": {"textAlign": "center"}},
                        "No se encontraron robots.",
                    )
                )
            ),
        )
    )


@component
def RobotRow(robot: Robot, on_action: Callable):
    async def handle_toggle_active(event):
        await on_action("toggle_active", robot)

    async def handle_toggle_online(event):
        await on_action("toggle_online", robot)

    async def handle_edit(event):
        await on_action("edit", robot)

    async def handle_assign(event):
        await on_action("assign", robot)

    async def handle_schedule(event):
        await on_action("schedule", robot)

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
                            "on_change": event(handle_toggle_active),
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
                            "on_change": event(handle_toggle_online),
                        }
                    )
                )
            )
        ),
        html.td("Programado" if robot.get("TieneProgramacion") else "A Demanda"),
        html.td(str(robot["PrioridadBalanceo"])),
        html.td(str(robot.get("TicketsPorEquipoAdicional", "N/A"))),
        html.td(
            html.div(
                {"class_name": "grid"},
                html.a(
                    {
                        "href": "#",
                        "on_click": event(handle_edit, prevent_default=True),
                        "data-tooltip": "Editar Robot",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-pencil"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "on_click": event(handle_assign, prevent_default=True),
                        "data-tooltip": "Asignar Equipos",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-users"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "on_click": event(handle_schedule, prevent_default=True),
                        "data-tooltip": "Programar Tareas",
                        "data-placement": "left",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-clock"}),
                ),
            )
        ),
    )


@component
def RobotCard(robot: Robot, on_action: Callable):
    async def handle_toggle_active(event):
        await on_action("toggle_active", robot)

    async def handle_toggle_online(event):
        await on_action("toggle_online", robot)

    async def handle_edit(event):
        await on_action("edit", robot)

    async def handle_assign(event):
        await on_action("assign", robot)

    async def handle_schedule(event):
        await on_action("schedule", robot)

    return html.article(
        {"key": robot["RobotId"], "class_name": "robot-card"},
        html.div(
            {"class_name": "robot-card-header"},
            html.h5(robot["Robot"]),
        ),
        html.div(
            {"class_name": "robot-card-body"},
            html.div(
                {"class_name": "grid"},
                html.label(
                    html.input(
                        {
                            "type": "checkbox",
                            "role": "switch",
                            "checked": robot["Activo"],
                            "on_change": event(handle_toggle_active),
                        }
                    ),
                    "Activo",
                ),
                html.label(
                    html.input(
                        {
                            "type": "checkbox",
                            "role": "switch",
                            "checked": robot["EsOnline"],
                            "on_change": event(handle_toggle_online),
                        }
                    ),
                    "Online",
                ),
            ),
            html.p(f"Equipos: {robot.get('CantidadEquiposAsignados', 0)}"),
            html.p(f"Ejecución: {'Programado' if robot.get('TieneProgramacion') else 'A Demanda'}"),
        ),
        html.footer(
            {"class_name": "robot-card-footer"},
            html.button({"class_name": "outline secondary", "on_click": event(handle_edit)}, "Editar"),
            html.button({"class_name": "outline secondary", "on_click": event(handle_assign)}, "Asignar"),
            html.button({"class_name": "outline secondary", "on_click": event(handle_schedule)}, "Programar"),
        ),
    )
