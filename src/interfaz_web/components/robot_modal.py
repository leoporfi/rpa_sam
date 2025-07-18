# interfaz_web/components/robot_modal.py

from typing import Any, Callable, Dict

import httpx
from reactpy import component, event, html, use_context, use_effect, use_state

from ..config.settings import Settings
from .notifications import NotificationContext

URL_BASE = Settings.API_BASE_URL

# Valores por defecto para un robot nuevo
DEFAULT_ROBOT_STATE = {
    "RobotId": None,
    "Robot": "",
    "Descripcion": "",
    "MinEquipos": 1,
    "MaxEquipos": -1,
    "PrioridadBalanceo": 100,
    "TicketsPorEquipoAdicional": 10,
}


@component
def RobotEditModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
    notification_ctx = use_context(NotificationContext)
    form_data, set_form_data = use_state(DEFAULT_ROBOT_STATE)
    errors, set_errors = use_state({})
    is_loading, set_is_loading = use_state(False)

    is_edit_mode = bool(robot and robot.get("RobotId") is not None)

    @use_effect(dependencies=[robot])
    def populate_form_data():
        # --- CORRECCIÓN 1: Usar 'is not None' para manejar el caso del diccionario vacío ---
        if robot is not None:
            if is_edit_mode:
                set_form_data(robot)
            else:
                # Esto ahora se ejecutará cuando 'robot' sea un diccionario vacío {}
                set_form_data(DEFAULT_ROBOT_STATE)

    if robot is None:
        return None

    def handle_form_change(field_name, field_value):
        if field_name in ["RobotId", "MinEquipos", "MaxEquipos", "PrioridadBalanceo", "TicketsPorEquipoAdicional"]:
            try:
                field_value = int(field_value) if field_value != "" else None
            except (ValueError, TypeError):
                field_value = None
        set_form_data(lambda old_data: {**old_data, field_name: field_value})

    def validate_form():
        new_errors = {}
        if not form_data.get("Robot"):
            new_errors["Robot"] = "El nombre del robot es requerido."
        if not is_edit_mode and not form_data.get("RobotId"):
            new_errors["RobotId"] = "El ID del robot es requerido."
        if form_data.get("MinEquipos", 1) < 0:
            new_errors["MinEquipos"] = "El valor no puede ser negativo."
        if form_data.get("MaxEquipos", -1) < -1:
            new_errors["MaxEquipos"] = "El valor no puede ser inferior a -1."
        set_errors(new_errors)
        return not new_errors

    async def handle_save(event):
        if not validate_form():
            return

        set_is_loading(True)
        show_notification = notification_ctx["show_notification"]

        try:
            async with httpx.AsyncClient() as client:
                if is_edit_mode:
                    robot_id_to_update = robot.get("RobotId")
                    payload_to_send = {k: v for k, v in form_data.items() if k not in ["RobotId", "Robot"]}
                    url = f"{URL_BASE}/api/robots/{robot_id_to_update}"
                    await client.put(url, json=payload_to_send)
                    show_notification("Robot actualizado con éxito.", "success")
                else:
                    payload_to_send = form_data.copy()
                    url = f"{URL_BASE}/api/robots"
                    await client.post(url, json=payload_to_send)
                    show_notification("Robot creado con éxito.", "success")

            await on_save_success()

        except Exception as e:
            show_notification(f"Error al guardar: {e}", "error")
        finally:
            set_is_loading(False)

    modal_class = "modal is-active"

    return html.div(
        {"className": modal_class},
        html.div({"className": "modal-background", "onClick": on_close}),
        html.div(
            {"className": "modal-card"},
            html.header(
                {"className": "modal-card-head"},
                html.p({"className": "modal-card-title"}, "Editar Robot" if is_edit_mode else "Crear Nuevo Robot"),
                # html.button({"className": "delete", "aria-label": "close", "onClick": on_close}),
            ),
            html.form(
                {"onSubmit": event(handle_save, prevent_default=True)},
                html.section(
                    {"className": "modal-card-body"},
                    # Campo FileId
                    html.div(
                        {"className": "field"},  # , "style": {"display": "block" if not is_edit_mode else "none"}},
                        html.label({"htmlFor": "robot-id", "className": "label"}, "Robot ID (de A360)"),
                        html.div(
                            {"className": "control"},
                            html.input(
                                {
                                    "id": "robot-id",
                                    "type": "number",
                                    "className": "input",
                                    "value": form_data.get("RobotId", "") if is_edit_mode else None,
                                    "onChange": lambda e: handle_form_change("RobotId", e["target"]["value"]),
                                    "required": not is_edit_mode,
                                    "disabled": is_edit_mode,
                                }
                            ),
                        ),
                        html.p({"className": "help is-danger"}, errors.get("RobotId", "")),
                    ),
                    # Campo Nombre
                    html.div(
                        {"className": "field"},
                        html.label({"htmlFor": "robot-name", "className": "label"}, "Nombre"),
                        html.div(
                            {"className": "control"},
                            html.input(
                                {
                                    "id": "robot-name",
                                    "type": "text",
                                    "className": "input",
                                    "value": form_data.get("Robot", ""),
                                    "onChange": lambda e: handle_form_change("Robot", e["target"]["value"]),
                                    "disabled": is_edit_mode,
                                    "required": True,
                                }
                            ),
                        ),
                        html.p({"className": "help is-danger"}, errors.get("Robot", "")),
                    ),
                    # Campo Descripción
                    html.div(
                        {"className": "field"},
                        html.label({"htmlFor": "robot-desc", "className": "label"}, "Descripción"),
                        html.div(
                            {"className": "control"},
                            html.textarea(
                                {
                                    "id": "robot-desc",
                                    "className": "textarea",
                                    "rows": 3,
                                    "value": form_data.get("Descripcion", ""),
                                    "onChange": lambda e: handle_form_change("Descripcion", e["target"]["value"]),
                                }
                            ),
                        ),
                    ),
                    # Campos numéricos en columnas
                    html.div(
                        {"className": "columns is-multiline"},
                        html.div(
                            {"className": "column is-half"},
                            html.div(
                                {"className": "field"},
                                html.label({"htmlFor": "min-equipos", "className": "label"}, "Mín. Equipos"),
                                html.div(
                                    {"className": "control"},
                                    html.input(
                                        {
                                            "id": "min-equipos",
                                            "type": "number",
                                            "className": "input",
                                            "value": form_data.get("MinEquipos", ""),
                                            "onChange": lambda e: handle_form_change("MinEquipos", e["target"]["value"]),
                                        }
                                    ),
                                ),
                                html.p({"className": "help is-danger"}, errors.get("MinEquipos", "")),
                            ),
                        ),
                        html.div(
                            {"className": "column is-half"},
                            html.div(
                                {"className": "field"},
                                html.label({"htmlFor": "max-equipos", "className": "label"}, "Máx. Equipos"),
                                html.div(
                                    {"className": "control"},
                                    html.input(
                                        {
                                            "id": "max-equipos",
                                            "type": "number",
                                            "className": "input",
                                            "value": form_data.get("MaxEquipos", ""),
                                            "onChange": lambda e: handle_form_change("MaxEquipos", e["target"]["value"]),
                                        }
                                    ),
                                ),
                                html.p({"className": "help is-danger"}, errors.get("MaxEquipos", "")),
                            ),
                        ),
                        html.div(
                            {"className": "column is-half"},
                            html.div(
                                {"className": "field"},
                                html.label({"htmlFor": "prioridad", "className": "label"}, "Prioridad"),
                                html.div(
                                    {"className": "control"},
                                    html.input(
                                        {
                                            "id": "prioridad",
                                            "type": "number",
                                            "className": "input",
                                            "value": form_data.get("PrioridadBalanceo", ""),
                                            "onChange": lambda e: handle_form_change("PrioridadBalanceo", e["target"]["value"]),
                                        }
                                    ),
                                ),
                            ),
                        ),
                        html.div(
                            {"className": "column is-half"},
                            html.div(
                                {"className": "field"},
                                html.label({"htmlFor": "tickets", "className": "label"}, "Tickets/Equipo Adic."),
                                html.div(
                                    {"className": "control"},
                                    html.input(
                                        {
                                            "id": "tickets",
                                            "type": "number",
                                            "className": "input",
                                            "value": form_data.get("TicketsPorEquipoAdicional", ""),
                                            "onChange": lambda e: handle_form_change("TicketsPorEquipoAdicional", e["target"]["value"]),
                                        }
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                html.footer(
                    {"className": "modal-card-foot is-justify-content-flex-end"},
                    html.div(
                        {"className": "buttons"},
                        html.button(
                            {"type": "submit", "className": f"button is-success {'is-loading' if is_loading else ''}", "disabled": is_loading},
                            "Guardar",
                        ),
                        html.button({"type": "button", "className": "button", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
                    ),
                ),
            ),
        ),
    )


""""VERSION ANTERIOR"""
# # interfaz_web/components/robot_modal.py

# from typing import Any, Callable, Dict

# import httpx
# from reactpy import component, event, html, use_context, use_effect, use_state

# from ..config.settings import Settings
# from .notifications import NotificationContext

# URL_BASE = Settings.API_BASE_URL

# # Valores por defecto para un robot nuevo
# DEFAULT_ROBOT_STATE = {
#     "RobotId": None,
#     "Robot": "",
#     "Descripcion": "",
#     "MinEquipos": 1,
#     "MaxEquipos": -1,
#     "PrioridadBalanceo": 100,
#     "TicketsPorEquipoAdicional": 10,
# }


# @component
# def RobotEditModal(robot: Dict[str, Any] | None, on_close: Callable, on_save_success: Callable):
#     notification_ctx = use_context(NotificationContext)
#     form_data, set_form_data = use_state(DEFAULT_ROBOT_STATE)
#     is_loading, set_is_loading = use_state(False)

#     # Determina si estamos en modo 'edición' o 'creación'
#     is_edit_mode = bool(robot and robot.get("RobotId") is not None)

#     @use_effect(dependencies=[robot])
#     def populate_form_data():
#         if robot:  # Solo actuar si el robot no es None
#             if is_edit_mode:
#                 # Si es modo edición, usamos los datos del robot
#                 set_form_data(robot)
#             else:
#                 # Si es modo creación (robot={}), usamos los valores por defecto
#                 set_form_data(DEFAULT_ROBOT_STATE)

#     if robot is None:
#         return None

#     def handle_form_change(field_name, field_value):
#         # Convertir a número si es necesario
#         if field_name in ["RobotId", "MinEquipos", "MaxEquipos", "PrioridadBalanceo", "TicketsPorEquipoAdicional"]:
#             try:
#                 # Manejar el caso de un campo vacío en un input numérico
#                 field_value = int(field_value) if field_value != "" else None
#             except (ValueError, TypeError):
#                 field_value = None
#         set_form_data(lambda old_data: {**old_data, field_name: field_value})

#     async def handle_save(event):
#         set_is_loading(True)
#         show_notification = notification_ctx["show_notification"]

#         # Validación simple
#         if not is_edit_mode and form_data.get("RobotId") is None:
#             show_notification("El campo 'Robot ID' es requerido para crear un nuevo robot.", "error")
#             set_is_loading(False)
#             return

#         try:
#             payload = form_data.copy()
#             async with httpx.AsyncClient() as client:
#                 if is_edit_mode:
#                     # MODO EDICIÓN: Usamos PUT. Excluimos RobotId del payload principal.
#                     # robot_id_to_update = robot.get("RobotId")
#                     if "RobotId" in payload:
#                         # del payload["RobotId"]
#                         payload = {k: v for k, v in form_data.items() if k != "RobotId"}
#                     url = f"{URL_BASE}/api/robots/{payload}"
#                     await client.put(url, json=payload)
#                     show_notification("Robot actualizado con éxito.", "success")
#                 else:
#                     # MODO CREACIÓN: Usamos POST
#                     url = f"{URL_BASE}/api/robots"
#                     await client.post(url, json=payload)
#                     show_notification("Robot creado con éxito.", "success")

#             await on_save_success()

#         except Exception as e:
#             show_notification(f"Error al guardar: {e}", "error")
#         finally:
#             set_is_loading(False)

#     # El modal se activa añadiendo la clase 'is-active'
#     modal_class = "modal is-active"

#     return html.div(
#         {"className": modal_class},
#         html.div({"className": "modal-background", "onClick": on_close}),
#         html.div(
#             {"className": "modal-card"},
#             html.header(
#                 {"className": "modal-card-head"},
#                 html.p({"className": "modal-card-title"}, "Editar Robot" if is_edit_mode else "Crear Nuevo Robot"),
#                 # html.button({"className": "delete", "aria-label": "close", "onClick": on_close}),
#             ),
#             html.form(
#                 {"onSubmit": event(handle_save, prevent_default=True)},
#                 html.section(
#                     {"className": "modal-card-body"},
#                     # Campo Robot ID (solo para creación)
#                     html.div(
#                         {"className": "field", "style": {"display": "block" if not is_edit_mode else "none"}},
#                         html.label({"htmlFor": "robot-id", "className": "label"}, "Robot ID (de A360)"),
#                         html.div(
#                             {"className": "control"},
#                             html.input(
#                                 {
#                                     "id": "robot-id",
#                                     "type": "number",
#                                     "className": "input",
#                                     "value": form_data.get("RobotId", ""),
#                                     "onChange": lambda e: handle_form_change("RobotId", e["target"]["value"]),
#                                     "required": not is_edit_mode,
#                                 }
#                             ),
#                         ),
#                     ),
#                     # Campo Nombre
#                     html.div(
#                         {"className": "field"},
#                         html.label({"htmlFor": "robot-name", "className": "label"}, "Nombre"),
#                         html.div(
#                             {"className": "control"},
#                             html.input(
#                                 {
#                                     "id": "robot-name",
#                                     "type": "text",
#                                     "className": "input",
#                                     "value": form_data.get("Robot", ""),
#                                     "onChange": lambda e: handle_form_change("Robot", e["target"]["value"]),
#                                     "disabled": is_edit_mode,
#                                     "required": True,
#                                 }
#                             ),
#                         ),
#                     ),
#                     # Campo Descripción
#                     html.div(
#                         {"className": "field"},
#                         html.label({"htmlFor": "robot-desc", "className": "label"}, "Descripción"),
#                         html.div(
#                             {"className": "control"},
#                             html.textarea(
#                                 {
#                                     "id": "robot-desc",
#                                     "className": "textarea",
#                                     "rows": 3,
#                                     "value": form_data.get("Descripcion", ""),
#                                     "onChange": lambda e: handle_form_change("Descripcion", e["target"]["value"]),
#                                 }
#                             ),
#                         ),
#                     ),
#                     # Campos numéricos en columnas
#                     html.div(
#                         {"className": "columns is-multiline"},
#                         html.div(
#                             {"className": "column is-half"},
#                             html.div(
#                                 {"className": "field"},
#                                 html.label({"htmlFor": "min-equipos", "className": "label"}, "Mín. Equipos"),
#                                 html.div(
#                                     {"className": "control"},
#                                     html.input(
#                                         {
#                                             "id": "min-equipos",
#                                             "type": "number",
#                                             "className": "input",
#                                             "value": form_data.get("MinEquipos", ""),
#                                             "onChange": lambda e: handle_form_change("MinEquipos", e["target"]["value"]),
#                                         }
#                                     ),
#                                 ),
#                             ),
#                         ),
#                         html.div(
#                             {"className": "column is-half"},
#                             html.div(
#                                 {"className": "field"},
#                                 html.label({"htmlFor": "max-equipos", "className": "label"}, "Máx. Equipos"),
#                                 html.div(
#                                     {"className": "control"},
#                                     html.input(
#                                         {
#                                             "id": "max-equipos",
#                                             "type": "number",
#                                             "className": "input",
#                                             "value": form_data.get("MaxEquipos", ""),
#                                             "onChange": lambda e: handle_form_change("MaxEquipos", e["target"]["value"]),
#                                         }
#                                     ),
#                                 ),
#                             ),
#                         ),
#                         html.div(
#                             {"className": "column is-half"},
#                             html.div(
#                                 {"className": "field"},
#                                 html.label({"htmlFor": "prioridad", "className": "label"}, "Prioridad"),
#                                 html.div(
#                                     {"className": "control"},
#                                     html.input(
#                                         {
#                                             "id": "prioridad",
#                                             "type": "number",
#                                             "className": "input",
#                                             "value": form_data.get("PrioridadBalanceo", ""),
#                                             "onChange": lambda e: handle_form_change("PrioridadBalanceo", e["target"]["value"]),
#                                         }
#                                     ),
#                                 ),
#                             ),
#                         ),
#                         html.div(
#                             {"className": "column is-half"},
#                             html.div(
#                                 {"className": "field"},
#                                 html.label({"htmlFor": "tickets", "className": "label"}, "Tickets/Equipo Adic."),
#                                 html.div(
#                                     {"className": "control"},
#                                     html.input(
#                                         {
#                                             "id": "tickets",
#                                             "type": "number",
#                                             "className": "input",
#                                             "value": form_data.get("TicketsPorEquipoAdicional", ""),
#                                             "onChange": lambda e: handle_form_change("TicketsPorEquipoAdicional", e["target"]["value"]),
#                                         }
#                                     ),
#                                 ),
#                             ),
#                         ),
#                     ),
#                 ),
#                 html.footer(
#                     {"className": "modal-card-foot is-justify-content-flex-end"},
#                     html.div(
#                         {"className": "buttons"},
#                         html.button(
#                             {"type": "submit", "className": f"button is-success {'is-loading' if is_loading else ''}", "disabled": is_loading},
#                             "Guardar",
#                         ),
#                         html.button({"type": "button", "className": "button", "onClick": on_close, "disabled": is_loading}, "Cancelar"),
#                     ),
#                 ),
#             ),
#         ),
#     )
