# interfaz_web/components/assignments_modal.py
import asyncio
from typing import Any, Callable, Dict, List

from reactpy import component, html, use_context, use_effect, use_state

from ..services.api_service import get_api_service
from .notifications import NotificationContext


@component
def AssignmentsModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    api_service = get_api_service()

    assigned_teams, set_assigned_teams = use_state([])
    available_teams, set_available_teams = use_state([])
    to_unassign, set_to_unassign = use_state([])
    to_assign, set_to_assign = use_state([])
    is_loading, set_is_loading = use_state(False)

    @use_effect(dependencies=[robot])
    async def fetch_data():
        if not robot:
            return
        set_is_loading(True)
        set_to_unassign([])
        set_to_assign([])
        try:
            assigned_task = api_service.get_robot_assignments(robot["RobotId"])
            available_task = api_service.get_available_teams(robot["RobotId"])
            assigned_res, available_res = await asyncio.gather(assigned_task, available_task)
            set_assigned_teams(assigned_res)
            set_available_teams(available_res)
        except Exception as e:
            show_notification(f"Error al cargar datos: {e}", "error")
        finally:
            set_is_loading(False)

    async def handle_save(event):
        set_is_loading(True)
        try:
            await api_service.update_robot_assignments(robot["RobotId"], to_assign, to_unassign)
            await on_save_success()
        except Exception as e:
            show_notification(f"Error al guardar los cambios: {e}", "error")
        finally:
            set_is_loading(False)

    if not robot:
        return None

    def handle_select_all(teams_in_table, selection_list, set_selection, checked):
        # Convertir todo a listas desde el inicio para evitar problemas de serialización
        teams_list = list(teams_in_table) if teams_in_table else []
        selection_list_safe = list(selection_list) if selection_list else []

        ids_in_table = [team["EquipoId"] for team in teams_list]

        if checked:
            # Agregar IDs que no están en la selección actual
            new_ids = selection_list_safe.copy()
            for team_id in ids_in_table:
                if team_id not in new_ids:
                    new_ids.append(team_id)
        else:
            # Remover IDs que están en la tabla
            new_ids = [team_id for team_id in selection_list_safe if team_id not in ids_in_table]

        set_selection(new_ids)

    def on_toggle_selection(team_id: int, checked: bool, selection_list: List, set_selection: Callable):
        new_list = list(selection_list) if selection_list else []
        is_present = team_id in new_list
        if checked and not is_present:
            new_list.append(team_id)
        elif not checked and is_present:
            new_list.remove(team_id)
        set_selection(new_list)

    def get_status_tag(team):
        if team.get("Reservado"):
            return html.span({"className": "tag is-warning is-light"}, "Reservado")
        if team.get("EsProgramado"):
            return html.span({"className": "tag is-info is-light"}, "Programado")
        return html.span({"className": "tag is-success is-light"}, "Dinámico")

    def render_table(title, teams, selection_list, set_selection, action_label):
        # Convertir a listas para evitar problemas de serialización
        teams_list = list(teams) if teams else []
        selection_list_safe = list(selection_list) if selection_list else []

        ids_in_table = [team["EquipoId"] for team in teams_list]

        # Verificar si todos están seleccionados usando listas
        are_all_selected = len(ids_in_table) > 0 and all(team_id in selection_list_safe for team_id in ids_in_table)

        return html.div(
            html.h3({"className": "title is-5"}, title),
            html.div(
                {"style": {"maxHeight": "25vh", "overflowY": "auto", "border": "1px solid #dbdbdb", "borderRadius": "4px"}},
                html.table(
                    {"className": "table is-fullwidth is-hoverable"},
                    html.thead(
                        html.tr(
                            html.th(
                                {"style": {"width": "10%"}},
                                html.label(
                                    {"className": "checkbox"},
                                    html.input(
                                        {
                                            "type": "checkbox",
                                            "checked": are_all_selected,
                                            "onChange": lambda e: handle_select_all(
                                                teams_list, selection_list_safe, set_selection, e["target"]["checked"]
                                            ),
                                        }
                                    ),
                                ),
                                # f" {action_label}",
                            ),
                            html.th("Nombre Equipo"),
                            html.th("Estado") if action_label == "Desasignar" else None,
                        )
                    ),
                    html.tbody(
                        [
                            html.tr(
                                {"key": team["EquipoId"]},
                                html.td(
                                    html.label(
                                        {"className": "checkbox"},
                                        html.input(
                                            {
                                                "type": "checkbox",
                                                "checked": team["EquipoId"] in selection_list_safe,
                                                "onChange": lambda e, eid=team["EquipoId"]: on_toggle_selection(
                                                    eid, e["target"]["checked"], selection_list_safe, set_selection
                                                ),
                                            }
                                        ),
                                    )
                                ),
                                html.td(team["Equipo"]),
                                html.td(get_status_tag(team)) if action_label == "Desasignar" else None,
                            )
                            for team in teams_list
                        ]
                        if teams_list
                        else [html.tr(html.td({"colSpan": 3, "className": "has-text-centered"}, "No hay equipos."))]
                    ),
                ),
            ),
        )

    return html.div(
        {"className": "modal is-active"},
        html.div({"className": "modal-background", "onClick": on_close}),
        html.div(
            {"className": "modal-card", "style": {"width": "60%", "maxWidth": "800px"}},
            html.header(
                {"className": "modal-card-head"},
                html.p({"className": "modal-card-title"}, "Gestionar Asignaciones de Equipos"),
                html.p({"className": "modal-card-subtitle is-size-7 pt-1"}, f"Robot: {robot['Robot']}"),
                # html.button({"className": "delete", "aria-label": "close", "onClick": on_close}),
            ),
            html.section(
                {"className": "modal-card-body"},
                html.div(
                    {"className": "columns is-variable is-1"},
                    html.div(
                        {"className": "column"},
                        render_table("Equipos Asignados", assigned_teams, to_unassign, set_to_unassign, "Desasignar"),
                    ),
                    html.div(
                        {"className": "column"},
                        render_table("Equipos Disponibles para Asignar", available_teams, to_assign, set_to_assign, "Asignar"),
                    ),
                ),
            ),
            html.footer(
                {"className": "modal-card-foot is-justify-content-flex-end"},
                html.div(
                    {"className": "buttons"},
                    html.button(
                        {
                            "className": f"button is-success {'is-loading' if is_loading else ''}",
                            "onClick": handle_save,
                            "disabled": is_loading or (not to_assign and not to_unassign),
                        },
                        "Guardar Cambios",
                    ),
                    html.button({"className": "button", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
                ),
            ),
        ),
    )


"""VERSION AN"""
# # interfaz_web/components/assignments_modal.py
# import asyncio
# from typing import Any, Callable, Dict, List

# from reactpy import component, html, use_context, use_effect, use_state

# from ..services.api_service import get_api_service
# from .notifications import NotificationContext


# @component
# def AssignmentsModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
#     notification_ctx = use_context(NotificationContext)
#     show_notification = notification_ctx["show_notification"]
#     api_service = get_api_service()

#     assigned_teams, set_assigned_teams = use_state([])
#     available_teams, set_available_teams = use_state([])
#     to_unassign, set_to_unassign = use_state([])
#     to_assign, set_to_assign = use_state([])
#     is_loading, set_is_loading = use_state(False)

#     @use_effect(dependencies=[robot])
#     async def fetch_data():
#         if not robot:
#             return
#         set_is_loading(True)
#         set_to_unassign([])
#         set_to_assign([])
#         try:
#             assigned_task = api_service.get_robot_assignments(robot["RobotId"])
#             available_task = api_service.get_available_teams(robot["RobotId"])
#             assigned_res, available_res = await asyncio.gather(assigned_task, available_task)
#             set_assigned_teams(assigned_res)
#             set_available_teams(available_res)
#         except Exception as e:
#             show_notification(f"Error al cargar datos: {e}", "error")
#         finally:
#             set_is_loading(False)

#     async def handle_save(event):
#         set_is_loading(True)
#         try:
#             await api_service.update_robot_assignments(robot["RobotId"], to_assign, to_unassign)
#             await on_save_success()
#         except Exception as e:
#             show_notification(f"Error al guardar los cambios: {e}", "error")
#         finally:
#             set_is_loading(False)

#     if not robot:
#         return None

#     def handle_select_all(teams_in_table, selection_list, set_selection, checked):
#         # Convertir todo a listas desde el inicio para evitar problemas de serialización
#         teams_list = list(teams_in_table) if teams_in_table else []
#         selection_list_safe = list(selection_list) if selection_list else []

#         ids_in_table = [team["EquipoId"] for team in teams_list]

#         if checked:
#             # Agregar IDs que no están en la selección actual
#             new_ids = selection_list_safe.copy()
#             for team_id in ids_in_table:
#                 if team_id not in new_ids:
#                     new_ids.append(team_id)
#         else:
#             # Remover IDs que están en la tabla
#             new_ids = [team_id for team_id in selection_list_safe if team_id not in ids_in_table]

#         set_selection(new_ids)

#     def on_toggle_selection(team_id: int, checked: bool, selection_list: List, set_selection: Callable):
#         new_list = list(selection_list) if selection_list else []
#         is_present = team_id in new_list
#         if checked and not is_present:
#             new_list.append(team_id)
#         elif not checked and is_present:
#             new_list.remove(team_id)
#         set_selection(new_list)

#     def get_status_tag(team):
#         if team.get("Reservado"):
#             return html.span({"className": "tag is-warning"}, "Reservado")
#         if team.get("EsProgramado"):
#             return html.span({"className": "tag is-info"}, "Programado")
#         return html.span({"className": "tag is-success"}, "Dinámico")

#     def render_table(title, teams, selection_list, set_selection, action_label):
#         # Convertir a listas para evitar problemas de serialización
#         teams_list = list(teams) if teams else []
#         selection_list_safe = list(selection_list) if selection_list else []

#         ids_in_table = [team["EquipoId"] for team in teams_list]

#         # Verificar si todos están seleccionados usando listas
#         are_all_selected = len(ids_in_table) > 0 and all(team_id in selection_list_safe for team_id in ids_in_table)

#         return html.div(
#             html.h3({"className": "title is-5"}, title),
#             html.div(
#                 {"style": {"maxHeight": "25vh", "overflowY": "auto", "border": "1px solid #dbdbdb", "borderRadius": "4px"}},
#                 html.table(
#                     {"className": "table is-fullwidth is-hoverable"},
#                     html.thead(
#                         html.tr(
#                             html.th(
#                                 {"style": {"width": "10%"}},
#                                 html.label(
#                                     {"className": "checkbox"},
#                                     html.input(
#                                         {
#                                             "type": "checkbox",
#                                             "checked": are_all_selected,
#                                             "onChange": lambda e: handle_select_all(
#                                                 teams_list, selection_list_safe, set_selection, e["target"]["checked"]
#                                             ),
#                                         }
#                                     ),
#                                 ),
#                                 # f" {action_label}",
#                             ),
#                             html.th("Nombre Equipo"),
#                             html.th("Estado") if action_label == "" else None,
#                         )
#                     ),
#                     html.tbody(
#                         [
#                             html.tr(
#                                 {"key": team["EquipoId"]},
#                                 html.td(
#                                     html.label(
#                                         {"className": "checkbox"},
#                                         html.input(
#                                             {
#                                                 "type": "checkbox",
#                                                 "checked": team["EquipoId"] in selection_list_safe,
#                                                 "onChange": lambda e, eid=team["EquipoId"]: on_toggle_selection(
#                                                     eid, e["target"]["checked"], selection_list_safe, set_selection
#                                                 ),
#                                             }
#                                         ),
#                                     )
#                                 ),
#                                 html.td(team["Equipo"]),
#                                 html.td(get_status_tag(team)) if action_label == "Desasignar" else None,
#                             )
#                             for team in teams_list
#                         ]
#                         if teams_list
#                         else [html.tr(html.td({"colSpan": 3, "className": "has-text-centered"}, "No hay equipos."))]
#                     ),
#                 ),
#             ),
#         )

#     return html.div(
#         {"className": "modal is-active"},
#         html.div({"className": "modal-background", "onClick": on_close}),
#         html.div(
#             {"className": "modal-card", "style": {"width": "60%", "maxWidth": "800px"}},
#             html.header(
#                 {"className": "modal-card-head"},
#                 html.p({"className": "modal-card-title"}, "Gestionar Asignaciones de Equipos"),
#                 html.p({"className": "modal-card-subtitle is-size-7 pt-1"}, f"Robot: {robot['Robot']}"),
#                 # html.button({"className": "delete", "aria-label": "close", "onClick": on_close}),
#             ),
#             html.section(
#                 {"className": "modal-card-body"},
#                 html.div(
#                     {"className": "columns is-variable is-1"},
#                     html.div(
#                         {"className": "column"},
#                         render_table("Equipos Asignados", assigned_teams, to_unassign, set_to_unassign, "desasignado"),
#                     ),
#                     html.div(
#                         {"className": "column"},
#                         render_table("Equipos Disponible", available_teams, to_assign, set_to_assign, "asignado"),
#                     ),
#                 ),
#             ),
#             html.footer(
#                 {"className": "modal-card-foot is-justify-content-flex-end"},
#                 html.div(
#                     {"className": "buttons"},
#                     html.button(
#                         {"className": f"button is-success {'is-loading' if is_loading else ''}", "onClick": handle_save, "disabled": is_loading},
#                         "Guardar",
#                     ),
#                     html.button({"className": "button", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
#                 ),
#             ),
#         ),
#     )
