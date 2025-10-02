# ARCHIVO: src/interfaz_web/shared/layout.py
from typing import Callable

from reactpy import component, html

from .common_components import ThemeSwitcher


@component
def AppLayout(children, theme_is_dark: bool, on_theme_toggle: Callable, current_path: str = "/"):
    """
    Layout principal que ahora recibe y pasa los props del tema y la ruta actual.
    """
    return html._(
        Header(theme_is_dark=theme_is_dark, on_theme_toggle=on_theme_toggle, current_path=current_path),
        html.main(
            {"className": "container"},
            *children,
        ),
    )


@component
def Header(theme_is_dark: bool, on_theme_toggle: Callable, current_path: str = "/"):
    """
    Header que ahora recibe los props y renderiza el ThemeSwitcher.
    Recibe current_path para marcar el enlace activo.
    """

    # Función helper para determinar las clases CSS
    def get_nav_classes(path: str) -> str:
        if current_path == path:
            return "contrast"  # Clase para el enlace activo
        return "secondary"  # Clase por defecto

    # Función helper para determinar si un enlace está activo
    def is_active(path: str) -> bool:
        return current_path == path

    return html.header(
        {"className": "container"},
        html.a({"aria-label": "SAM", "data-discover": "true", "href": "/"}),
        html.nav(
            # Lado izquierdo: Logo y Links
            html.ul(
                html.li(
                    html.strong(
                        html.a(
                            {
                                "href": "/",
                                "className": "contrast",
                                # Agregar atributo aria-current para accesibilidad
                                **({"aria-current": "page"} if is_active("/") else {}),
                            },
                            "SAM",
                        )
                    )
                ),
                html.li(
                    html.a(
                        {
                            "href": "/pools",
                            "className": get_nav_classes("/pools"),
                            # Agregar atributo aria-current para accesibilidad
                            **({"aria-current": "page"} if is_active("/pools") else {}),
                        },
                        "Pools",
                    )
                ),
                # Ejemplos de cómo agregar más enlaces cuando los descomentes:
                # html.li(
                #     html.a(
                #         {
                #             "href": "/robots",
                #             "className": get_nav_classes("/robots"),
                #             **({"aria-current": "page"} if is_active("/robots") else {})
                #         },
                #         "Robots"
                #     )
                # ),
            ),
            # Lado derecho: Interruptor del tema
            html.ul(html.li(ThemeSwitcher(is_dark=theme_is_dark, on_toggle=on_theme_toggle))),
        ),
    )


@component
def Footer(): ...
