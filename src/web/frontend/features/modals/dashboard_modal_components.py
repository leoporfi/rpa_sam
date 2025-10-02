# src/interfaz_web/components/robot_modal.py

# src/interfaz_web/components/assignments_modal.py
# interfaz_web/components/schedules_modal.py
import asyncio
from typing import Any, Callable, Dict, List, Set

import httpx
from reactpy import component, event, html, use_callback, use_context, use_effect, use_memo, use_state

from ...api_client import ApiClient, get_api_client
from ...shared.notifications import NotificationContext

# from ..client.config.settings import Settings

# Constantes para mejorar mantenibilidad
SCHEDULE_TYPES = ["Diaria", "Semanal", "Mensual", "Especifica"]
DEFAULT_FORM_STATE = {
    "ProgramacionId": None,
    "TipoProgramacion": "Diaria",
    "HoraInicio": "09:00",
    "Tolerancia": 60,
    "DiasSemana": "Lu,Ma,Mi,Ju,Vi",
    "DiaDelMes": 1,
    "FechaEspecifica": "",
    "Equipos": [],  # Siempre lista, nunca set
}


# URL_BASE = Settings.API_BASE_URL

DEFAULT_ROBOT_STATE = {
    "RobotId": None,
    "Robot": "",
    "Descripcion": "",
    "Activo": True,  # Campo requerido para la creación
    "EsOnline": False,  # Campo requerido para la creación
    "MinEquipos": 1,
    "MaxEquipos": -1,
    "PrioridadBalanceo": 100,
    "TicketsPorEquipoAdicional": 10,
}


