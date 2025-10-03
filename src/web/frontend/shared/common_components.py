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
        html.div(
            html.button(
                {"className": "secondary", "onClick": handle_previous, "disabled": is_first_page},
                "Anterior",
            )
        ),
        html.div(
            {"style": {"textAlign": "center", "lineHeight": "2.5rem"}},
            f"Página {current_page} de {total_pages}",
        ),
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
            "Cargando datos...",
        ),
    )


@component
def ActionMenu(actions: List[Dict[str, any]]):
    """
    Menú desplegable de acciones que usa la estructura <details> de Pico.css.
    """
    return html.details(
        {"className": "dropdown"},
        html.summary(
            {"role": "", "className": "outline"},
        ),
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
    Un interruptor para cambiar entre tema claro y oscuro, con iconos de sol y luna.
    """

    def handle_change(event):
        on_toggle(event["target"]["checked"])

    return html.label(
        {"htmlFor": "theme-switcher", "className": "theme-switcher"},
        html.span({"className": "material-symbols-outlined"}, "light_mode"),
        html.input(
            {
                "type": "checkbox",
                "id": "theme-switcher",
                "role": "switch",
                "checked": is_dark,
                "onChange": handle_change,
            }
        ),
        html.span({"className": "material-symbols-outlined"}, "dark_mode"),
    )


@component
def ConfirmationModal(is_open: bool, title: str, message: str, on_confirm: Callable, on_cancel: Callable):
    """Un modal genérico para solicitar confirmación del usuario."""
    if not is_open:
        return None

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
                    html.button(
                        {
                            "onClick": handle_confirm_click,
                            "style": {"backgroundColor": "var(--pico-color-pink-550)", "borderColor": "var(--pico-color-pink-550)"},
                        },
                        "Confirmar",
                    ),
                ),
            ),
        ),
    )
