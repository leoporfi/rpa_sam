# src/interfaz_web/service/main.py

import asyncio
from datetime import date
from functools import partial

import reactpy
from reactpy import component, html, use_effect, use_state

# Importar los módulos comunes de SAM
from common.database.sql_client import DatabaseConnector
from common.utils.config_manager import ConfigManager

# --- Conexión a la Base de Datos ---
try:
    cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
    db = DatabaseConnector(
        servidor=cfg_sql_sam["server"], base_datos=cfg_sql_sam["database"], usuario=cfg_sql_sam["uid"], contrasena=cfg_sql_sam["pwd"]
    )
    print("INFO: Conexión a la base de datos SAM establecida para la interfaz web.")
except Exception as e:
    db = None
    print(f"ERROR CRÍTICO: No se pudo conectar a la base de datos SAM: {e}")


# --- Componente del Formulario de Edición (Modal) ---
@component
def RobotEditForm(robot, on_save, on_cancel):
    form_data, set_form_data = use_state(robot)

    def handle_change(field_name, event):
        value = event["target"]["value"]
        set_form_data(lambda old: {**old, field_name: value})

    async def handle_submit_form_data(event):
        await on_save(form_data)

    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content"},
            html.h2(f"Editando Robot: {robot['Robot']}"),
            html.div(
                {"class_name": "form-group"},
                html.label("Prioridad Balanceo:"),
                html.input(
                    {
                        "type": "number",
                        "name": "PrioridadBalanceo",
                        "value": form_data.get("PrioridadBalanceo", ""),
                        "on_change": partial(handle_change, "PrioridadBalanceo"),
                    }
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Min Equipos:"),
                html.input(
                    {
                        "type": "number",
                        "name": "MinEquipos",
                        "value": form_data.get("MinEquipos", ""),
                        "on_change": partial(handle_change, "MinEquipos"),
                    }
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Max Equipos (-1 para ilimitado):"),
                html.input(
                    {
                        "type": "number",
                        "name": "MaxEquipos",
                        "value": form_data.get("MaxEquipos", ""),
                        "on_change": partial(handle_change, "MaxEquipos"),
                    }
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Tickets por Equipo Adicional:"),
                html.input(
                    {
                        "type": "number",
                        "name": "TicketsPorEquipoAdicional",
                        "value": form_data.get("TicketsPorEquipoAdicional") or "",
                        "on_change": partial(handle_change, "TicketsPorEquipoAdicional"),
                    }
                ),
            ),
            html.div(
                {"class_name": "modal-actions"},
                html.button({"on_click": handle_submit_form_data, "class_name": "btn-accion"}, "Guardar Cambios"),
                html.button({"on_click": on_cancel}, "Cancelar"),
            ),
        ),
    )


# --- Componente para Crear Programaciones ---
@component
def ScheduleCreateForm(robot, equipos_disponibles, on_save, on_cancel):
    initial_form_data = {
        "tipo": "Diaria",
        "hora_inicio": "09:00:00",
        "equipo_ids": [],
        "dias_semana": "LU,MA,MI,JU,VI",
        "dia_mes": 1,
        "fecha_especifica": date.today().isoformat(),
        "tolerancia": 60,
    }
    form_data, set_form_data = use_state(initial_form_data)

    def handle_regular_input_change(field_name, event):
        value = event["target"]["value"]
        set_form_data(lambda old: {**old, field_name: value})

    def handle_team_selection_change(team_id_clicked, is_checked):
        current_team_ids = form_data.get("equipo_ids", [])
        if is_checked:
            if team_id_clicked not in current_team_ids:
                new_team_ids = sorted(current_team_ids + [team_id_clicked])
                set_form_data(lambda old: {**old, "equipo_ids": new_team_ids})
        else:
            new_team_ids = [tid for tid in current_team_ids if tid != team_id_clicked]
            set_form_data(lambda old: {**old, "equipo_ids": new_team_ids})

    async def handle_submit_form_data(event):
        await on_save(robot, form_data)

    dynamic_fields = []
    if form_data.get("tipo") == "Semanal":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "dias"},
                html.label("Días Semana (LU,MA,MI...):"),
                html.input(
                    {
                        "type": "text",
                        "name": "dias_semana",
                        "value": form_data.get("dias_semana", "LU,MA,MI,JU,VI"),
                        "on_change": partial(handle_regular_input_change, "dias_semana"),
                    }
                ),
            )
        )
    elif form_data.get("tipo") == "Mensual":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "dia_mes"},
                html.label("Día del Mes:"),
                html.input(
                    {
                        "type": "number",
                        "name": "dia_mes",
                        "value": form_data.get("dia_mes", 1),
                        "on_change": partial(handle_regular_input_change, "dia_mes"),
                    }
                ),
            )
        )
    elif form_data.get("tipo") == "Especifica":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "fecha"},
                html.label("Fecha Específica:"),
                html.input(
                    {
                        "type": "date",
                        "name": "fecha_especifica",
                        "value": form_data.get("fecha_especifica", date.today().isoformat()),
                        "on_change": partial(handle_regular_input_change, "fecha_especifica"),
                    }
                ),
            )
        )

    team_checkbox_elements = (
        [
            html.div(
                {"key": f"schedule-team-{eq['EquipoId']}", "class_name": "checkbox-item"},
                html.input(
                    {
                        "type": "checkbox",
                        "id": f"schedule-team-cb-{eq['EquipoId']}",
                        "checked": eq["EquipoId"] in form_data.get("equipo_ids", []),
                        "on_change": lambda event, team_id=eq["EquipoId"]: handle_team_selection_change(team_id, event["target"]["checked"]),
                    }
                ),
                html.label({"for": f"schedule-team-cb-{eq['EquipoId']}"}, f" {eq['Equipo']}"),
            )
            for eq in equipos_disponibles
        ]
        if equipos_disponibles
        else [html.p("No hay equipos disponibles.")]
    )

    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content"},
            html.h2(f"Programar Robot: {robot['Robot']}"),
            html.div(
                {"class_name": "form-group"},
                html.label("Tipo de Programación:"),
                html.select(
                    {"name": "tipo", "value": form_data.get("tipo", "Diaria"), "on_change": partial(handle_regular_input_change, "tipo")},
                    html.option({"value": "Diaria"}, "Diaria"),
                    html.option({"value": "Semanal"}, "Semanal"),
                    html.option({"value": "Mensual"}, "Mensual"),
                    html.option({"value": "Especifica"}, "Específica"),
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Equipos Exclusivos:"),
                html.div(
                    {
                        "class_name": "teams-checkbox-list",
                        "style": {
                            "max_height": "150px",
                            "overflow_y": "auto",
                            "border": "1px solid #ced4da",
                            "padding": "10px",
                            "border_radius": "4px",
                        },
                    },
                    team_checkbox_elements,
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Hora Inicio (HH:MM:SS):"),
                html.input(
                    {
                        "type": "text",
                        "name": "hora_inicio",
                        "value": form_data.get("hora_inicio", "09:00:00"),
                        "on_change": partial(handle_regular_input_change, "hora_inicio"),
                        "placeholder": "HH:MM:SS",
                    }
                ),
            ),
            *dynamic_fields,
            html.div(
                {"class_name": "form-group"},
                html.label("Tolerancia (minutos):"),
                html.input(
                    {
                        "type": "number",
                        "name": "tolerancia",
                        "value": form_data.get("tolerancia", 60),
                        "on_change": partial(handle_regular_input_change, "tolerancia"),
                    }
                ),
            ),
            html.div(
                {"class_name": "modal-actions"},
                html.button(
                    {"on_click": handle_submit_form_data, "class_name": "btn-accion", "disabled": not form_data.get("equipo_ids")},
                    "Guardar Programación",
                ),
                html.button({"on_click": on_cancel}, "Cancelar"),
            ),
        ),
    )