@component
def RobotEditModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    form_data, set_form_data = use_state(DEFAULT_ROBOT_STATE)
    is_loading, set_is_loading = use_state(False)
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]

    #  Usar la instancia del servicio de API
    api_service = get_api_client()
    is_edit_mode = bool(robot and robot.get("RobotId") is not None)

    @use_effect(dependencies=[robot])
    def populate_form_data():
        if robot is not None:
            # Si es un objeto vacío (crear), usa el default. Si tiene datos (editar), lo puebla.
            set_form_data(robot if is_edit_mode else DEFAULT_ROBOT_STATE)

    if robot is None:
        return None

    def handle_form_change(field_name, field_value):
        if field_name in ["RobotId", "MinEquipos", "MaxEquipos", "PrioridadBalanceo", "TicketsPorEquipoAdicional"]:
            try:
                field_value = int(field_value) if field_value != "" else None
            except (ValueError, TypeError):
                field_value = None
        set_form_data(lambda old_data: {**old_data, field_name: field_value})

    async def handle_save(event_data):
        set_is_loading(True)

        try:
            if is_edit_mode:
                # El payload para actualizar debe coincidir con el modelo RobotUpdateRequest
                payload_to_send = {
                    "Robot": form_data.get("Robot"),
                    "Descripcion": form_data.get("Descripcion"),
                    "MinEquipos": form_data.get("MinEquipos"),
                    "MaxEquipos": form_data.get("MaxEquipos"),
                    "PrioridadBalanceo": form_data.get("PrioridadBalanceo"),
                    "TicketsPorEquipoAdicional": form_data.get("TicketsPorEquipoAdicional"),
                }
                await api_service.update_robot(robot["RobotId"], payload_to_send)
                show_notification("Robot actualizado con éxito.", "success")
            else:
                # El payload para crear debe coincidir con RobotCreateRequest
                # Validar que el RobotId no esté vacío
                if not form_data.get("RobotId"):
                    show_notification("El campo 'Robot ID' es requerido.", "error")
                    set_is_loading(False)
                    return

                await api_service.create_robot(form_data)
                show_notification("Robot creado con éxito.", "success")

            await on_save_success()
        except Exception as e:
            show_notification(str(e), "error")
        finally:
            set_is_loading(False)

    return html.dialog(
        {"open": True if robot is not None else False},
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": event(on_close, prevent_default=True)}),
                html.h2("Editar Robot") if is_edit_mode else html.h2("Crear Nuevo Robot"),
            ),
            html.form(
                {"id": "robot-form", "onSubmit": event(handle_save, prevent_default=True)},
                html.div(
                    {"className": "grid"},
                    # Campo Nombre
                    html.label(
                        {"htmlFor": "robot-name"},
                        "Nombre",
                        html.input(
                            {
                                "id": "robot-name",
                                "type": "text",
                                "value": form_data.get("Robot", ""),
                                "onChange": lambda e: handle_form_change("Robot", e["target"]["value"]),
                                "required": True,
                            }
                        ),
                    ),
                    # Campo Robot ID
                    html.label(
                        {"htmlFor": "robot-id"},
                        "Robot ID (de A360)",
                        html.input(
                            {
                                "id": "robot-id",
                                "type": "number",
                                "value": form_data.get("RobotId", ""),
                                "onChange": lambda e: handle_form_change("RobotId", e["target"]["value"]),
                                "required": not is_edit_mode,
                                "disabled": is_edit_mode,
                            }
                        ),
                    ),
                ),
                # Campo Descripción
                html.label(
                    {"htmlFor": "robot-desc"},
                    "Descripción",
                    html.textarea(
                        {
                            "id": "robot-desc",
                            "rows": 3,
                            "value": form_data.get("Descripcion", ""),
                            "onChange": lambda e: handle_form_change("Descripcion", e["target"]["value"]),
                        }
                    ),
                ),
                html.div(
                    {"className": "grid"},
                    html.label(
                        {"htmlFor": "min-equipos"},
                        "Mín. Equipos",
                        html.div(
                            {"className": "range"},
                            html.output(
                                form_data.get("MinEquipos", "0"),
                            ),
                            html.input(
                                {
                                    "id": "min-equipos",
                                    "type": "range",
                                    "min": "0",
                                    "max": "99",
                                    "value": form_data.get("MinEquipos", ""),
                                    "onChange": lambda e: handle_form_change("MinEquipos", e["target"]["value"]),
                                    "style": {"flexGrow": "1"},
                                }
                            ),
                        ),
                    ),
                    html.label(
                        {"htmlFor": "max-equipos"},
                        "Máx. Equipos",
                        html.div(
                            {"className": "range"},
                            html.output(
                                form_data.get("MaxEquipos", "0"),
                            ),
                            html.input(
                                {
                                    "id": "max-equipos",
                                    "type": "range",
                                    "min": "-1",
                                    "max": "100",
                                    "value": form_data.get("MaxEquipos", ""),
                                    "onChange": lambda e: handle_form_change("MaxEquipos", e["target"]["value"]),
                                    "style": {"flexGrow": "1"},
                                }
                            ),
                        ),
                    ),
                ),
                html.div(
                    {"className": "grid"},
                    html.label(
                        {"htmlFor": "prioridad"},
                        "Prioridad",
                        html.div(
                            {"className": "range"},
                            html.output(
                                {"className": "button"},
                                form_data.get("PrioridadBalanceo", "0"),
                            ),
                            html.input(
                                {
                                    "id": "prioridad",
                                    "type": "range",
                                    "min": "0",
                                    "max": "100",
                                    "step": "10",
                                    "value": form_data.get("PrioridadBalanceo", ""),
                                    "onChange": lambda e: handle_form_change("PrioridadBalanceo", e["target"]["value"]),
                                    "style": {"flexGrow": "1"},
                                }
                            ),
                        ),
                    ),
                    html.label(
                        {"htmlFor": "tickets"},
                        "Tickets/Equipo Adic.",
                        html.div(
                            {"className": "range"},
                            html.output(
                                form_data.get("TicketsPorEquipoAdicional", "0"),
                            ),
                            html.input(
                                {
                                    "id": "tickets",
                                    "type": "range",
                                    "min": "1",
                                    "max": "100",
                                    "value": form_data.get("TicketsPorEquipoAdicional", ""),
                                    "onChange": lambda e: handle_form_change("TicketsPorEquipoAdicional", e["target"]["value"]),
                                    "style": {"flexGrow": "1"},
                                }
                            ),
                        ),
                    ),
                ),
            ),
            html.footer(
                html.div(
                    {"className": "grid"},
                    html.button({"type": "button", "className": "secondary", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
                    html.button({"type": "submit", "form": "robot-form", "aria-busy": str(is_loading).lower(), "disabled": is_loading}, "Guardar"),
                )
            ),
        ),
    )


