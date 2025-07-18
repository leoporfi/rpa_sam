# src/interfaz_web/components/robot_row.py
from typing import Callable

from reactpy import component, html

from ..schemas.robot_types import Robot
from .common.action_menu import ActionMenu


@component
def RobotRow(robot: Robot, on_action: Callable):
    """
    Renderiza una única fila para la tabla de robots con clases de Bulma
    y manejadores de eventos asíncronos.
    """

    async def handle_edit(event=None):
        await on_action("edit", robot)

    async def handle_assign(event=None):
        await on_action("assign", robot)

    async def handle_schedule(event=None):
        await on_action("schedule", robot)

    async def handle_toggle_active(event=None):
        await on_action("toggle_active", robot)

    async def handle_toggle_online(event=None):
        await on_action("toggle_online", robot)

    async def handle_delete(event=None):
        await on_action("delete", robot)

    actions = [
        {"label": "Editar Propiedades", "on_click": handle_edit},
        {"label": "Gestionar Asignaciones", "on_click": handle_assign},
        {"label": "Gestionar Programaciones", "on_click": handle_schedule},
        {"label": "Eliminar Robot", "on_click": handle_delete, "is_danger": True},
    ]

    # bulma-switch
    return html.tr(
        {"key": robot["RobotId"], "className": "is-vcentered"},
        html.td(robot["Robot"]),
        html.td({"className": "has-text-centered"}, robot.get("CantidadEquiposAsignados", 0)),
        # Celda para el interruptor "Activo"
        html.td(
            html.div(
                {"className": "field"},
                html.input(
                    {
                        "id": f"switch-activo-{robot['RobotId']}",
                        "type": "checkbox",
                        "className": "switch is-rounded is-small is-info",  # Clases de bulma-switch
                        "checked": robot["Activo"],
                        "onChange": handle_toggle_active,
                    }
                ),
                html.label({"htmlFor": f"switch-activo-{robot['RobotId']}"}),
            )
        ),
        # Celda para el interruptor "Online"
        html.td(
            html.div(
                {"className": "field"},
                html.input(
                    {
                        "id": f"switch-online-{robot['RobotId']}",
                        "type": "checkbox",
                        "className": "switch is-rounded is-small is-success",  # Clases de bulma-switch
                        "checked": robot["EsOnline"],
                        "onChange": handle_toggle_online,
                    }
                ),
                html.label({"htmlFor": f"switch-online-{robot['RobotId']}"}),
            )
        ),
        html.td(
            html.span(
                {"className": f"tag  {'is-info' if robot.get('TieneProgramacion') else 'is-primary'}"},
                "Programado" if robot.get("TieneProgramacion") else "A Demanda",
            )
        ),
        html.td(str(robot["PrioridadBalanceo"])),
        html.td({"className": "has-text-centered"}, str(robot.get("TicketsPorEquipoAdicional", "N/A"))),
        html.td({"className": "has-text-right"}, ActionMenu(actions=actions)),
    )
