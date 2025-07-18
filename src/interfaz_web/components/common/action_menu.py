# src/interfaz_web/components/common/action_menu.py
from typing import List, Dict
from reactpy import component, html, use_state


@component
def ActionMenu(actions: List[Dict[str, any]]):
    """
    Menú desplegable de acciones genérico, estilizado con el componente 'dropdown' de Bulma.
    """
    is_visible, set_is_visible = use_state(False)

    def handle_item_click(action_callback):
        # Función wrapper para ejecutar la acción y luego cerrar el menú.
        async def do_action(event=None):
            await action_callback(event)
            set_is_visible(False)

        return do_action

    # Clases para el dropdown, se añade 'is-active' para mostrarlo.
    dropdown_class = f"dropdown is-right {'is-active' if is_visible else ''}"

    return html.div(
        {"className": dropdown_class},
        # El botón que activa el dropdown
        html.div(
            {"className": "dropdown-trigger"},
            html.button(
                {
                    "className": "button is-small",  # Botón estándar de Bulma
                    "aria-haspopup": "true",
                    "aria-controls": "dropdown-menu",
                    "onClick": lambda event: set_is_visible(not is_visible),
                },
                html.span("Acciones"),
                html.span(
                    {"className": "icon is-small"},
                    html.i({"className": "fas fa-angle-down", "aria-hidden": "true"}),
                ),
            ),
        ),
        # El menú desplegable que se muestra u oculta
        html.div(
            {"className": "dropdown-menu", "id": "dropdown-menu", "role": "menu"},
            html.div(
                {"className": "dropdown-content"},
                # Se renderizan las acciones que vienen por props
                *[
                    html.button(
                        {
                            "key": action["label"],
                            "className": f"dropdown-item has-text-left {'is-danger' if action.get('is_danger') else ''}",
                            "onClick": handle_item_click(action["on_click"]),
                        },
                        action["label"],
                    )
                    for action in actions
                ],
            ),
        ),
    )
