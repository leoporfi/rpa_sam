# ---------------------------------------------------------------------------
# ARCHIVO: src/interfaz_web/features/pools/pool_components.py
# ---------------------------------------------------------------------------
from typing import Callable, Dict, List

from reactpy import component, event, html, use_state

from ...hooks.use_pools_hook import use_pools_management
from ...shared.common_components import ConfirmationModal, LoadingSpinner
from .pool_modals import PoolAssignmentsModal, PoolEditModal


@component
def PoolsDashboard():
    """
    Componente principal para el dashboard de gestión de Pools.
    Utiliza el hook `use_pools_management` para manejar su estado.
    """
    state = use_pools_management()
    pools = state["pools"]
    loading = state["loading"]
    error = state["error"]

    # Estado para controlar qué modal está abierto y con qué datos
    modal_pool, set_modal_pool = use_state(None)
    modal_view, set_modal_view = use_state(None)  # 'edit' o 'assign'
    pool_to_delete, set_pool_to_delete = use_state(None)

    def handle_close_modal():
        set_modal_pool(None)
        set_modal_view(None)

    def handle_edit_click(pool):
        set_modal_pool(pool)
        set_modal_view("edit")

    def handle_assign_click(pool):
        set_modal_pool(pool)
        set_modal_view("assign")

    def handle_delete_click(pool):
        set_pool_to_delete(pool)

    async def handle_confirm_delete():
        if pool_to_delete:
            await state["remove_pool"](pool_to_delete["PoolId"])
            set_pool_to_delete(None)

    async def handle_save_pool(pool_data):
        if pool_data.get("PoolId"):
            await state["edit_pool"](pool_data["PoolId"], pool_data)
        else:
            await state["add_pool"](pool_data)

    if error:
        return html.article({"aria-invalid": "true"}, f"Error: {error}")
    if loading and not pools:
        return LoadingSpinner()

    return html.section(
        html.div(
            {"className": "grid"},
            html.h2("Gestión de Pools de Recursos"),
            html.div(
                {"style": {"textAlign": "right"}},
                html.button(
                    {"onClick": lambda e: handle_edit_click({})},
                    html.i({"className": "fa-solid fa-plus", "aria-hidden": "true"}),
                    " Crear Nuevo Pool",
                ),
            ),
        ),
        PoolsTable(
            pools=pools,
            on_edit=handle_edit_click,
            on_assign=handle_assign_click,
            on_delete=handle_delete_click,
        ),
        # Renderizado condicional de modales
        PoolEditModal(
            pool=modal_pool if modal_view == "edit" else None,
            on_close=handle_close_modal,
            on_save=handle_save_pool,
        ),
        PoolAssignmentsModal(
            pool=modal_pool if modal_view == "assign" else None,
            on_close=handle_close_modal,
            on_save_success=state["refresh"],
        ),
        ConfirmationModal(
            is_open=bool(pool_to_delete),
            title="Confirmar Eliminación",
            message=f"¿Estás seguro de que quieres eliminar el pool '{pool_to_delete['Nombre'] if pool_to_delete else ''}'? Esta acción no se puede deshacer.",
            on_confirm=handle_confirm_delete,
            on_cancel=lambda: set_pool_to_delete(None),
        ),
    )


@component
def PoolsTable(pools: List[Dict], on_edit: Callable, on_assign: Callable, on_delete: Callable):
    """Tabla que muestra la lista de pools."""
    return html.article(
        html.div(
            {"className": "table-container"},
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
                    else html.tr(html.td({"colSpan": 5, "style": {"textAlign": "center"}}, "No se encontraron pools."))
                ),
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
                {"className": "grid"},
                html.a(
                    {
                        "href": "#",
                        "onClick": event(lambda e: on_edit(pool), prevent_default=True),
                        "data-tooltip": "Editar Pool",
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-pencil"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "onClick": event(lambda e: on_assign(pool), prevent_default=True),
                        "data-tooltip": "Asignar Recursos",
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-link"}),
                ),
                html.a(
                    {
                        "href": "#",
                        "onClick": event(lambda e: on_delete(pool), prevent_default=True),
                        "data-tooltip": "Eliminar Pool",
                        "data-placement": "left",
                        "className": "secondary",
                    },
                    html.i({"className": "fa-solid fa-trash-alt"}),
                ),
            )
        ),
    )
