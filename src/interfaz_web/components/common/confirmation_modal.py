from typing import Callable

from reactpy import component, html


@component
def ConfirmationModal(
    is_active: bool,
    on_close: Callable,
    on_confirm: Callable,
    title: str,
    message: str,
    confirm_text: str = "Confirmar",
    cancel_text: str = "Cancelar",
    is_loading: bool = False,
):
    """
    Un modal de confirmación genérico.
    """
    modal_class = "modal is-active" if is_active else "modal"

    return html.div(
        {"className": modal_class},
        html.div({"className": "modal-background", "onClick": on_close}),
        html.div(
            {"className": "modal-card"},
            html.header(
                {"className": "modal-card-head"},
                html.p({"className": "modal-card-title"}, title),
                html.button({"className": "delete", "aria-label": "close", "onClick": on_close}),
            ),
            html.section(
                {"className": "modal-card-body"},
                html.p(message),
            ),
            html.footer(
                {"className": "modal-card-foot"},
                html.button(
                    {
                        "className": f"button is-success {'is-loading' if is_loading else ''}",
                        "onClick": on_confirm,
                        "disabled": is_loading,
                    },
                    confirm_text,
                ),
                html.button(
                    {"className": "button", "onClick": on_close, "disabled": is_loading},
                    cancel_text,
                ),
            ),
        ),
    )
