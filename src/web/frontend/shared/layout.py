# ARCHIVO: src/interfaz_web/shared/layout.py
from typing import Callable

from reactpy import component, html

from .common_components import ThemeSwitcher


@component
def AppLayout(children, theme_is_dark: bool, on_theme_toggle: Callable, current_path: str = "/", page_controls=None):
    """
    Layout principal que ahora acepta 'page_controls' para renderizarlos en el header.
    """
    return html._(
        html.header(
            {"className": "sticky-header"},
            Header(
                theme_is_dark=theme_is_dark,
                on_theme_toggle=on_theme_toggle,
                current_path=current_path,
                page_controls=page_controls,  # <-- Pasamos los controles al Header
            ),
        ),
        html.main(
            {"className": "container"},
            *children,
        ),
    )


@component
def Header(theme_is_dark: bool, on_theme_toggle: Callable, current_path: str = "/", page_controls=None):
    """
    Header que renderiza la navegación principal y, opcionalmente, los controles
    específicos de la página actual.
    """

    def get_nav_classes(path: str) -> str:
        return "contrast" if current_path == path else "secondary"

    def is_active(path: str) -> bool:
        return current_path == path

    return html.div(
        {"className": "container"},
        # Navegación principal (se mantiene igual)
        html.nav(
            html.ul(
                html.li(
                    html.strong(
                        html.a(
                            {"href": "/", "className": "contrast", "aria-current": "page" if is_active("/") else ""},
                            "SAM",
                        )
                    )
                ),
                html.li(
                    html.a(
                        {"href": "/pools", "className": get_nav_classes("/pools"), "aria-current": "page" if is_active("/pools") else ""},
                        "Pools",
                    )
                ),
            ),
            html.ul(html.li(ThemeSwitcher(is_dark=theme_is_dark, on_toggle=on_theme_toggle))),
        ),
        # <<-- NUEVO: Contenedor para los controles de página -->>
        html.div(
            {"className": "page-controls-container"},
            page_controls if page_controls else "",
        ),
    )


@component
def Footer(): ...
