# src/interfaz_web/features/modals/dashboard_modal_components.py
import asyncio
from typing import Any, Callable, Dict, List

from reactpy import component, event, html, use_callback, use_context, use_effect, use_memo, use_state

from ...api_client import ApiClient, get_api_client
from ...shared.common_components import ConfirmationModal
from ...shared.notifications import NotificationContext

# --- Constantes y Estados por Defecto ---

DEFAULT_ROBOT_STATE = {
    "RobotId": None,
    "Robot": "",
    "Descripcion": "",
    "Activo": True,
    "EsOnline": False,
    "MinEquipos": 1,
    "MaxEquipos": -1,
    "PrioridadBalanceo": 100,
    "TicketsPorEquipoAdicional": 10,
}

SCHEDULE_TYPES = ["Diaria", "Semanal", "Mensual", "Especifica"]
DEFAULT_FORM_STATE = {
    "ProgramacionId": None,
    "TipoProgramacion": "Diaria",
    "HoraInicio": "09:00",
    "Tolerancia": 60,
    "DiasSemana": "Lu,Ma,Mi,Ju,Vi",
    "DiaDelMes": 1,
    "FechaEspecifica": "",
    "Equipos": [],
}


# --- Componentes de Modal ---


@component
def RobotEditModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    form_data, set_form_data = use_state(DEFAULT_ROBOT_STATE)
    is_loading, set_is_loading = use_state(False)
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    api_service = get_api_client()
    is_edit_mode = bool(robot and robot.get("RobotId") is not None)

    @use_effect(dependencies=[robot])
    def populate_form_data():
        if robot is not None:
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
                            html.output(form_data.get("MinEquipos", "0")),
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
                            html.output(form_data.get("MaxEquipos", "0")),
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
                            html.output({"className": "button"}, form_data.get("PrioridadBalanceo", "0")),
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
                            html.output(form_data.get("TicketsPorEquipoAdicional", "0")),
                            html.input(
                                {
                                    "id": "tickets",
                                    "type": "range",
                                    "min": "1",
                                    "max": "100",
                                    "value": form_data.get("TicketsPorEquipoAdicional", ""),
                                    "onChange": lambda e: handle_form_change(
                                        "TicketsPorEquipoAdicional", e["target"]["value"]
                                    ),
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
                    html.button(
                        {"type": "button", "className": "secondary", "onClick": on_close, "disabled": is_loading},
                        "Cancelar",
                    ),
                    html.button(
                        {
                            "type": "submit",
                            "form": "robot-form",
                            "aria-busy": str(is_loading).lower(),
                            "disabled": is_loading,
                        },
                        "Guardar",
                    ),
                )
            ),
        ),
    )


