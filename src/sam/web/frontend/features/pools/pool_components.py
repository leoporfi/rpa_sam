# /src/web/features/pools/pool_components.py

from typing import Callable, Dict, List

from reactpy import component, event, html

from ...shared.common_components import LoadingSpinner


@component
def PoolsControls(on_create_pool: Callable):
    """Controles para el dashboard de Pools."""
    return html.div(
        {"class_name": "grid"},
        html.h2("Gestión de Pools de Recursos"),
        html.div(
            {"style": {"text_align": "right"}},
            html.button(
                {"on_click": on_create_pool},
                html.i({"class_name": "fa-solid fa-plus", "aria-hidden": "true"}),
                " Crear Nuevo Pool",
            ),
        ),
    )


@component
def PoolsDashboard(
    pools: List[Dict], on_edit: Callable, on_assign: Callable, on_delete: Callable, loading: bool, error: str
):
    """Componente principal que ahora solo renderiza la tabla/tarjetas."""
    if error:
        return html.article({"aria_invalid": "true"}, f"Error: {error}")
    if loading and not pools:
        return LoadingSpinner()

    return html._(
        html.div(
            {"class_name": "cards-container pool-cards"},
            *[PoolCard(pool=p, on_edit=on_edit, on_assign=on_assign, on_delete=on_delete) for p in pools],
        ),
        html.div(
            {"class_name": "table-container"},
            PoolsTable(pools=pools, on_edit=on_edit, on_assign=on_assign, on_delete=on_delete),
        ),
    )


@component
def PoolsTable(pools: List[Dict], on_edit: Callable, on_assign: Callable, on_delete: Callable):
    """Tabla que muestra la lista de pools."""
    return html.article(
        html.table(
            html.thead(
                html.tr(
                    html.th("Nombre"),
                    html.th("Descripción"),
                    html.th("Robots"),
                    html.th("Equipos"),
                    html.th("Acciones"),
                )
            ),
            html.tbody(
                *[PoolRow(pool=p, on_edit=on_edit, on_assign=on_assign, on_delete=on_delete) for p in pools]
                if pools
                # RFR-17: Mensaje descriptivo cuando no hay datos.
                else html.tr(html.td({"colSpan": 5, "style": {"textAlign": "center"}}, "No se encontraron pools."))
            ),
        )
    )


@component
def PoolRow(pool: Dict, on_edit: Callable, on_assign: Callable, on_delete: Callable):
    """Fila individual para la tabla de pools."""
    return html.tr(
        {"key": pool["PoolId"]},
        html.td(pool["Nombre"]),
        html.td(pool.get("Descripcion", "-")),
        html.td(str(pool.get("CantidadRobots", 0))),
        html.td(str(pool.get("CantidadEquipos", 0))),
        html.td(
            html.div(
                {"class_name": "grid"},
                html.a(
                    {
                        "href": "#",
                        "on_click": event(lambda e: on_edit(pool), prevent_default=True),
                        "data-tooltip": "Editar Pool",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-pencil"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "on_click": event(lambda e: on_assign(pool), prevent_default=True),
                        "data-tooltip": "Asignar Recursos",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-link"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "on_click": event(lambda e: on_delete(pool), prevent_default=True),
                        "data-tooltip": "Eliminar Pool",
                        "data-placement": "left",
                        "class_name": "secondary",
                    },
                    html.i({"class_name": "fa-solid fa-trash-alt"}),
                ),
            )
        ),
    )


@component
def PoolCard(pool: Dict, on_edit: Callable, on_assign: Callable, on_delete: Callable):
    """Tarjeta individual para la vista móvil de pools."""
    return html.article(
        {"key": pool["PoolId"], "class_name": "pool-card"},
        html.div(
            {"class_name": "pool-card-header"},
            html.h5(pool["Nombre"]),
            html.small(pool.get("Descripcion", "")),
        ),
        html.div(
            {"class_name": "pool-card-body"},
            html.div(
                {"class_name": "resource-counts"},
                html.span(html.i({"class_name": "fa-solid fa-robot"}), f" {pool.get('CantidadRobots', 0)} Robots"),
                html.span(html.i({"class_name": "fa-solid fa-computer"}), f" {pool.get('CantidadEquipos', 0)} Equipos"),
            ),
        ),
        html.footer(
            {"class_name": "pool-card-footer"},
            html.button({"class_name": "outline secondary", "on_click": lambda e: on_edit(pool)}, "Editar"),
            html.button({"class_name": "outline secondary", "on_click": lambda e: on_assign(pool)}, "Asignar"),
            html.button({"class_name": "outline secondary", "on_click": lambda e: on_delete(pool)}, "Eliminar"),
        ),
    )