# --- Componente para Editar Programaciones ---
@component
def ScheduleEditForm(schedule_to_edit, equipos_disponibles_all, on_save, on_cancel):
    initial_form_data_state, set_initial_form_data_state = use_state(None)
    form_data, set_form_data = use_state({})

    @use_effect(dependencies=[schedule_to_edit, equipos_disponibles_all])
    def _init_form():
        if not schedule_to_edit:
            set_form_data({})
            set_initial_form_data_state("empty")
            return
        # Obtenemos el valor de la hora
        hora_inicio_val = schedule_to_edit.get("HoraInicio") or schedule_to_edit.get("HorasInicio")
        # Si es un objeto de tiempo, lo convertimos a string. Si no, lo usamos como está.
        if hasattr(hora_inicio_val, "isoformat"):
            hora_inicio_str = hora_inicio_val.isoformat()
        else:
            hora_inicio_str = str(hora_inicio_val or "09:00:00")

        current_team_names = (
            [name.strip() for name in schedule_to_edit.get("EquiposProgramados", "").split(",") if name.strip()]
            if schedule_to_edit.get("EquiposProgramados")
            else []
        )
        current_team_ids = []
        if equipos_disponibles_all:
            equipos_map_name_to_id = {eq["Equipo"].upper().strip(): eq["EquipoId"] for eq in equipos_disponibles_all}
            for name in current_team_names:
                team_id = equipos_map_name_to_id.get(name.upper().strip())
                if team_id is not None:
                    current_team_ids.append(team_id)

        data_for_form = {
            "tipo": schedule_to_edit.get("TipoProgramacion") or "Diaria",
            "hora_inicio": hora_inicio_str,  # Usamos el string convertido
            "equipo_ids": current_team_ids,
            "dias_semana": schedule_to_edit.get("DiasSemana") or "LU,MA,MI,JU,VI",
            "dia_mes": schedule_to_edit.get("DiaDelMes") or 1,
            "fecha_especifica": schedule_to_edit.get("FechaEspecifica") or date.today().isoformat(),
            "tolerancia": schedule_to_edit.get("Tolerancia") if schedule_to_edit.get("Tolerancia") is not None else 60,
        }
        set_form_data(data_for_form)
        set_initial_form_data_state("loaded")

    if initial_form_data_state is None:
        return html.div({"class_name": "modal-overlay"}, html.div({"class_name": "modal-content"}, "Cargando..."))
    if initial_form_data_state == "empty":
        return html.div({"class_name": "modal-overlay"}, html.div({"class_name": "modal-content"}, "Error: Datos no disponibles."))

    def handle_regular_input_change(field_name, event):
        value = event["target"]["value"]
        set_form_data(lambda old: {**old, field_name: value})

    def handle_team_selection_change(team_id_clicked, is_checked):
        current_ids = form_data.get("equipo_ids", [])
        new_team_ids = (
            sorted(current_ids + [team_id_clicked])
            if is_checked and team_id_clicked not in current_ids
            else [tid for tid in current_ids if tid != team_id_clicked]
        )
        set_form_data(lambda old: {**old, "equipo_ids": new_team_ids})

    async def handle_submit_form_data(event):
        await on_save(schedule_to_edit["ProgramacionId"], form_data)

    dynamic_fields = []
    current_tipo = form_data.get("tipo", "Diaria")
    if current_tipo == "Semanal":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "dias"},
                html.label("Días Semana (LU,MA,MI...):"),
                html.input(
                    {
                        "type": "text",
                        "name": "dias_semana",
                        "value": form_data.get("dias_semana", ""),
                        "on_change": partial(handle_regular_input_change, "dias_semana"),
                    }
                ),
            )
        )
    elif current_tipo == "Mensual":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "dia_mes"},
                html.label("Día del Mes:"),
                html.input(
                    {
                        "type": "number",
                        "name": "dia_mes",
                        "value": form_data.get("dia_mes", 1),
                        "on_change": partial(handle_regular_input_change, "dia_mes"),
                    }
                ),
            )
        )
    elif current_tipo == "Especifica":
        dynamic_fields.append(
            html.div(
                {"class_name": "form-group", "key": "fecha"},
                html.label("Fecha Específica:"),
                html.input(
                    {
                        "type": "date",
                        "name": "fecha_especifica",
                        "value": form_data.get("fecha_especifica", date.today().isoformat()),
                        "on_change": partial(handle_regular_input_change, "fecha_especifica"),
                    }
                ),
            )
        )

    robot_display_name = schedule_to_edit.get("RobotName", f"Robot ID: {schedule_to_edit.get('RobotId', 'N/A')}")
    team_checkbox_elements = (
        [
            html.div(
                {"key": f"schedule-edit-team-{eq['EquipoId']}", "class_name": "checkbox-item"},
                html.input(
                    {
                        "type": "checkbox",
                        "id": f"schedule-edit-team-cb-{eq['EquipoId']}",
                        "checked": eq["EquipoId"] in form_data.get("equipo_ids", []),
                        "on_change": lambda event, team_id=eq["EquipoId"]: handle_team_selection_change(team_id, event["target"]["checked"]),
                    }
                ),
                html.label({"for": f"schedule-edit-team-cb-{eq['EquipoId']}"}, f" {eq['Equipo']}"),
            )
            for eq in equipos_disponibles_all
        ]
        if equipos_disponibles_all
        else [html.p("No hay equipos disponibles.")]
    )

    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content schedule-edit-form-modal"},
            html.h2(f"Editando Programación ID: {schedule_to_edit.get('ProgramacionId', 'N/A')} para {robot_display_name}"),
            html.div(
                {"class_name": "form-group"},
                html.label("Tipo de Programación:"),
                html.select(
                    {"name": "tipo", "value": form_data.get("tipo", "Diaria"), "on_change": partial(handle_regular_input_change, "tipo")},
                    html.option({"value": "Diaria"}, "Diaria"),
                    html.option({"value": "Semanal"}, "Semanal"),
                    html.option({"value": "Mensual"}, "Mensual"),
                    html.option({"value": "Especifica"}, "Específica"),
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Equipos Exclusivos:"),
                html.div(
                    {
                        "class_name": "teams-checkbox-list",
                        "style": {
                            "max_height": "150px",
                            "overflow_y": "auto",
                            "border": "1px solid #ced4da",
                            "padding": "10px",
                            "border_radius": "4px",
                        },
                    },
                    team_checkbox_elements,
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Hora Inicio (HH:MM:SS):"),
                html.input(
                    {
                        "type": "text",
                        "name": "hora_inicio",
                        "value": form_data.get("hora_inicio", "09:00:00"),
                        "on_change": partial(handle_regular_input_change, "hora_inicio"),
                        "placeholder": "HH:MM:SS",
                    }
                ),
            ),
            *dynamic_fields,
            html.div(
                {"class_name": "form-group"},
                html.label("Tolerancia (minutos):"),
                html.input(
                    {
                        "type": "number",
                        "name": "tolerancia",
                        "value": form_data.get("tolerancia", 60),
                        "on_change": partial(handle_regular_input_change, "tolerancia"),
                    }
                ),
            ),
            html.div(
                {"class_name": "modal-actions"},
                html.button(
                    {"on_click": handle_submit_form_data, "class_name": "btn-accion", "disabled": not form_data.get("equipo_ids")}, "Guardar Cambios"
                ),
                html.button({"on_click": on_cancel}, "Cancelar"),
            ),
        ),
    )