@component
def DeviceList(
    title: str,
    devices: List[Dict],
    selected_ids: List[int],
    on_selection_change: Callable,
    search_term: str,
    on_search_change: Callable,
):
    """
    Componente reutilizable que renderiza una lista de equipos con búsqueda y selección.
    """

    def handle_select_all(event):
        if event["target"]["checked"]:
            on_selection_change([device["EquipoId"] for device in devices])
        else:
            on_selection_change([])

    def handle_select_one(device_id, is_checked):
        current_ids = list(selected_ids)
        if is_checked:
            if device_id not in current_ids:
                current_ids.append(device_id)
        else:
            if device_id in current_ids:
                current_ids.remove(device_id)
        on_selection_change(current_ids)

    def get_estado(device: Dict) -> tuple[str, str]:
        if device.get("EsProgramado"):
            return ("Programado", "tag-programado")
        if device.get("Reservado"):
            return ("Reservado", "tag-reservado")
        return ("Dinámico", "tag-dinamico")

    has_status_column = devices and "EsProgramado" in devices[0]

    return html.div(
        html.h5(title),
        html.input(
            {
                "type": "search",
                "placeholder": "Filtrar equipos...",
                "value": search_term,
                "onChange": lambda e: on_search_change(e["target"]["value"]),
                "style": {"marginBottom": "0.5rem"},
            }
        ),
        html.div(
            {"style": {"height": "35vh", "overflowY": "auto", "fontSize": "0.90rem"}},
            html.table(
                html.thead(
                    html.tr(
                        html.th(html.input({"type": "checkbox", "onChange": handle_select_all})),
                        html.th("Nombre Equipo"),
                        html.th("Estado") if has_status_column else None,
                    )
                ),
                html.tbody(
                    *[
                        html.tr(
                            {"key": device["EquipoId"]},
                            html.td(
                                html.input(
                                    {
                                        "type": "checkbox",
                                        "checked": device["EquipoId"] in selected_ids,
                                        "onChange": lambda e, eid=device["EquipoId"]: handle_select_one(
                                            eid, e["target"]["checked"]
                                        ),
                                    }
                                )
                            ),
                            html.td(device["Equipo"]),
                            html.td(html.span({"className": f"tag {get_estado(device)[1]}"}, get_estado(device)[0]))
                            if has_status_column
                            else None,
                        )
                        for device in devices
                    ]
                    if devices
                    else html.tr(
                        html.td(
                            {"colSpan": 3 if has_status_column else 2, "style": {"textAlign": "center"}},
                            "No hay equipos para mostrar.",
                        )
                    )
                ),
            ),
        ),
    )