# AssignmentsModal
@component
def AssignmentsModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    # El estado se inicializa correctamente con listas
    assigned_teams, set_assigned_teams = use_state([])
    available_teams, set_available_teams = use_state([])
    to_unassign, set_to_unassign = use_state([])
    to_assign, set_to_assign = use_state([])
    is_loading, set_is_loading = use_state(False)

    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]

    api_service = get_api_client()

    @use_effect(dependencies=[robot])
    def fetch_data():
        async def get_data():
            if not robot:
                return
            set_is_loading(True)
            set_to_unassign([])
            set_to_assign([])
            try:
                assigned_res = await api_service.get_robot_assignments(robot["RobotId"])
                available_res = await api_service.get_available_teams(robot["RobotId"])
                set_assigned_teams(assigned_res)
                set_available_teams(available_res)
            except Exception as e:
                show_notification(f"Error al cargar datos: {e}", "error")
            finally:
                set_is_loading(False)

        asyncio.create_task(get_data())

    async def handle_save(event_data):
        set_is_loading(True)
        try:
            await api_service.update_robot_assignments(robot["RobotId"], to_assign, to_unassign)
            await on_save_success()
            show_notification("Se actualizó la asiganación correctamente", "success")
        except Exception as e:
            show_notification(f"Error al guardar: {e}", "error")
        finally:
            set_is_loading(False)

    if not robot:
        return None

    def get_estado(team: Dict) -> tuple[str, str]:
        if team.get("EsProgramado"):
            return ("Programado", "tag-programado")
        if team.get("Reservado"):
            return ("Reservado", "tag-reservado")
        return ("Dinámico", "tag-dinamico")

    return html.dialog(
        {"open": True},
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": event(on_close, prevent_default=True)}),
                html.h2("Asignación de Robots"),
                html.p(f"{robot.get('Robot', '')}"),
            ),
            html.div(
                {"className": "grid"},
                # Columna de Equipos Asignados
                html.div(
                    html.h5("Equipos Asignados"),
                    html.div(
                        {"style": {"maxHeight": "40vh", "overflow-y": "auto", "font-size": "0.90rem"}},
                        html.table(
                            html.thead(
                                html.tr(
                                    html.th(
                                        html.input(
                                            {
                                                "type": "checkbox",
                                                "onChange": lambda e: set_to_unassign(
                                                    list({team["EquipoId"] for team in assigned_teams}) if e["target"]["checked"] else []
                                                ),
                                            }
                                        )
                                    ),
                                    html.th("Nombre Equipo"),
                                    html.th("Estado"),
                                )
                            ),
                            html.tbody(
                                *[
                                    html.tr(
                                        {"key": team["EquipoId"]},
                                        html.td(
                                            html.input(
                                                {
                                                    "type": "checkbox",
                                                    "checked": team["EquipoId"] in to_unassign,
                                                    "onChange": lambda e, eid=team["EquipoId"]: set_to_unassign(
                                                        (to_unassign + [eid]) if e["target"]["checked"] else [i for i in to_unassign if i != eid]
                                                    ),
                                                }
                                            )
                                        ),
                                        html.td(team["Equipo"]),
                                        html.td(
                                            # Usamos un <span> para poder darle estilo si queremos
                                            html.span(
                                                {"className": f"tag {get_estado(team)[1]}"},
                                                get_estado(team)[0],  # Llamamos a la función para obtener el texto
                                            )
                                        ),
                                    )
                                    for team in assigned_teams
                                    if isinstance(team, dict)
                                ]
                            ),
                        ),
                    ),
                ),
                # Columna de Equipos Disponibles
                html.div(
                    html.h5("Equipos Disponibles"),
                    html.div(
                        {"style": {"maxHeight": "40vh", "overflow-y": "auto", "font-size": "0.90rem"}},
                        html.table(
                            html.thead(
                                html.tr(
                                    html.th(
                                        html.input(
                                            {
                                                "type": "checkbox",
                                                "onChange": lambda e: set_to_assign(
                                                    list({team["EquipoId"] for team in available_teams}) if e["target"]["checked"] else []
                                                ),
                                            }
                                        )
                                    ),
                                    html.th("Nombre Equipo"),
                                )
                            ),
                            html.tbody(
                                *[
                                    html.tr(
                                        {"key": team["EquipoId"]},
                                        html.td(
                                            html.input(
                                                {
                                                    "type": "checkbox",
                                                    "checked": team["EquipoId"] in to_assign,
                                                    "onChange": lambda e, eid=team["EquipoId"]: set_to_assign(
                                                        (to_assign + [eid]) if e["target"]["checked"] else [i for i in to_assign if i != eid]
                                                    ),
                                                }
                                            )
                                        ),
                                        html.td(team["Equipo"]),
                                    )
                                    for team in available_teams
                                    if isinstance(team, dict)
                                ]
                            ),
                        ),
                    ),
                ),
            ),
            html.footer(
                html.button({"className": "secondary", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
                html.button({"aria-busy": str(is_loading).lower(), "onClick": handle_save, "disabled": is_loading}, "Guardar"),
            ),
        ),
    )