# --- Componente para Visualizar Programaciones ---
@component
def ViewSchedulesModal(robot_for_schedules, schedules_list, on_cancel, on_edit_schedule, on_delete_schedule):
    if not robot_for_schedules:
        return html.div()
    header = f"Programaciones para Robot: {robot_for_schedules['Robot']}"
    table_header = html.thead(
        html.tr(
            html.th("ID"), html.th("Tipo"), html.th("Activación"), html.th("Equipos Programados"), html.th("Tolerancia (min)"), html.th("Acciones")
        )
    )
    rows = []
    if not schedules_list:
        rows.append(html.tr(html.td({"colSpan": 6}, "Este robot no tiene programaciones.")))
    else:
        for schedule in schedules_list:
            activation_details = ""
            tipo = schedule.get("TipoProgramacion")
            hi = schedule.get("HoraInicio") or schedule.get("HorasInicio", "N/A")  # Prioritize HoraInicio from Programaciones table

            if tipo == "Diaria":
                activation_details = f"Todos los días a las {hi}"
            elif tipo == "Semanal":
                activation_details = f"{schedule.get('DiasSemana', 'N/A')} a las {hi}"
            elif tipo == "Mensual":
                activation_details = f"Día {schedule.get('DiaDelMes', 'N/A')} del mes a las {hi}"
            elif tipo == "Especifica":
                activation_details = f"Fecha {schedule.get('FechaEspecifica', 'N/A')} a las {hi}"  # Corrected to FechaEspecifica
            else:
                activation_details = "Desconocida"
            rows.append(
                html.tr(
                    {"key": schedule["ProgramacionId"]},
                    html.td(schedule["ProgramacionId"]),
                    html.td(tipo or "N/A"),
                    html.td(activation_details),
                    html.td(schedule.get("EquiposProgramados") or "Ninguno"),
                    html.td(schedule.get("Tolerancia", "N/A")),
                    html.td(
                        html.button(
                            {"on_click": lambda event, s=schedule: asyncio.ensure_future(on_edit_schedule(s)), "class_name": "btn-accion-secundario"},
                            "Editar",
                        ),
                        html.button(
                            {
                                "on_click": lambda event, pid=schedule["ProgramacionId"]: asyncio.ensure_future(on_delete_schedule(pid)),
                                "class_name": "btn-accion-peligro",
                            },
                            "Eliminar",
                        ),
                    ),
                )
            )
    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content view-schedules-modal", "style": {"width": "80%", "max_width": "900px"}},
            html.h2(header),
            html.table({"class_name": "sam-table"}, table_header, html.tbody(rows)),
            html.div({"class_name": "modal-actions"}, html.button({"on_click": on_cancel}, "Cerrar")),
        ),
    )


# --- Componente para Desasignar Equipos ---
@component
def DeassignmentForm(robot_for_deassignment, teams_for_deassignment, on_save, on_cancel):
    selected_team_ids_to_deassign, set_selected_team_ids_to_deassign = use_state([])

    def handle_team_selection_change(team_id, event):
        is_checked = event["target"]["checked"]
        current_ids = selected_team_ids_to_deassign
        if is_checked:
            if team_id not in current_ids:
                set_selected_team_ids_to_deassign(sorted(current_ids + [team_id]))
        else:
            set_selected_team_ids_to_deassign([tid for tid in current_ids if tid != team_id])

    async def handle_submit(event):
        await on_save(robot_for_deassignment["RobotId"], selected_team_ids_to_deassign)

    modal_title = f"Desasignar Equipos del Robot: {robot_for_deassignment['Robot']}" if robot_for_deassignment else "Desasignar Equipos"
    team_checkboxes = (
        [
            html.div(
                {"key": f"deassign-team-{team['EquipoId']}", "class_name": "checkbox-item"},
                html.input(
                    {
                        "type": "checkbox",
                        "id": f"deassign-team-cb-{team['EquipoId']}",
                        "checked": team["EquipoId"] in selected_team_ids_to_deassign,
                        "on_change": lambda event, tid=team["EquipoId"]: handle_team_selection_change(tid, event),
                    }
                ),
                html.label({"for": f"deassign-team-cb-{team['EquipoId']}"}, f" {team['Equipo']}"),
            )
            for team in teams_for_deassignment
        ]
        if teams_for_deassignment
        else [html.p("No hay equipos asignados manualmente a este robot.")]
    )
    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content deassignment-form-modal"},
            html.h2({"class_name": "modal-title"}, modal_title),
            html.div(
                {"class_name": "form-group"},
                html.label("Seleccionar Equipos a desasignar:"),
                html.div(
                    {
                        "class_name": "teams-checkbox-list",
                        "style": {
                            "max_height": "250px",
                            "overflow_y": "auto",
                            "border": "1px solid #ced4da",
                            "padding": "10px",
                            "border_radius": "4px",
                        },
                    },
                    team_checkboxes,
                ),
            ),
            html.div(
                {"class_name": "modal-actions"},
                html.button(
                    {"on_click": handle_submit, "class_name": "btn-accion-peligro", "disabled": not selected_team_ids_to_deassign},
                    "Desasignar Seleccionados",
                ),
                html.button({"on_click": on_cancel, "class_name": "btn-accion-secundario"}, "Cancelar"),
            ),
        ),
    )