@component
def AssignmentsModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    assigned_devices, set_assigned_devices = use_state([])
    available_devices, set_available_devices = use_state([])
    is_loading, set_is_loading = use_state(False)

    selected_in_available, set_selected_in_available = use_state([])
    selected_in_assigned, set_selected_in_assigned = use_state([])

    # Nuevo estado para el modal de confirmación
    confirmation_data, set_confirmation_data = use_state(None)

    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    api_service = get_api_client()

    search_assigned, set_search_assigned = use_state("")
    search_available, set_search_available = use_state("")

    @use_effect(dependencies=[robot])
    def fetch_data():
        async def get_data():
            if not robot:
                return
            set_is_loading(True)
            set_selected_in_available([])
            set_selected_in_assigned([])
            set_search_assigned("")
            set_search_available("")
            try:
                assigned_res, available_res = await asyncio.gather(
                    api_service.get_robot_assignments(robot["RobotId"]),
                    api_service.get_available_devices(robot["RobotId"]),
                )
                set_assigned_devices(assigned_res)
                set_available_devices(available_res)
            except Exception as e:
                show_notification(f"Error al cargar datos: {e}", "error")
            finally:
                set_is_loading(False)

        asyncio.create_task(get_data())

    filtered_assigned = use_memo(
        lambda: [device for device in assigned_devices if search_assigned.lower() in device.get("Equipo", "").lower()],
        [assigned_devices, search_assigned],
    )
    filtered_available = use_memo(
        lambda: [
            device for device in available_devices if search_available.lower() in device.get("Equipo", "").lower()
        ],
        [available_devices, search_available],
    )

    def move_items(source_list, set_source, dest_list, set_dest, selected_ids, clear_selection):
        items_to_move = {item["EquipoId"]: item for item in source_list if item["EquipoId"] in selected_ids}
        set_dest(sorted(dest_list + list(items_to_move.values()), key=lambda x: x["Equipo"]))
        set_source([item for item in source_list if item["EquipoId"] not in items_to_move])
        clear_selection([])

    async def execute_save():
        """Función que ejecuta el guardado después de la confirmación."""
        if not confirmation_data:
            return
        set_is_loading(True)
        try:
            ids_to_assign, ids_to_unassign = confirmation_data["assign"], confirmation_data["unassign"]
            await api_service.update_robot_assignments(robot["RobotId"], ids_to_assign, ids_to_unassign)
            await on_save_success()
            show_notification("Se actualizó la asignación correctamente", "success")
            on_close()
        except Exception as e:
            show_notification(f"Error al guardar: {e}", "error")
        finally:
            set_is_loading(False)
            set_confirmation_data(None)

    async def handle_save(event_data):
        original_assigned_ids_set = {t["EquipoId"] for t in (await api_service.get_robot_assignments(robot["RobotId"]))}
        current_assigned_ids_set = {t["EquipoId"] for t in assigned_devices}

        ids_to_assign = list(current_assigned_ids_set - original_assigned_ids_set)
        ids_to_unassign = list(original_assigned_ids_set - current_assigned_ids_set)

        if not ids_to_assign and not ids_to_unassign:
            on_close()
            return

        # Abre el modal de confirmación si hay cambios que guardar.
        set_confirmation_data({"assign": ids_to_assign, "unassign": ids_to_unassign})

    if not robot:
        return None

    return html.dialog(
        {"open": True, "style": {"width": "90vw", "maxWidth": "1000px"}},
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": event(on_close, prevent_default=True)}),
                html.h2("Asignación de Equipos"),
                html.p(f"Robot: {robot.get('Robot', '')}"),
            ),
            html.div(
                {
                    "className": "grid",
                    "style": {"gridTemplateColumns": "5fr 1fr 5fr", "alignItems": "center", "gap": "1rem"},
                },
                DeviceList(
                    title="Equipos Disponibles",
                    devices=filtered_available,
                    selected_ids=selected_in_available,
                    on_selection_change=set_selected_in_available,
                    search_term=search_available,
                    on_search_change=set_search_available,
                ),
                html.div(
                    {"style": {"display": "flex", "flexDirection": "column", "gap": "1rem"}},
                    html.button(
                        {
                            "onClick": lambda e: move_items(
                                available_devices,
                                set_available_devices,
                                assigned_devices,
                                set_assigned_devices,
                                selected_in_available,
                                set_selected_in_available,
                            ),
                            "disabled": not selected_in_available,
                            "data-tooltip": "Asignar seleccionados",
                        },
                        "->",
                    ),
                    html.button(
                        {
                            "onClick": lambda e: move_items(
                                assigned_devices,
                                set_assigned_devices,
                                available_devices,
                                set_available_devices,
                                selected_in_assigned,
                                set_selected_in_assigned,
                            ),
                            "disabled": not selected_in_assigned,
                            "data-tooltip": "Desasignar seleccionados",
                        },
                        "<-",
                    ),
                ),
                DeviceList(
                    title="Equipos Asignados",
                    devices=filtered_assigned,
                    selected_ids=selected_in_assigned,
                    on_selection_change=set_selected_in_assigned,
                    search_term=search_assigned,
                    on_search_change=set_search_assigned,
                ),
            ),
            html.footer(
                html.button({"className": "secondary", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
                html.button(
                    {"aria-busy": str(is_loading).lower(), "onClick": handle_save, "disabled": is_loading}, "Guardar"
                ),
            ),
        ),
        # Añadir el modal de confirmación
        ConfirmationModal(
            is_open=bool(confirmation_data),
            title="Confirmar Cambios",
            message="¿Estás seguro de que quieres modificar las asignaciones de equipos para este robot?",
            on_confirm=execute_save,
            on_cancel=lambda: set_confirmation_data(None),
        ),
    )


