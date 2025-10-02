from typing import Callable, Dict, List

from reactpy import component, event, html


@component
def Pagination(current_page: int, total_pages: int, on_page_change: Callable):
    """
    Componente de paginación refactorizado para Pico.css usando un grid.
    """
    is_first_page = current_page == 1
    is_last_page = current_page == total_pages

    def handle_previous(e):
        if not is_first_page:
            on_page_change(current_page - 1)

    def handle_next(e):
        if not is_last_page:
            on_page_change(current_page + 1)

    return html.nav(
        {"className": "grid"},
        # Botón Anterior (a la izquierda)
        html.div(
            html.button(
                {"className": "secondary", "onClick": handle_previous, "disabled": is_first_page},
                "Anterior",
            )
        ),
        # Contador de Página (centrado)
        html.div(
            {"style": {"textAlign": "center", "lineHeight": "2.5rem"}},
            f"Página {current_page} de {total_pages}",
        ),
        # Botón Siguiente (a la derecha)
        html.div(
            {"style": {"textAlign": "right"}},
            html.button(
                {"className": "secondary", "onClick": handle_next, "disabled": is_last_page},
                "Siguiente",
            ),
        ),
    )


@component
def LoadingSpinner():
    """
    Un spinner de carga estilizado usando el atributo aria-busy de Pico.css.
    """
    return html.div(
        {"className": "container", "style": {"textAlign": "center", "padding": "2rem"}},
        html.article(
            {"aria-busy": "true"},
            # El texto dentro del elemento se muestra mientras carga
            "Cargando datos...",
        ),
    )


@component
def ActionMenu(actions: List[Dict[str, any]]):
    """
    Menú desplegable de acciones que usa la estructura <details> de Pico.css.
    Es semántico y no necesita estado para funcionar.
    """
    return html.details(
        # La clase 'dropdown' le da el estilo y posicionamiento correcto.
        {"className": "dropdown"},
        # Esto es lo que se ve siempre: el icono de 3 puntos.
        html.summary(
            {"role": "", "className": "outline"},
            # html.i({"className": "fas fa-ellipsis-v"}),
        ),
        # Esto es lo que se despliega.
        html.ul(
            {"role": "listbox"},
            *[
                html.li(html.a({"href": "#", "onClick": event(action["on_click"], prevent_default=True)}, html.small(action["label"])))
                for action in actions
            ],
        ),
    )


@component
def ThemeSwitcher(is_dark: bool, on_toggle: Callable):
    """
    Un interruptor para cambiar entre el tema claro y oscuro.
    """

    def handle_change(event):
        on_toggle(event["target"]["checked"])

    return html.fieldset(
        html.label(
            html.input({"type": "checkbox", "role": "switch", "checked": is_dark, "onChange": handle_change}),
            "Tema Oscuro" if is_dark else "Tema Claro",
        )
    )


@component
def ConfirmationModal(is_open: bool, title: str, message: str, on_confirm: Callable, on_cancel: Callable):
    """Un modal genérico para solicitar confirmación del usuario."""
    if not is_open:
        return None

    # Envolvemos la llamada asíncrona en un manejador
    async def handle_confirm_click(event):
        await on_confirm()

    return html.dialog(
        {"open": True},
        html.article(
            html.header(
                html.button({"aria-label": "Close", "rel": "prev", "onClick": lambda e: on_cancel()}),
                html.h3(title),
            ),
            html.p(message),
            html.footer(
                html.div(
                    {"className": "grid"},
                    html.button({"className": "secondary", "onClick": lambda e: on_cancel()}, "Cancelar"),
                    # Usamos un botón con un color que indique peligro/acción destructiva
                    html.button(
                        {
                            # "className": "pico-color-red-550",
                            "onClick": handle_confirm_click,
                            "style": {"backgroundColor": "var(--pico-color-pink-550)", "borderColor": "var(--pico-color-pink-550)"},
                        },
                        "Confirmar",
                    ),
                ),
            ),
        ),
    )