# --- Componente para Asignar Robot a Equipos ---
@component
def AssignmentForm(robots, available_teams, on_save, on_cancel):
    selected_robot_id, set_selected_robot_id = use_state("")
    selected_team_ids, set_selected_team_ids = use_state([])

    def handle_robot_change(event):
        set_selected_robot_id(event["target"]["value"])

    def handle_team_selection_change(team_id, event):
        is_checked = event["target"]["checked"]
        if is_checked:
            set_selected_team_ids(lambda old_ids: sorted(old_ids + [team_id] if team_id not in old_ids else old_ids))
        else:
            set_selected_team_ids(lambda old_ids: [tid for tid in old_ids if tid != team_id])

    async def handle_submit(event):
        await on_save(selected_robot_id, selected_team_ids)

    robot_options = [html.option({"value": ""}, "Seleccione un robot")] + [html.option({"value": r["RobotId"]}, r["Robot"]) for r in robots]
    team_checkboxes = (
        [
            html.div(
                {"key": f"assign-team-{team['EquipoId']}", "class_name": "checkbox-item"},
                html.input(
                    {
                        "type": "checkbox",
                        "id": f"assign-team-cb-{team['EquipoId']}",
                        "checked": team["EquipoId"] in selected_team_ids,
                        "on_change": lambda event, tid=team["EquipoId"]: handle_team_selection_change(tid, event),
                    }
                ),
                html.label({"for": f"assign-team-cb-{team['EquipoId']}"}, f" {team['Equipo']}"),
            )
            for team in available_teams
        ]
        if available_teams
        else [html.p("No hay equipos disponibles para asignación.")]
    )

    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content assignment-form-modal"},
            html.h2({"class_name": "modal-title"}, "Asignar Robot a Equipos"),
            html.div(
                {"class_name": "form-group"},
                html.label({"for": "robot_select_assignment"}, "Seleccionar Robot:"),
                html.select(
                    {"id": "robot_select_assignment", "value": selected_robot_id, "on_change": handle_robot_change, "class_name": "form-control"},
                    robot_options,
                ),
            ),
            html.div(
                {"class_name": "form-group"},
                html.label("Seleccionar Equipos Disponibles:"),
                html.div(
                    {
                        "class_name": "teams-checkbox-list",
                        "style": {
                            "max_height": "250px",
                            "overflow_y": "auto",
                            "border": "1px solid #ced4da",
                            "padding": "10px",
                            "border_radius": "4px",
                        },
                    },
                    team_checkboxes,
                ),
            ),
            html.div(
                {"class_name": "modal-actions"},
                html.button(
                    {"on_click": handle_submit, "class_name": "btn-accion", "disabled": not selected_robot_id or not selected_team_ids},
                    "Guardar Asignaciones",
                ),
                html.button({"on_click": on_cancel}, "Cancelar"),
            ),
        ),
    )


# --- Componente de Confirmación Genérico ---
@component
def ConfirmationModal(message, on_confirm, on_cancel):
    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": "modal-content confirmation-modal"},
            html.h2({"class_name": "modal-title"}, "Confirmación"),
            html.p({"class_name": "modal-message"}, message),
            html.div(
                {"class_name": "modal-actions"},
                html.button(
                    {
                        "on_click": lambda event: asyncio.ensure_future(on_confirm()) if asyncio.iscoroutinefunction(on_confirm) else on_confirm(),
                        "class_name": "btn-accion btn-confirm",
                    },
                    "Confirmar",
                ),
                html.button({"on_click": on_cancel, "class_name": "btn-accion-secundario btn-cancel"}, "Cancelar"),
            ),
        ),
    )


# --- Componente de Feedback Genérico ---
@component
def FeedbackModal(message, message_type, on_dismiss):
    # Este hook se ejecuta una sola vez cuando el modal aparece en pantalla
    @use_effect(dependencies=[])
    async def auto_dismiss_effect():
        # Espera 3 segundos de forma no bloqueante
        await asyncio.sleep(2)
        # Llama a la función para cerrar el modal.
        # Pasamos `None` porque no hay un evento de click real.
        on_dismiss(None)

    modal_content_class = f"modal-content feedback-modal feedback-modal-{message_type}"
    title_text = "Éxito" if message_type == "success" else "Error"
    title_class = f"modal-title feedback-title-{message_type}"

    return html.div(
        {"class_name": "modal-overlay"},
        html.div(
            {"class_name": modal_content_class},
            html.h2({"class_name": title_class}, title_text),
            html.p({"class_name": "modal-message"}, message),
            html.div(
                {"class_name": "modal-actions"},
                # El botón OK sigue aquí por si el usuario quiere cerrarlo antes
                html.button({"on_click": on_dismiss, "class_name": "btn-accion"}, "OK"),
            ),
        ),
    )