@component
def DeleteButton(api_service: ApiClient, schedule_id: int, robot_id: int, on_delete_success: Callable):
    """Botón de borrado optimizado con mejor manejo de errores"""
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    is_deleting, set_is_deleting = use_state(False)

    async def delete_schedule(event):
        if is_deleting:
            return
        set_is_deleting(True)
        try:
            await api_service.delete_schedule(robot_id, schedule_id)
            show_notification("Programación eliminada.", "success")
            await on_delete_success()
        except Exception as e:
            print(str(e))
            show_notification(str(e), "error")
        finally:
            set_is_deleting(False)

    handle_click = use_callback(delete_schedule, [schedule_id, robot_id, is_deleting])

    return html.button(
        {"className": "secondary outline", "onClick": handle_click, "disabled": is_deleting, "aria-busy": is_deleting},
        "Eliminar",
    )


@component
def TeamSelector(available_teams: List[Dict], selected_teams: List[int], on_change: Callable):
    """Componente separado para la selección de equipos usando checkboxes"""

    safe_selected_teams = list(selected_teams) if selected_teams else []
    selected_teams_set = use_memo(lambda: set(safe_selected_teams), [safe_selected_teams])
    all_available_ids_set = use_memo(lambda: {team["EquipoId"] for team in available_teams}, [available_teams])
    are_all_teams_selected = use_memo(
        lambda: all_available_ids_set and all_available_ids_set.issubset(selected_teams_set), [selected_teams_set, all_available_ids_set]
    )

    def handle_select_all_teams(event):
        is_checked = event["target"]["checked"]
        new_teams = list(all_available_ids_set) if is_checked else []
        on_change(new_teams)

    def handle_team_select(team_id, checked):
        current_teams = set(safe_selected_teams)
        if checked:
            current_teams.add(team_id)
        else:
            current_teams.discard(team_id)
        on_change(list(current_teams))

    return html.fieldset(
        # Checkbox para seleccionar todos
        # html.legend("Asignar Equipos"),
        html.label(
            html.input({"type": "checkbox", "checked": are_all_teams_selected, "onChange": handle_select_all_teams}),
            "Asignar Equipos",
        ),
        html.div(
            {"style": {"maxHeight": "200px", "overflowY": "auto"}},
            *[
                html.label(
                    {"key": team["EquipoId"]},
                    html.input(
                        {
                            "type": "checkbox",
                            "checked": team["EquipoId"] in selected_teams_set,
                            "onChange": lambda e, tid=team["EquipoId"]: handle_team_select(tid, e["target"]["checked"]),
                        }
                    ),
                    team["Equipo"],
                )
                for team in available_teams
            ],
        ),
    )


@component
def ScheduleForm(form_data: Dict, available_teams: List[Dict], is_loading: bool, on_submit: Callable, on_cancel: Callable, on_change: Callable):
    """Componente separado para el formulario de programación"""

    tipo = form_data.get("TipoProgramacion")

    schedule_options = use_memo(
        lambda: [html.option({"value": schedule_type, "key": schedule_type}, schedule_type) for schedule_type in SCHEDULE_TYPES], []
    )

    def handle_form_change(field, value):
        on_change(field, value)

    def handle_team_change(teams):
        safe_teams = list(teams) if teams else []
        on_change("Equipos", safe_teams)

    return html._(
        html.form(
            {"id": "schedule-form", "onSubmit": event(on_submit, prevent_default=True)},
            # Fila 1: Tipo, Hora, Tolerancia
            html.label(
                "Tipo de Programación",
                html.select({"value": tipo, "onChange": lambda e: handle_form_change("TipoProgramacion", e["target"]["value"])}, *schedule_options),
            ),
            html.div(
                {"className": "grid"},
                html.label(
                    "Hora Inicio",
                    html.input(
                        {
                            "type": "time",
                            "value": form_data.get("HoraInicio"),
                            "onChange": lambda e: handle_form_change("HoraInicio", e["target"]["value"]),
                        }
                    ),
                ),
                html.label(
                    "Tolerancia (min)",
                    html.input(
                        {
                            "type": "number",
                            "min": "0",
                            "max": "60",
                            "value": form_data.get("Tolerancia"),
                            "onChange": lambda e: handle_form_change("Tolerancia", int(e["target"]["value"]) if e["target"]["value"] else 0),
                        }
                    ),
                ),
            ),
            # Campos condicionales según el tipo
            ConditionalFields(tipo, form_data, handle_form_change),
            # Selección de equipos
            TeamSelector(available_teams, form_data.get("Equipos", []), handle_team_change),
        ),
        html.footer(
            # Botones de acción
            html.div(
                {"className": "grid"},
                html.button({"type": "button", "className": "secondary", "onClick": lambda e: on_cancel(), "disabled": is_loading}, "Cancelar"),
                html.button({"type": "submit", "form": "schedule-form", "disabled": is_loading, "aria-busy": is_loading}, "Guardar"),
            ),
        ),
    )


