# ---------------------------------------------------------------------------
# ARCHIVO: src/interfaz_web/hooks/use_robots_hook.py
# ---------------------------------------------------------------------------
# NOTA: He añadido la lógica de sondeo (polling) para que los datos
# se actualicen automáticamente cada 15 segundos.
# ---------------------------------------------------------------------------
import asyncio
from typing import Dict

from backend.schemas import RobotFilters
from frontend.api_client import get_api_client
from reactpy import use_callback, use_effect, use_memo, use_state

# --- Constantes de configuración ---
PAGE_SIZE = 20
INITIAL_FILTERS = {"name": None, "active": True, "online": None}
POLLING_INTERVAL_SECONDS = 15  # <--- NUEVO: Intervalo de actualización en segundos


def use_robots():
    """
    Hook para gestionar el estado del dashboard de robots, incluyendo la carga,
    filtrado, paginación, ordenación y actualización automática.
    """
    api_client = get_api_client()

    # --- Estados del hook ---
    robots, set_robots = use_state([])
    loading, set_loading = use_state(True)
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

    # --- Efecto para la carga inicial y cuando cambian las dependencias ---
    use_effect(load_robots, [filters, current_page, sort_by, sort_dir])

    # --- NUEVO: Efecto para la actualización automática (Polling) ---
    @use_effect(dependencies=[filters, current_page, sort_by, sort_dir])
    def setup_polling():
        """
        Este efecto establece un bucle que llama a `load_robots` periódicamente.
        """
        # Se crea una tarea asíncrona que se ejecutará en segundo plano.
        task = asyncio.ensure_future(polling_loop())

        # La función de limpieza es crucial: se ejecuta cuando el componente
        # se "desmonta" o cuando las dependencias cambian, cancelando la
        # tarea anterior para evitar fugas de memoria o ejecuciones múltiples.
        def cleanup():
            task.cancel()

        return cleanup

    async def polling_loop():
        """
        Bucle infinito que espera el intervalo definido y luego recarga los datos.
        """
        while True:
            await asyncio.sleep(POLLING_INTERVAL_SECONDS)
            try:
                # No queremos que el spinner de "Cargando..." aparezca en cada
                # actualización de fondo, por lo que no llamamos a set_loading(True) aquí.
                # La recarga será silenciosa para el usuario.
                await load_robots()
            except asyncio.CancelledError:
                # Si la tarea se cancela, salimos del bucle limpiamente.
                break
            except Exception as e:
                # Si hay un error durante el polling, lo mostramos en el estado.
                set_error(f"Error de actualización automática: {e}")

    # --- Manejadores de eventos  ---
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

    return {
        "robots": robots,
        "loading": loading,
        "error": error,
        "total_count": total_count,
        "filters": filters,
        "set_filters": handle_set_filters,
        "update_robot_status": update_robot_status,
        "refresh": load_robots,
        "current_page": current_page,
        "set_current_page": set_current_page,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "handle_sort": handle_sort,
    }