# --- Componente Principal de la Aplicación ---
@component
def App():
    robots, set_robots = use_state([])
    robot_en_edicion, set_robot_en_edicion = use_state(None)
    robot_para_programar, set_robot_para_programar = use_state(None)
    equipos_disponibles, set_equipos_disponibles = use_state([])
    all_active_teams_list, set_all_active_teams_list = use_state([])

    search_term, set_search_term = use_state("")
    activo_filter, set_activo_filter = use_state("all")
    online_filter, set_online_filter = use_state("all")
    show_confirmation, set_show_confirmation = use_state(False)
    confirmation_message, set_confirmation_message = use_state("")
    on_confirm_action_callback, set_on_confirm_action_callback = use_state(lambda: None)
    show_feedback, set_show_feedback = use_state(False)
    feedback_message, set_feedback_message = use_state("")
    feedback_type, set_feedback_type = use_state("success")
    show_assignment_form, set_show_assignment_form = use_state(False)
    available_teams_for_assignment, set_available_teams_for_assignment = use_state([])

    show_deassignment_modal, set_show_deassignment_modal = use_state(False)
    robot_for_deassignment, set_robot_for_deassignment = use_state(None)
    teams_for_deassignment, set_teams_for_deassignment = use_state([])

    show_view_schedules_modal, set_show_view_schedules_modal = use_state(False)
    robot_for_schedules, set_robot_for_schedules = use_state(None)
    schedules_list, set_schedules_list = use_state([])

    show_edit_schedule_modal, set_show_edit_schedule_modal = use_state(False)
    schedule_to_edit_data, set_schedule_to_edit_data = use_state(None)

    current_theme, set_current_theme = use_state("dark")
    sort_key, set_sort_key = use_state("Robot")
    sort_ascending, set_sort_ascending = use_state(True)

    def toggle_theme(event=None):
        set_current_theme(lambda old: "light" if old == "dark" else "dark")

    def handle_sort_click(key):
        if key == sort_key:
            set_sort_ascending(not sort_ascending)
        else:
            set_sort_key(key)
            set_sort_ascending(True)

    # --- Función fetch_robots (Corregida) ---
    async def fetch_robots(event=None):
        if not db:
            return
        # Modificamos el LEFT JOIN para que SOLO considere las asignaciones manuales.
        # Esto alinea lo que ve el usuario en la tabla con lo que puede desasignar.
        query = """
            SELECT R.RobotId, R.Robot, R.Activo, R.EsOnline, R.PrioridadBalanceo, R.MinEquipos, R.MaxEquipos, R.TicketsPorEquipoAdicional,
                   STRING_AGG(E.Equipo, ', ') WITHIN GROUP (ORDER BY E.Equipo) AS EquiposAsignados
            FROM dbo.Robots R
            LEFT JOIN dbo.Asignaciones A ON R.RobotId = A.RobotId
            LEFT JOIN dbo.Equipos E ON A.EquipoId = E.EquipoId
            WHERE R.Robot NOT LIKE '%_Loop'
            GROUP BY R.RobotId, R.Robot, R.Activo, R.EsOnline, R.PrioridadBalanceo, R.MinEquipos, R.MaxEquipos, R.TicketsPorEquipoAdicional
            ORDER BY R.Robot
        """
        query_1 = """
            SELECT R.RobotId, R.Robot, R.Activo, R.EsOnline, R.PrioridadBalanceo, R.MinEquipos, R.MaxEquipos, R.TicketsPorEquipoAdicional,
                STRING_AGG(E.Equipo, ', ') WITHIN GROUP (ORDER BY E.Equipo) AS EquiposAsignados
            FROM dbo.Robots R
            LEFT JOIN dbo.Asignaciones A ON R.RobotId = A.RobotId AND A.Reservado = 1 AND (A.EsProgramado = 0 OR A.EsProgramado IS NULL)
            LEFT JOIN dbo.Equipos E ON A.EquipoId = E.EquipoId
            WHERE R.Robot NOT LIKE '%_Loop'
            GROUP BY R.RobotId, R.Robot, R.Activo, R.EsOnline, R.PrioridadBalanceo, R.MinEquipos, R.MaxEquipos, R.TicketsPorEquipoAdicional
            ORDER BY R.Robot
        """
        try:
            data = await asyncio.to_thread(db.ejecutar_consulta, query, None, True)
            set_robots(data or [])
        except Exception as e:
            print(f"Error fetching robots with STRING_AGG: {e}. Falling back.")
            query_fallback = "SELECT RobotId, Robot, Activo, EsOnline, PrioridadBalanceo, MinEquipos, MaxEquipos, TicketsPorEquipoAdicional FROM dbo.Robots ORDER BY Robot"
            data_fallback = await asyncio.to_thread(db.ejecutar_consulta, query_fallback, None, True)
            processed_data = [{**row, "EquiposAsignados": None} for row in data_fallback] if data_fallback else []
            set_robots(processed_data)
            set_feedback_message("No se pudieron cargar los equipos asignados (funcionalidad limitada).")
            set_feedback_type("warning")
            set_show_feedback(True)

    async def fetch_all_active_teams_if_needed():
        current_list = all_active_teams_list
        if not current_list and db:
            try:
                query_all_teams = "SELECT EquipoId, Equipo FROM dbo.Equipos WHERE Activo_SAM = 1 ORDER BY Equipo"
                all_teams = await asyncio.to_thread(db.ejecutar_consulta, query_all_teams, None, True)
                actual_teams = all_teams or []
                set_all_active_teams_list(actual_teams)
                return actual_teams
            except Exception as e:
                print(f"Error fetching all active teams: {e}")
                set_feedback_message(f"Error crítico al cargar lista completa de equipos: {str(e)}")
                set_feedback_type("error")
                set_show_feedback(True)
                return []
        return current_list

    # use_effect(lambda: asyncio.ensure_future(fetch_robots()), [])
    # use_effect(lambda: asyncio.ensure_future(fetch_all_active_teams_if_needed()), [])

    # Combinamos las llamadas de carga inicial en un solo efecto.
    # Esta función no devuelve nada (implícitamente devuelve None),
    # por lo que ReactPy sabe que no hay función de limpieza que ejecutar.
    @use_effect(dependencies=[])
    def initial_data_load():
        asyncio.ensure_future(fetch_robots())
        asyncio.ensure_future(fetch_all_active_teams_if_needed())

    async def handle_toggle(robot_id, field, event=None):
        robot_actual = next((r for r in robots if r["RobotId"] == robot_id), None)
        if not robot_actual or db is None:
            return
        nuevo_estado = not robot_actual.get(field, False)
        query = f"UPDATE dbo.Robots SET {field} = ? WHERE RobotId = ?"
        await asyncio.to_thread(db.ejecutar_consulta, query, (nuevo_estado, robot_id), False)
        await fetch_robots()

    async def trigger_robot_edit_confirmation(form_data):
        set_confirmation_message("¿Guardar cambios en el robot?")

        async def actual_action():
            await handle_save_robot_action(form_data)

        set_on_confirm_action_callback(lambda _: actual_action)
        set_show_confirmation(True)

    async def execute_confirmed_action():
        set_show_confirmation(False)
        action_constructor = on_confirm_action_callback
        if action_constructor and callable(action_constructor):
            action_coro = action_constructor()
            try:
                await action_coro
            except Exception as e:
                print(f"Error ejecutando acción confirmada: {e}")
                set_feedback_message(f"Error ejecutando la acción: {e}")
                set_feedback_type("error")
                set_show_feedback(True)
        else:
            print("Error: La acción de confirmación guardada no es válida.")

        # Restablece el callback a un estado inactivo
        set_on_confirm_action_callback(lambda _: None)

    async def handle_save_robot_action(data):
        if db is None:
            return
        try:
            query = "UPDATE dbo.Robots SET PrioridadBalanceo = ?, MinEquipos = ?, MaxEquipos = ?, TicketsPorEquipoAdicional = ? WHERE RobotId = ?"
            tickets_adicional = data.get("TicketsPorEquipoAdicional")
            params_tuple = (
                data.get("PrioridadBalanceo"),
                data.get("MinEquipos"),
                data.get("MaxEquipos"),
                int(tickets_adicional) if tickets_adicional is not None and str(tickets_adicional).isdigit() else None,
                data["RobotId"],
            )
            await asyncio.to_thread(db.ejecutar_consulta, query, params_tuple, False)
            set_feedback_message("Robot actualizado.")
            set_feedback_type("success")
        except Exception as e:
            set_feedback_message(f"Error: {str(e)}")
            set_feedback_type("error")
        set_show_feedback(True)
        set_robot_en_edicion(None)
        await fetch_robots()

    async def trigger_robot_schedule_confirmation(robot, form_data):
        set_confirmation_message("¿Guardar esta programación?")

        async def actual_action():
            await handle_save_schedule_action(robot, form_data)

        set_on_confirm_action_callback(lambda _: actual_action)  # Usamos una lambda que devuelve la función
        set_show_confirmation(True)

    async def handle_save_schedule_action(robot, schedule_form_data):
        if not db:
            set_feedback_message("Error BD")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        selected_team_ids = schedule_form_data.get("equipo_ids", [])
        if not selected_team_ids:
            set_feedback_message("Debe seleccionar al menos un equipo.")
            set_feedback_type("error")
            set_show_feedback(True)
            return

        current_all_teams = await fetch_all_active_teams_if_needed()
        equipos_map = {eq["EquipoId"]: eq["Equipo"] for eq in current_all_teams}
        selected_team_names = [equipos_map.get(int(tid)) for tid in selected_team_ids if equipos_map.get(int(tid))]

        if not selected_team_names:
            set_feedback_message("Equipos seleccionados no válidos.")
            set_feedback_type("error")
            set_show_feedback(True)
            return

        nombres_equipos_str = ", ".join(selected_team_names)

        schedule_type = schedule_form_data.get("tipo", "Diaria")
        hora_inicio = str(schedule_form_data.get("hora_inicio", "09:00:00"))
        tolerancia = int(schedule_form_data.get("tolerancia", 60))

        params_sp = {"@Robot": robot["Robot"], "@Equipos": nombres_equipos_str, "@HoraInicio": hora_inicio, "@Tolerancia": tolerancia}

        if schedule_type == "Semanal":
            params_sp["@DiasSemana"] = schedule_form_data.get("dias_semana", "LU,MA,MI,JU,VI")
        elif schedule_type == "Mensual":
            params_sp["@DiaDelMes"] = int(schedule_form_data.get("dia_mes", 1))
        elif schedule_type == "Especifica":
            params_sp["@FechasEspecificas"] = schedule_form_data.get("fecha_especifica", date.today().isoformat())

        sp_name = f"dbo.CargarProgramacion{schedule_type}"
        current_param_keys = [
            k for k in ["@Robot", "@Equipos", "@HoraInicio", "@Tolerancia", "@DiasSemana", "@DiaDelMes", "@FechasEspecificas"] if k in params_sp
        ]
        param_placeholders = ", ".join([f"{k}=?" for k in current_param_keys])
        query_sp_call = f"EXEC {sp_name} {param_placeholders}"
        params_tuple_for_sp = tuple(params_sp[k] for k in current_param_keys)

        try:
            await asyncio.to_thread(db.ejecutar_consulta, query_sp_call, params_tuple_for_sp, False)
            set_feedback_message("Robot programado.")
            set_feedback_type("success")
        except Exception as e:
            set_feedback_message(f"Error SP: {str(e)}")
            set_feedback_type("error")
        set_show_feedback(True)
        set_robot_para_programar(None)
        await fetch_robots()

    async def fetch_available_teams():
        if not db:
            return
        query = "SELECT E.EquipoId, E.Equipo FROM dbo.Equipos E WHERE E.Activo_SAM = 1 AND E.EquipoId NOT IN (SELECT DISTINCT A.EquipoId FROM dbo.Asignaciones A WHERE A.Reservado = 1 AND (A.EsProgramado = 0 OR A.EsProgramado IS NULL)) ORDER BY E.Equipo"
        try:
            teams = await asyncio.to_thread(db.ejecutar_consulta, query, None, True)
            set_available_teams_for_assignment(teams or [])
        except Exception as e:
            print(f"Error fetch available teams for assignment: {e}")
            set_available_teams_for_assignment([])

    async def handle_open_assignment_form(event=None):
        await fetch_available_teams()
        set_show_assignment_form(True)

    async def handle_save_assignments_action(robot_id, team_ids_list):
        if not db or not team_ids_list or not robot_id:
            return
        all_ok = True
        errors = []
        for team_id in team_ids_list:
            try:
                await asyncio.to_thread(
                    db.ejecutar_consulta,
                    "INSERT INTO dbo.Asignaciones (RobotId, EquipoId, Reservado, FechaAsignacion, AsignadoPor) VALUES (?, ?, 1, GETDATE(), 'WebApp')",
                    (int(robot_id), int(team_id)),
                    False,
                )
            except Exception as e:
                all_ok = False
                errors.append(str(e))
        if all_ok:
            set_feedback_message(f"{len(team_ids_list)} equipo(s) asignados.")
            set_feedback_type("success")
        else:
            set_feedback_message(f"Error asignando: {'; '.join(errors)}")
            set_feedback_type("error")
        set_show_feedback(True)
        set_show_assignment_form(False)
        await fetch_robots()
        await fetch_available_teams()

    async def trigger_assignment_confirmation(robot_id, team_ids_list):
        if not robot_id or not team_ids_list:
            set_feedback_message("Robot y equipo(s) deben ser seleccionados.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        robot_name = next((r["Robot"] for r in robots if str(r["RobotId"]) == str(robot_id)), "Desconocido")
        msg = f"Asignar {len(team_ids_list)} equipo(s) al robot '{robot_name}'?"
        set_confirmation_message(msg)

        async def actual_action():
            await handle_save_assignments_action(robot_id, team_ids_list)

        set_on_confirm_action_callback(lambda _: actual_action)  # Usamos una lambda que devuelve la función
        set_show_confirmation(True)

    async def handle_open_deassignment_modal(robot_data_arg, event=None):
        if not db:
            set_feedback_message("Error BD.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        set_robot_for_deassignment(robot_data_arg)
        try:
            query = "SELECT E.EquipoId, E.Equipo FROM dbo.Equipos E INNER JOIN dbo.Asignaciones A ON E.EquipoId = A.EquipoId WHERE A.RobotId = ? AND A.Reservado = 1 AND (A.EsProgramado = 0 OR A.EsProgramado IS NULL) ORDER BY E.Equipo"
            teams = await asyncio.to_thread(db.ejecutar_consulta, query, (robot_data_arg["RobotId"],), True)
            set_teams_for_deassignment(teams or [])
            set_show_deassignment_modal(True)
        except Exception as e:
            set_feedback_message(f"Error cargando equipos para desasignar: {str(e)}")
            set_feedback_type("error")
            set_show_feedback(True)
            set_show_deassignment_modal(False)

    async def handle_save_deassignments_action(robot_id, team_ids_list):
        if not db or not team_ids_list:
            return
        all_ok = True
        errors = []
        for team_id in team_ids_list:
            try:
                await asyncio.to_thread(
                    db.ejecutar_consulta,
                    "DELETE FROM dbo.Asignaciones WHERE RobotId = ? AND EquipoId = ? AND Reservado = 1 AND (EsProgramado = 0 OR EsProgramado IS NULL)",
                    (robot_id, team_id),
                    False,
                )
            except Exception as e:
                all_ok = False
                errors.append(str(e))
        if all_ok:
            set_feedback_message("Equipos de-asignados.")
            set_feedback_type("success")
        else:
            set_feedback_message(f"Error de-asignando: {'; '.join(errors)}")
            set_feedback_type("error")
        set_show_feedback(True)
        set_show_deassignment_modal(False)
        await fetch_robots()
        await fetch_available_teams()

    async def trigger_deassignment_confirmation(robot_id, team_ids_list):
        if not team_ids_list:
            set_feedback_message("Nada seleccionado.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        robot_name = robot_for_deassignment["Robot"] if robot_for_deassignment else "Desconocido"
        msg = f"Desasignar {len(team_ids_list)} equipo(s) del robot '{robot_name}'?"
        set_confirmation_message(msg)

        async def actual_action():
            await handle_save_deassignments_action(robot_id, team_ids_list)

        set_on_confirm_action_callback(lambda _: actual_action)  # Usamos una lambda que devuelve la función
        set_show_confirmation(True)

    async def handle_open_schedule_form(robot_data_arg, event=None):
        if not db:
            set_feedback_message("Error BD.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        current_teams = await fetch_all_active_teams_if_needed()
        set_equipos_disponibles(current_teams)
        set_robot_para_programar(robot_data_arg)

    async def handle_open_view_schedules_modal(robot_data_arg, event=None):
        set_robot_for_schedules(robot_data_arg)
        if not db:
            print("Database connection error")
            set_feedback_message("Error BD.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        query = """
            SELECT P.ProgramacionId, P.RobotId, P.TipoProgramacion, P.HoraInicio, P.DiasSemana, P.DiaDelMes, P.FechaEspecifica, P.Tolerancia,
                   STRING_AGG(E.Equipo, ', ') WITHIN GROUP (ORDER BY E.Equipo) AS EquiposProgramados
            FROM dbo.Programaciones P
            LEFT JOIN dbo.Asignaciones A ON P.ProgramacionId = A.ProgramacionId AND A.EsProgramado = 1
            LEFT JOIN dbo.Equipos E ON A.EquipoId = E.EquipoId
            WHERE P.RobotId = ?
            GROUP BY P.ProgramacionId, P.RobotId, P.TipoProgramacion, P.HoraInicio, P.DiasSemana, P.DiaDelMes, P.FechaEspecifica, P.Tolerancia
            ORDER BY P.ProgramacionId;
        """
        try:
            schedules = await asyncio.to_thread(db.ejecutar_consulta, query, (robot_data_arg["RobotId"],), True)
            set_schedules_list(schedules or [])
            set_show_view_schedules_modal(True)
        except Exception as e:
            set_feedback_message(f"Error cargando prog: {str(e)}")
            set_feedback_type("error")
            set_show_feedback(True)
            set_schedules_list([])

    async def handle_open_edit_schedule_modal(schedule_data_arg):
        robot_name = robot_for_schedules["Robot"] if robot_for_schedules else "N/A"
        data_for_form = {
            **schedule_data_arg,
            "RobotName": robot_name,
            "RobotId": schedule_data_arg.get("RobotId") or (robot_for_schedules.get("RobotId") if robot_for_schedules else None),
        }
        set_schedule_to_edit_data(data_for_form)
        if not db:
            set_feedback_message("Error BD.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        try:
            await fetch_all_active_teams_if_needed()
            set_show_edit_schedule_modal(True)
        except Exception as e:
            set_feedback_message(f"Error cargando equipos: {str(e)}")
            set_feedback_type("error")
            set_show_feedback(True)
            return

    async def handle_update_schedule_action(programacion_id, form_data):
        if not db or not robot_for_schedules:
            set_feedback_message("Error BD/Contexto Robot.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        current_robot_id = robot_for_schedules["RobotId"]
        team_ids = form_data.get("equipo_ids", [])
        current_all_active_teams = await fetch_all_active_teams_if_needed()
        equipos_map = {eq["EquipoId"]: eq["Equipo"] for eq in current_all_active_teams}

        selected_team_names = [equipos_map.get(int(tid)) for tid in team_ids if equipos_map.get(int(tid))]
        equipos_str = ", ".join(selected_team_names)
        dia_mes_val = form_data.get("dia_mes")
        tol_val = form_data.get("tolerancia")
        hora_inicio_val = str(form_data.get("hora_inicio", "00:00:00"))

        params_tuple = (
            programacion_id,
            current_robot_id,
            form_data.get("tipo"),
            hora_inicio_val,
            form_data.get("dias_semana") if form_data.get("tipo") == "Semanal" else None,
            int(dia_mes_val) if form_data.get("tipo") == "Mensual" and dia_mes_val is not None and str(dia_mes_val).strip().isdigit() else None,
            form_data.get("fecha_especifica") if form_data.get("tipo") == "Especifica" else None,
            int(tol_val) if tol_val is not None and str(tol_val).strip().isdigit() else None,
            equipos_str,
            "WebApp_Update",
        )
        try:
            await asyncio.to_thread(
                db.ejecutar_consulta,
                "EXEC dbo.ActualizarProgramacionCompleta @ProgramacionId=?, @RobotId=?, @TipoProgramacion=?, @HoraInicio=?, @DiasSemana=?, @DiaDelMes=?, @FechaEspecifica=?, @Tolerancia=?, @Equipos=?, @UsuarioModifica=?",
                params_tuple,
                False,
            )
            set_feedback_message("Programación actualizada.")
            set_feedback_type("success")
        except Exception as e:
            set_feedback_message(f"Error actualizando: {str(e)}")
            set_feedback_type("error")
        set_show_edit_schedule_modal(False)
        if robot_for_schedules:
            await handle_open_view_schedules_modal(robot_for_schedules)
        await fetch_robots()
        set_show_feedback(True)

    async def trigger_edit_schedule_confirmation(programacion_id, updated_form_data):
        confirmation_msg = f"¿Está seguro de que desea guardar los cambios en la programación ID {programacion_id}?"
        set_confirmation_message(confirmation_msg)

        async def actual_db_action():
            await handle_update_schedule_action(programacion_id, updated_form_data)

        set_on_confirm_action_callback(lambda _: actual_db_action)
        set_show_confirmation(True)

    async def handle_delete_schedule_action(pid_to_delete):
        if not db or not robot_for_schedules:
            set_feedback_message("Error BD/Contexto Robot.")
            set_feedback_type("error")
            set_show_feedback(True)
            return
        current_robot_id = robot_for_schedules["RobotId"]
        try:
            await asyncio.to_thread(
                db.ejecutar_consulta,
                "EXEC dbo.EliminarProgramacionCompleta @ProgramacionId=?, @RobotId=?, @UsuarioModifica=?",
                (pid_to_delete, current_robot_id, "WebApp_Delete"),
                False,
            )
            set_feedback_message(f"Programación {pid_to_delete} eliminada.")
            set_feedback_type("success")
        except Exception as e:
            set_feedback_message(f"Error eliminando: {str(e)}")
            set_feedback_type("error")
        set_show_feedback(True)
        if robot_for_schedules:
            await handle_open_view_schedules_modal(robot_for_schedules)
        await fetch_robots()

    async def trigger_delete_schedule_confirmation(pid_to_delete):
        robot_name = robot_for_schedules.get("Robot", "desconocido") if robot_for_schedules else "Robot desconocido"
        msg = f"¿Eliminar programación ID {pid_to_delete} del robot '{robot_name}'?"
        set_confirmation_message(msg)

        async def actual_action():
            await handle_delete_schedule_action(pid_to_delete)

        # Hazlo consistente con las otras funciones
        set_on_confirm_action_callback(lambda _: actual_action)  # Usamos una lambda que devuelve la función
        set_show_confirmation(True)

    if not db:
        return html.div(html.h1("Error de Conexión"), html.p("No se pudo establecer la conexión con la base de datos SAM."))

    current_filter_stage = list(robots)
    if search_term:
        current_filter_stage = [r for r in current_filter_stage if search_term.lower() in r.get("Robot", "").lower()]
    if activo_filter == "true":
        current_filter_stage = [r for r in current_filter_stage if r.get("Activo")]
    elif activo_filter == "false":
        current_filter_stage = [r for r in current_filter_stage if not r.get("Activo")]
    if online_filter == "true":
        current_filter_stage = [r for r in current_filter_stage if r.get("EsOnline")]
    elif online_filter == "false":
        current_filter_stage = [r for r in current_filter_stage if not r.get("EsOnline")]

    if sort_key and current_filter_stage:

        def get_sort_value(item):
            val = item.get(sort_key)
            numeric_cols = ["PrioridadBalanceo", "MinEquipos", "MaxEquipos", "TicketsPorEquipoAdicional"]
            is_numeric_col = sort_key in numeric_cols
            if val is None:
                if is_numeric_col:
                    return float("-inf") if sort_ascending else float("inf")
                return ""
            if isinstance(val, str) and not is_numeric_col:
                return val.lower()
            try:
                if is_numeric_col:
                    return float(val)
            except ValueError:
                return float("-inf") if sort_ascending else float("inf")
            return val

        try:
            current_filter_stage.sort(key=get_sort_value, reverse=not sort_ascending)
        except TypeError as e:
            print(f"Sort error: {e} for key {sort_key}")
    filtered_robots = current_filter_stage

    table_rows = []
    for robot_data in filtered_robots:
        equipos_asignados_text = robot_data.get("EquiposAsignados") or "Ninguno"

        action_buttons_list = [
            html.button({"on_click": partial(handle_open_schedule_form, robot_data), "class_name": "btn-accion"}, "Programar"),
            html.button({"on_click": lambda event, r=robot_data: set_robot_en_edicion(r), "class_name": "btn-accion-secundario"}, "Editar Robot"),
        ]
        if robot_data.get("EquiposAsignados"):
            action_buttons_list.append(
                html.button(
                    {"on_click": partial(handle_open_deassignment_modal, robot_data), "class_name": "btn-accion-peligro"}, "Desasignar Equipos"
                )
            )
        action_buttons_list.append(
            html.button({"on_click": partial(handle_open_view_schedules_modal, robot_data), "class_name": "btn-accion-info"}, "Ver Programaciones")
        )

        table_rows.append(
            html.tr(
                {"key": robot_data["RobotId"]},
                html.td(robot_data.get("Robot", "N/A")),
                html.td(equipos_asignados_text),
                html.td(
                    html.button(
                        {
                            "on_click": partial(handle_toggle, robot_data["RobotId"], "Activo"),
                            "class_name": f"btn-{'activo' if robot_data.get('Activo') else 'inactivo'}",
                        },
                        "Sí" if robot_data.get("Activo") else "No",
                    )
                ),
                html.td(
                    html.button(
                        {
                            "on_click": partial(handle_toggle, robot_data["RobotId"], "EsOnline"),
                            "class_name": f"btn-{'activo' if robot_data.get('EsOnline') else 'inactivo'}",
                        },
                        "Sí" if robot_data.get("EsOnline") else "No",
                    )
                ),
                html.td(robot_data.get("PrioridadBalanceo", "N/A")),
                html.td(*action_buttons_list),
            )
        )

    final_table_headers = []
    col_keys_ordered = ["Robot", "EquiposAsignados", "Activo", "EsOnline", "PrioridadBalanceo", "Acciones"]
    sortable_cols_with_display = {"Robot": "Robot", "EquiposAsignados": "Equipos Asignados", "PrioridadBalanceo": "Prioridad"}

    for col_key in col_keys_ordered:
        if col_key in sortable_cols_with_display:
            text = sortable_cols_with_display[col_key]
            final_table_headers.append(
                html.th(
                    {"on_click": lambda event, k=col_key: handle_sort_click(k), "style": {"cursor": "pointer"}},
                    f"{text}{' ▲' if sort_key == col_key and sort_ascending else ' ▼' if sort_key == col_key else ''}",
                )
            )
        elif col_key == "Acciones":
            final_table_headers.append(html.th(col_key))
        else:
            final_table_headers.append(html.th(col_key.replace("EsOnline", "Es Online")))

    app_children = [
        html.head(html.title("SAM - Gestión de Robots"), html.link({"rel": "stylesheet", "href": "/static/style.css"})),
        html.h1("SAM - Gestión de Robots"),
        html.div(
            {"class_name": "filter-controls"},
            html.input(
                {
                    "type": "text",
                    "placeholder": "Buscar robot...",
                    "value": search_term,
                    "on_change": lambda e: set_search_term(e["target"]["value"]),
                    "class_name": "search-input",
                }
            ),
            html.div(
                {"class_name": "filter-group"},
                html.label({"for": "activo_filter_select"}, "Activo: "),
                html.select(
                    {
                        "id": "activo_filter_select",
                        "value": activo_filter,
                        "on_change": lambda e: set_activo_filter(e["target"]["value"]),
                        "class_name": "filter-select",
                    },
                    html.option({"value": "all"}, "Todos"),
                    html.option({"value": "true"}, "Sí"),
                    html.option({"value": "false"}, "No"),
                ),
            ),
            html.div(
                {"class_name": "filter-group"},
                html.label({"for": "online_filter_select"}, "Online: "),
                html.select(
                    {
                        "id": "online_filter_select",
                        "value": online_filter,
                        "on_change": lambda e: set_online_filter(e["target"]["value"]),
                        "class_name": "filter-select",
                    },
                    html.option({"value": "all"}, "Todos"),
                    html.option({"value": "true"}, "Sí"),
                    html.option({"value": "false"}, "No"),
                ),
            ),
        ),
        html.div(
            {"class_name": "action-buttons-bar"},
            html.button({"on_click": toggle_theme, "class_name": "btn-accion-secundario theme-toggle-btn"}, "🌓"),
            html.button({"on_click": fetch_robots, "class_name": "btn-accion"}, "Refrescar Datos"),
            html.button({"on_click": handle_open_assignment_form, "class_name": "btn-accion-secundario"}, "Asignar Equipos"),
        ),
        html.table(
            {"class_name": "sam-table"},
            html.thead(html.tr(*final_table_headers)),
            html.tbody(table_rows if filtered_robots else html.tr(html.td({"colSpan": len(final_table_headers)}, "No hay robots para mostrar."))),
        ),
    ]

    if robot_en_edicion:
        app_children.append(
            RobotEditForm(robot=robot_en_edicion, on_save=trigger_robot_edit_confirmation, on_cancel=lambda e: set_robot_en_edicion(None))
        )
    if robot_para_programar:
        app_children.append(
            ScheduleCreateForm(
                robot=robot_para_programar,
                equipos_disponibles=all_active_teams_list,
                on_save=trigger_robot_schedule_confirmation,
                on_cancel=lambda e: set_robot_para_programar(None),
            )
        )
    if show_assignment_form:
        app_children.append(
            AssignmentForm(
                robots=robots,
                available_teams=available_teams_for_assignment,
                on_save=trigger_assignment_confirmation,
                on_cancel=lambda e: set_show_assignment_form(False),
            )
        )

    if show_deassignment_modal and robot_for_deassignment:
        app_children.append(
            DeassignmentForm(
                robot_for_deassignment=robot_for_deassignment,
                teams_for_deassignment=teams_for_deassignment,
                on_save=trigger_deassignment_confirmation,
                on_cancel=lambda e: set_show_deassignment_modal(False),
            )
        )

    if show_view_schedules_modal and robot_for_schedules:
        app_children.append(
            ViewSchedulesModal(
                robot_for_schedules=robot_for_schedules,
                schedules_list=schedules_list,
                on_cancel=lambda e: set_show_view_schedules_modal(False),
                on_edit_schedule=handle_open_edit_schedule_modal,
                on_delete_schedule=trigger_delete_schedule_confirmation,
            )
        )

    if show_edit_schedule_modal and schedule_to_edit_data and robot_for_schedules:
        app_children.append(
            ScheduleEditForm(
                schedule_to_edit=schedule_to_edit_data,
                equipos_disponibles_all=all_active_teams_list,
                on_save=trigger_edit_schedule_confirmation,
                on_cancel=lambda e: set_show_edit_schedule_modal(False),
            )
        )

    if show_confirmation:
        app_children.append(
            ConfirmationModal(message=confirmation_message, on_confirm=execute_confirmed_action, on_cancel=lambda e: set_show_confirmation(False))
        )
    if show_feedback:
        app_children.append(FeedbackModal(message=feedback_message, message_type=feedback_type, on_dismiss=lambda e: set_show_feedback(False)))

    return html.div({"class_name": f"container theme-{current_theme}"}, *app_children)