@component
def ConditionalFields(tipo: str, form_data: Dict, on_change: Callable):
    """Campos condicionales según el tipo de programación"""

    if tipo == "Semanal":
        return html.label(
            "Días (ej: Lu,Ma,Mi)",
            html.input(
                {
                    "type": "text",
                    "value": form_data.get("DiasSemana", ""),
                    "onChange": lambda e: on_change("DiasSemana", e["target"]["value"]),
                }
            ),
        )
    elif tipo == "Mensual":
        return html.label(
            "Día del Mes",
            html.input(
                {
                    "type": "number",
                    "min": 1,
                    "max": 31,
                    "value": form_data.get("DiaDelMes", 1),
                    "onChange": lambda e: on_change("DiaDelMes", int(e["target"]["value"]) if e["target"]["value"] else 1),
                }
            ),
        )
    elif tipo == "Especifica":
        return html.label(
            "Fecha Específica",
            html.input(
                {
                    "type": "date",
                    "value": form_data.get("FechaEspecifica", ""),
                    "onChange": lambda e: on_change("FechaEspecifica", e["target"]["value"]),
                }
            ),
        )

    return html.div()


@component
def SchedulesModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    """Componente principal del modal optimizado"""
    api_service = get_api_client()
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]

    # Estados del componente
    view_mode, set_view_mode = use_state("list")
    schedules, set_schedules = use_state([])
    available_teams, set_available_teams = use_state([])
    form_data, set_form_data = use_state(DEFAULT_FORM_STATE)
    is_loading, set_is_loading = use_state(False)

    # Función para cargar datos
    @use_effect(dependencies=[robot])
    def load_data():
        if not robot:
            return

        async def fetch_data():
            set_is_loading(True)
            try:
                schedules_res, teams_res = await asyncio.gather(
                    api_service.get_robot_schedules(robot["RobotId"]), api_service.get_available_teams(robot["RobotId"])
                )
                set_schedules(schedules_res)
                set_available_teams(teams_res)
            except Exception as e:
                show_notification(str(e), "error")
            finally:
                set_is_loading(False)

        # Crear la tarea
        task = asyncio.create_task(fetch_data())

        # Función de limpieza
        def cleanup():
            if not task.done():
                task.cancel()

        return cleanup

    async def handle_successful_change():
        """Esta función se encarga de refrescar tanto el dashboard como el modal."""
        # Primero, refresca la lista principal de robots en el dashboard
        await on_save_success()
        # Luego, refresca la lista de programaciones dentro de este modal
        if robot:
            try:
                schedules_res, teams_res = await asyncio.gather(
                    api_service.get_robot_schedules(robot["RobotId"]), api_service.get_available_teams(robot["RobotId"])
                )
                set_schedules(schedules_res)
                set_available_teams(teams_res)
            except Exception as e:
                show_notification(str(e), "error")

    # Definir la función async para submit por separado
    async def submit_form(event):
        set_is_loading(True)
        if not form_data.get("Equipos"):
            show_notification("Debe seleccionar al menos un equipo.", "error")
            set_is_loading(False)
            return

        payload = {**form_data, "RobotId": robot["RobotId"]}

        try:
            if payload.get("ProgramacionId"):
                await api_service.update_schedule(payload["ProgramacionId"], payload)
                message = "Programación actualizada con éxito."
            else:
                await api_service.create_schedule(payload)
                message = "Programación creada con éxito."

            show_notification(message, "success")
            set_view_mode("list")
            # En lugar de llamar a on_save_success directamente, llamamos a nuestro nuevo handler
            await handle_successful_change()

        except Exception as e:
            show_notification(str(e), "error")
        finally:
            set_is_loading(False)

    handle_form_submit = use_callback(submit_form, [form_data, robot, on_save_success])

    def handle_edit_click(schedule_to_edit):
        equipos_ids = [team["EquipoId"] for team in schedule_to_edit.get("Equipos", [])]
        form_state = {
            "ProgramacionId": schedule_to_edit.get("ProgramacionId"),
            "TipoProgramacion": schedule_to_edit.get("TipoProgramacion", "Diaria"),
            "HoraInicio": (schedule_to_edit.get("HoraInicio") or "09:00")[:5],
            "Tolerancia": schedule_to_edit.get("Tolerancia", 60),
            "DiasSemana": schedule_to_edit.get("DiasSemana", ""),
            "DiaDelMes": schedule_to_edit.get("DiaDelMes", 1),
            "FechaEspecifica": (schedule_to_edit.get("FechaEspecifica") or "")[:10],
            "Equipos": equipos_ids,
        }
        set_form_data(form_state)
        set_view_mode("form")

    def handle_form_change(field, value):
        if field == "Equipos":
            value = list(value) if value else []
        set_form_data(lambda old: {**old, field: value})

    def handle_new_click():
        set_form_data(DEFAULT_FORM_STATE.copy())
        set_view_mode("form")

    def handle_cancel():
        set_view_mode("list")

    if not robot:
        return None

    return html.dialog(
        {"open": True},  # , "style": {"width": "90vw", "maxWidth": "800px", "font-size": "0.90rem"}},  # Modal más ancho
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": event(on_close, prevent_default=True)}),
                html.h2("Programación de Robots"),
                html.p(f"{robot.get('Robot', '')}"),
            ),
            # Contenido principal
            html._(
                SchedulesList(
                    api_service=api_service,
                    schedules=schedules,
                    robot_id=robot["RobotId"],
                    on_edit=handle_edit_click,
                    on_delete_success=handle_successful_change,
                )
                if view_mode == "list"
                else ScheduleForm(
                    form_data=form_data,
                    available_teams=available_teams,
                    is_loading=is_loading,
                    on_submit=handle_form_submit,
                    on_cancel=handle_cancel,
                    on_change=handle_form_change,
                ),
            ),
            # El footer solo es visible en la vista de lista
            html.footer(
                html.div(
                    {"className": "grid"},
                    html.div(),
                    html.button({"onClick": lambda e: handle_new_click()}, "Crear nueva programación"),
                )
            )
            if view_mode == "list"
            else None,
        ),
    )