@component
def SchedulesModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    api_service = get_api_client()
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    view_mode, set_view_mode = use_state("list")
    schedules, set_schedules = use_state([])
    available_devices, set_available_devices = use_state([])
    form_data, set_form_data = use_state(DEFAULT_FORM_STATE)
    is_loading, set_is_loading = use_state(False)

    @use_effect(dependencies=[robot])
    def load_data():
        if not robot:
            return
        task = asyncio.create_task(fetch_schedule_data())
        return lambda: task.cancel()

    async def fetch_schedule_data():
        set_is_loading(True)
        try:
            schedules_res, devices_res = await asyncio.gather(
                api_service.get_robot_schedules(robot["RobotId"]), api_service.get_available_devices(robot["RobotId"])
            )
            set_schedules(schedules_res)
            set_available_devices(devices_res)
        except Exception as e:
            show_notification(str(e), "error")
        finally:
            set_is_loading(False)

    async def handle_successful_change():
        await on_save_success()
        if robot:
            await fetch_schedule_data()

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
            await handle_successful_change()
        except Exception as e:
            show_notification(str(e), "error")
        finally:
            set_is_loading(False)

    handle_form_submit = use_callback(submit_form, [form_data, robot, on_save_success])

    def handle_edit_click(schedule_to_edit):
        equipos_ids = [device["EquipoId"] for device in schedule_to_edit.get("Equipos", [])]
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
        {"open": True},
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": event(on_close, prevent_default=True)}),
                html.h2("Programación de Robots"),
                html.p(f"{robot.get('Robot', '')}"),
            ),
            html._(
                SchedulesList(
                    api_service=api_service,
                    robot_id=robot["RobotId"],
                    robot_nombre=robot["Robot"],
                    schedules=schedules,
                    on_edit=handle_edit_click,
                    on_delete_success=handle_successful_change,
                )
                if view_mode == "list"
                else ScheduleForm(
                    form_data=form_data,
                    available_devices=available_devices,
                    is_loading=is_loading,
                    on_submit=handle_form_submit,
                    on_cancel=handle_cancel,
                    on_change=handle_form_change,
                ),
            ),
            html.footer(html.button({"onClick": lambda e: handle_new_click()}, "Crear nueva programación"))
            if view_mode == "list"
            else None,
        ),
    )


@component
def SchedulesList(
    api_service: ApiClient,
    robot_id: int,
    robot_nombre: str,
    schedules: List[Dict],
    on_edit: Callable,
    on_delete_success: Callable,
):
    notification_ctx = use_context(NotificationContext)
    show_notification = notification_ctx["show_notification"]
    schedule_to_delete, set_schedule_to_delete = use_state(None)

    def format_schedule_details(schedule):
        details = f"{schedule.get('TipoProgramacion', 'N/A')} a las {schedule.get('HoraInicio', '')}"
        tipo = schedule.get("TipoProgramacion")
        if tipo == "Semanal":
            details += f" los días {schedule.get('DiasSemana', '')}"
        elif tipo == "Mensual":
            details += f" el día {schedule.get('DiaDelMes', '')} de cada mes"
        elif tipo == "Especifica":
            details += f" en la fecha {schedule.get('FechaEspecifica', '')}"
        return details

    async def handle_confirm_delete():
        if not schedule_to_delete:
            return
        try:
            await api_service.delete_schedule(schedule_to_delete["ProgramacionId"], robot_id)
            show_notification("Programación eliminada.", "success")
            await on_delete_success()
        except Exception as e:
            show_notification(str(e), "error")
        finally:
            set_schedule_to_delete(None)

    rows = use_memo(
        lambda: [
            html.tr(
                {"key": s["ProgramacionId"]},
                html.td(format_schedule_details(s)),
                html.td(", ".join([device["Equipo"] for device in s.get("Equipos", [])]) or "Ninguno"),
                html.td(
                    html.div(
                        {"className": "grid"},
                        html.button({"className": "outline", "onClick": lambda e, sch=s: on_edit(sch)}, "Editar"),
                        html.button(
                            {"className": "secondary outline", "onClick": lambda e, sch=s: set_schedule_to_delete(sch)},
                            "Eliminar",
                        ),
                    )
                ),
            )
            for s in schedules
        ],
        [schedules, on_edit, on_delete_success],
    )
    return html._(
        html.table(
            html.thead(html.tr(html.th("Detalles"), html.th("Equipos"), html.th("Acciones"))),
            html.tbody(
                rows
                if rows
                else html.tr(html.td({"colSpan": 3, "style": {"textAlign": "center"}}, "No hay programaciones."))
            ),
        ),
        ConfirmationModal(
            is_open=bool(schedule_to_delete),
            title="Confirmar Eliminación",
            message=f"¿Estás seguro de que quieres eliminar la programación para '{robot_nombre}'?",
            on_confirm=handle_confirm_delete,
            on_cancel=lambda: set_schedule_to_delete(None),
        ),
    )


