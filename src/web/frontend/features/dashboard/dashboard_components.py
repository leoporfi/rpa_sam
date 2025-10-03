# /src/web/frontend/features/dashboard/dashboard_components.py

from typing import Callable, Dict, List

from backend.schemas import Robot
from reactpy import component, event, html

from ...shared.common_components import LoadingSpinner, Pagination


@component
def DashboardControls(
    # Props para los botones de acción
    is_syncing: bool,
    on_sync: Callable,
    on_create_robot: Callable,
    # Props para los filtros
    search_term: str,
    on_search_change: Callable,
    active_filter: str,
    on_active_change: Callable,
    online_filter: str,
    on_online_change: Callable,
    is_searching: bool,
):
    """
    Componente que encapsula todos los controles superiores del dashboard.
    Su estructura se ha corregido para usar flexbox y gap.
    """
    return html.div(
        {"style": {"display": "flex", "flexDirection": "column", "gap": "var(--pico-form-element-spacing-vertical)"}},
        # Fila para Título y Botones de Acción
        html.div(
            {"className": "grid"},
            html.div(html.h2("Gestión de Robots")),
            html.div(
                {"style": {"display": "flex", "justifyContent": "flex-end", "gap": "1rem"}},
                html.button(
                    {
                        "onClick": on_sync,
                        "disabled": is_syncing,
                        "aria-busy": str(is_syncing).lower(),
                        "className": "secondary-ghost",
                    },
                    html.i({"className": "fa-solid fa-refresh"}),
                    " Sincronizar con A360",
                ),
                html.button(
                    {"onClick": on_create_robot},
                    html.i({"className": "fa-solid fa-plus"}),
                    " Añadir Robot",
                ),
            ),
        ),
        # Fila de Filtros
        html.div(
            {"className": "grid"},
            html.input(
                {
                    "type": "search",
                    "placeholder": "Buscar robots por nombre...",
                    "value": search_term,
                    "onChange": lambda event: on_search_change(event["target"]["value"]),
                    "aria-busy": str(is_searching).lower(),
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
        ),
    )


@component
def RobotDashboard(robots_state: dict, on_action: Callable):
    """
    Componente presentacional para el dashboard de robots.
    Recibe todo el estado y los manejadores como props.
    """
    # Desempaca el estado del hook que recibe como prop
    robots = robots_state["robots"]
    loading = robots_state["loading"]
    error = robots_state["error"]

    if error:
        content = html.article({"aria-invalid": "true"}, f"Error al cargar datos: {error}")
    elif loading and not robots:
        content = LoadingSpinner()
    else:
        content = RobotTable(
            robots=robots,
            on_action=on_action,
            sort_by=robots_state["sort_by"],
            sort_dir=robots_state["sort_dir"],
            on_sort=robots_state["handle_sort"],
        )

    # El dashboard ya no renderiza los modales directamente
    return html.div(
        content,
        Pagination(
            current_page=robots_state["current_page"],
            total_pages=robots_state["total_pages"],
            on_page_change=robots_state["set_current_page"],
        )
        if robots_state["total_pages"] > 1
        else None,
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
            {"className": "table-container"},
            html.table(
                html.thead(html.tr(*[render_header(h) for h in table_headers])),
                html.tbody(
                    *[RobotRow(robot=robot, on_action=on_action) for robot in robots]
                    if robots
                    else html.tr(
                        html.td({"colSpan": len(table_headers), "style": {"textAlign": "center", "padding": "2rem"}}, "No se encontraron robots.")
                    )
                ),
            ),
        ),
    )


@component
def RobotRow(robot: Robot, on_action: Callable):
    # <<-- CORRECCIÓN: Definimos manejadores async -->>
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
        # <<-- CORRECCIÓN: Usamos los nuevos manejadores async -->>
        html.td(
            html.fieldset(
                html.label(html.input({"type": "checkbox", "role": "switch", "checked": robot["Activo"], "onChange": handle_toggle_active}))
            )
        ),
        html.td(
            html.fieldset(
                html.label(html.input({"type": "checkbox", "role": "switch", "checked": robot["EsOnline"], "onChange": handle_toggle_online}))
            )
        ),
        html.td("Programado" if robot.get("TieneProgramacion") else "A Demanda"),
        html.td(str(robot["PrioridadBalanceo"])),
        html.td(str(robot.get("TicketsPorEquipoAdicional", "N/A"))),
        html.td(
            html.div(
                {"className": "grid"},
                # <<-- CORRECCIÓN: Usamos los nuevos manejadores async -->>
                html.a(
                    {"href": "#", "onClick": event(handle_edit, prevent_default=True), "data-tooltip": "Editar Robot", "className": "secondary"},
                    html.i({"className": "fa-solid fa-pencil"}),
                ),
                html.a(
                    {"href": "#", "onClick": event(handle_assign, prevent_default=True), "data-tooltip": "Asignar Equipos", "className": "secondary"},
                    html.i({"className": "fa-solid fa-users"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "onClick": event(handle_schedule, prevent_default=True),
                        "data-tooltip": "Programar Tareas",
                        "data-placement": "left",
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-clock"}),
                ),
            )
        ),
    )