@component
def SchedulesList(api_service: ApiClient, schedules: List[Dict], robot_id: int, on_edit: Callable, on_delete_success: Callable):
    def format_schedule_details(schedule):
        details = f"{schedule.get('TipoProgramacion', 'N/A')} a las {schedule.get('HoraInicio', '')}"
        if schedule.get("TipoProgramacion") == "Semanal":
            details += f" los días {schedule.get('DiasSemana', '')}"
        elif schedule.get("TipoProgramacion") == "Mensual":
            details += f" el día {schedule.get('DiaDelMes', '')} de cada mes"
        elif schedule.get("TipoProgramacion") == "Especifica":
            details += f" en la fecha {schedule.get('FechaEspecifica', '')}"
        return details

    rows = use_memo(
        lambda: [
            html.tr(
                {"key": s["ProgramacionId"]},
                html.td(format_schedule_details(s)),
                html.td(", ".join([team["Equipo"] for team in s.get("Equipos", [])]) or "Ninguno"),
                html.td(
                    html.div(
                        {"className": "grid"},
                        html.button({"className": "outline", "onClick": lambda e, sch=s: on_edit(sch)}, "Editar"),
                        DeleteButton(
                            api_service=api_service,
                            schedule_id=s["ProgramacionId"],
                            robot_id=robot_id,
                            on_delete_success=on_delete_success,
                        ),
                    ),
                ),
            )
            for s in schedules
        ],
        [schedules, robot_id, on_edit, on_delete_success],
    )

    return html.div(
        html.table(
            html.thead(html.tr(html.th("Detalles"), html.th("Equipos"), html.th("Acciones"))),
            html.tbody(rows if rows else html.tr(html.td({"colSpan": 3}, "No hay programaciones."))),
        ),
    )