@component
def ScheduleForm(
    form_data: Dict,
    available_devices: List[Dict],
    is_loading: bool,
    on_submit: Callable,
    on_cancel: Callable,
    on_change: Callable,
):
    tipo = form_data.get("TipoProgramacion")
    schedule_options = use_memo(
        lambda: [
            html.option({"value": schedule_type, "key": schedule_type}, schedule_type)
            for schedule_type in SCHEDULE_TYPES
        ],
        [],
    )

    def handle_form_change(field, value):
        on_change(field, value)

    def handle_device_change(devices):
        on_change("Equipos", list(devices) if devices else [])

    return html._(
        html.form(
            {"id": "schedule-form", "onSubmit": event(on_submit, prevent_default=True)},
            html.label(
                "Tipo de Programación",
                html.select(
                    {"value": tipo, "onChange": lambda e: handle_form_change("TipoProgramacion", e["target"]["value"])},
                    *schedule_options,
                ),
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
                            "onChange": lambda e: handle_form_change(
                                "Tolerancia", int(e["target"]["value"]) if e["target"]["value"] else 0
                            ),
                        }
                    ),
                ),
            ),
            ConditionalFields(tipo, form_data, handle_form_change),
            DeviceSelector(available_devices, form_data.get("Equipos", []), handle_device_change),
        ),
        html.footer(
            html.div(
                {"className": "grid"},
                html.button(
                    {
                        "type": "button",
                        "className": "secondary",
                        "onClick": lambda e: on_cancel(),
                        "disabled": is_loading,
                    },
                    "Cancelar",
                ),
                html.button(
                    {"type": "submit", "form": "schedule-form", "disabled": is_loading, "aria-busy": is_loading},
                    "Guardar",
                ),
            )
        ),
    )


@component
def ConditionalFields(tipo: str, form_data: Dict, on_change: Callable):
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
                    "onChange": lambda e: on_change(
                        "DiaDelMes", int(e["target"]["value"]) if e["target"]["value"] else 1
                    ),
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
def DeviceSelector(available_devices: List[Dict], selected_devices: List[int], on_change: Callable):
    safe_selected_devices = selected_devices or []
    all_available_ids = use_memo(lambda: [device["EquipoId"] for device in available_devices], [available_devices])
    are_all_devices_selected = len(safe_selected_devices) > 0 and all(
        item in safe_selected_devices for item in all_available_ids
    )

    def handle_select_all_devices(event):
        on_change(all_available_ids if event["target"]["checked"] else [])

    def handle_device_select(device_id, checked):
        current_devices = list(safe_selected_devices)
        if checked:
            if device_id not in current_devices:
                current_devices.append(device_id)
        else:
            if device_id in current_devices:
                current_devices.remove(device_id)
        on_change(current_devices)

    return html.fieldset(
        html.label(
            html.input(
                {"type": "checkbox", "checked": are_all_devices_selected, "onChange": handle_select_all_devices}
            ),
            "Asignar Equipos",
        ),
        html.div(
            {"style": {"maxHeight": "200px", "overflowY": "auto"}},
            *[
                html.label(
                    {"key": device["EquipoId"]},
                    html.input(
                        {
                            "type": "checkbox",
                            "checked": device["EquipoId"] in safe_selected_devices,
                            "onChange": lambda e, tid=device["EquipoId"]: handle_device_select(
                                tid, e["target"]["checked"]
                            ),
                        }
                    ),
                    device["Equipo"],
                )
                for device in available_devices
            ],
        ),
    )
