import asyncio
from typing import Callable

from reactpy import component, create_context, event, html, use_context, use_effect, use_state

# El contexto no cambia, es lógica pura.
NotificationContext = create_context(None)


@component
def Toast(message: str, style: str, on_dismiss: Callable):
    """
    Una notificación (toast) individual, estilizada para Pico.css.
    Soporta diferentes estilos: success, error, warning, info
    """
    # 1. Añadimos un estado local para controlar la visibilidad y la animación de entrada.
    is_visible, set_is_visible = use_state(False)

    # 2. El primer use_effect se encarga de la animación de ENTRADA.
    # Se ejecuta una sola vez cuando el componente se monta.
    @use_effect(dependencies=[])
    def animate_in():
        # Cambiamos el estado a visible justo después del renderizado inicial.
        # Esto añade la clase 'show' y dispara la transición CSS.
        set_is_visible(True)

    # 3. El segundo use_effect se encarga del auto-descarte (SALIDA).
    # Este código ya era correcto.
    @use_effect(dependencies=[])
    def setup_auto_dismiss():
        dismiss_task = asyncio.create_task(dismiss_after_delay(on_dismiss))

        def cleanup():
            dismiss_task.cancel()

        return cleanup

    style_config = {
        "success": {"className": "toast-success", "icon": "✓", "aria_label": "Mensaje de éxito"},
        "error": {"className": "toast-error", "icon": "✕", "aria_label": "Mensaje de error", "aria_invalid": "true"},
        "warning": {"className": "toast-warning", "icon": "⚠", "aria_label": "Mensaje de advertencia"},
        "info": {"className": "toast-info", "icon": "ℹ", "aria_label": "Mensaje informativo"},
    }
    config = style_config.get(style, style_config["info"])

    # 4. Construimos la clase dinámicamente: añadimos 'show' si is_visible es True.
    final_className = f"toast {config['className']}"
    if is_visible:
        final_className += " show"

    attributes = {"key": message, "className": final_className, "role": "alert", "aria-label": config["aria_label"]}
    if config.get("aria_invalid"):
        attributes["aria-invalid"] = config["aria_invalid"]

    return html.article(
        attributes,
        html.div(
            {"className": "toast-content"},
            html.div(
                {"className": "toast-message"},
                html.span({"className": "toast-icon"}, config["icon"]),
                html.span({"className": "toast-text"}, message),
            ),
            html.button(
                {"className": "toast-close", "aria-label": "Cerrar notificación", "onClick": event(lambda e: on_dismiss(), prevent_default=True)}, "×"
            ),
        ),
    )


async def dismiss_after_delay(on_dismiss_callback: Callable):
    """Auto-dismiss después de 5 segundos"""
    await asyncio.sleep(5)
    try:
        on_dismiss_callback()
    except Exception:
        pass  # El componente ya no existe


@component
def ToastContainer():
    """Contenedor para todas las notificaciones"""
    notification_ctx = use_context(NotificationContext)
    if not notification_ctx:
        return None

    notifications = notification_ctx["notifications"]
    dismiss_notification = notification_ctx["dismiss_notification"]

    return html.div(
        {"className": "toast-container"},
        html.div(
            {"className": "toast-stack"},
            [
                Toast(
                    key=n["id"],
                    message=n["message"],
                    style=n["style"],
                    on_dismiss=lambda event=None, nid=n["id"]: dismiss_notification(nid),
                )
                for n in notifications
            ],
        ),
    )
