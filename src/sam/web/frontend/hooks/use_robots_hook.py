import asyncio
from typing import Dict

from reactpy import use_callback, use_context, use_effect, use_memo, use_state

from ..api_client import get_api_client
from ..shared.notifications import NotificationContext

# --- Constantes de configuración ---
PAGE_SIZE = 20
INITIAL_FILTERS = {"name": None, "active": True, "online": None}
POLLING_INTERVAL_SECONDS = 15


def use_robots():
    """
    Hook para gestionar el estado del dashboard de robots, incluyendo la carga,
    filtrado, paginación, ordenación y actualización automática.
    """
    api_client = get_api_client()
    notification_ctx = use_context(NotificationContext)

    # --- Estados del hook ---
    robots, set_robots = use_state([])
    loading, set_loading = use_state(True)
    is_syncing, set_is_syncing = use_state(False)  # <-- NUEVO ESTADO
    error, set_error = use_state(None)
    total_count, set_total_count = use_state(0)
    filters, set_filters = use_state(INITIAL_FILTERS)
    current_page, set_current_page = use_state(1)
    sort_by, set_sort_by = use_state("Robot")
    sort_dir, set_sort_dir = use_state("asc")

    # --- Función de carga de datos ---
    @use_callback
    async def load_robots():
        set_loading(True)
        set_error(None)
        try:
            api_params = {
                **filters,
                "page": current_page,
                "size": PAGE_SIZE,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
            api_params = {k: v for k, v in api_params.items() if v is not None}

            data = await api_client.get_robots(api_params)
            set_robots(data.get("robots", []))
            set_total_count(data.get("total_count", 0))
        except Exception as e:
            set_error(str(e))
        finally:
            set_loading(False)

    # --- NUEVA FUNCIÓN DE SINCRONIZACIÓN ---
    @use_callback
    async def trigger_sync(event=None):  # RFR-03: Se añade `event=None`.
        # El handler de evento `on_click` de Reactpy pasa un dict del evento.
        # La función original no aceptaba argumentos, causando un TypeError.
        # Añadir un argumento opcional soluciona el problema.
        if is_syncing:
            return
        set_is_syncing(True)
        notification_ctx["show_notification"]("Iniciando sincronización con A360...", "info")
        try:
            summary = await api_client.trigger_sync()
            notification_ctx["show_notification"](
                f"Sincronización completa. Robots: {summary.get('robots_sincronizados', 0)}, Equipos: {summary.get('equipos_sincronizados', 0)}.",
                "success",
            )
            await load_robots()  # Refresca la tabla después de sincronizar
        except Exception as e:
            notification_ctx["show_notification"](f"Error en la sincronización: {e}", "error")
            set_error(f"Error en la sincronización: {e}")
        finally:
            set_is_syncing(False)

    # --- Efectos y Manejadores ---
    use_effect(load_robots, [filters, current_page, sort_by, sort_dir])

    # Polling effect (sin cambios)
    @use_effect(dependencies=[filters, current_page, sort_by, sort_dir])
    def setup_polling():
        task = asyncio.ensure_future(polling_loop())

        def cleanup():
            task.cancel()

        return cleanup

    async def polling_loop():
        while True:
            await asyncio.sleep(POLLING_INTERVAL_SECONDS)
            try:
                await load_robots()
            except asyncio.CancelledError:
                break
            except Exception as e:
                set_error(f"Error de actualización automática: {e}")

    def handle_sort(column_name: str):
        if sort_by == column_name:
            set_sort_dir("desc" if sort_dir == "asc" else "asc")
        else:
            set_sort_by(column_name)
            set_sort_dir("asc")
        set_current_page(1)

    def handle_set_filters(new_filters_func):
        set_current_page(1)
        set_filters(new_filters_func)

    @use_callback
    async def update_robot_status(robot_id: int, status_data: Dict[str, bool]):
        try:
            await api_client.update_robot_status(robot_id, status_data)
            await load_robots()
        except Exception as e:
            set_error(f"Error al actualizar estado del robot {robot_id}: {e}")

    total_pages = use_memo(lambda: max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE), [total_count])

    # --- Devolvemos los nuevos estados y funciones ---
    return {
        "robots": robots,
        "loading": loading,
        "is_syncing": is_syncing,
        "error": error,
        "total_count": total_count,
        "filters": filters,
        "set_filters": handle_set_filters,
        "update_robot_status": update_robot_status,
        "refresh": load_robots,
        "trigger_sync": trigger_sync,
        "current_page": current_page,
        "set_current_page": set_current_page,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "handle_sort": handle_sort,
    }
