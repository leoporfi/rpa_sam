# src/interfaz_web/hooks/use_robots.py
from typing import Any, Dict, Optional

from reactpy import use_callback, use_effect, use_memo, use_state

from ..schemas.robot_types import RobotFilters
from ..services.api_service import get_api_service

PAGE_SIZE = 20
INITIAL_FILTERS = {"name": None, "active": True, "online": None}


def use_robots():
    api_service = get_api_service()

    robots, set_robots = use_state([])
    loading, set_loading = use_state(True)
    error, set_error = use_state(None)
    total_count, set_total_count = use_state(0)
    filters, set_filters = use_state(INITIAL_FILTERS)
    current_page, set_current_page = use_state(1)

    sort_by, set_sort_by = use_state("Robot")
    sort_dir, set_sort_dir = use_state("asc")

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
            # Se eliminan los filtros con valor None para no ensuciar la URL
            api_params = {k: v for k, v in api_params.items() if v is not None}

            data = await api_service.get_robots(api_params)
            set_robots(data.get("robots", []))
            set_total_count(data.get("total_count", 0))
        except Exception as e:
            set_error(str(e))
        finally:
            set_loading(False)

    use_effect(load_robots, [filters, current_page, sort_by, sort_dir])

    def handle_sort(column_name: str):
        if sort_by == column_name:
            set_sort_dir("desc" if sort_dir == "asc" else "asc")
        else:
            set_sort_by(column_name)
            set_sort_dir("asc")
        set_current_page(1)  # Volver a la página 1 al cambiar la ordenación

    def handle_set_filters(new_filters_func):
        set_current_page(1)
        set_filters(new_filters_func)

    @use_callback
    async def update_robot_status(robot_id: int, status_data: Dict[str, bool], show_notification):
        try:
            await api_service.update_robot_status(robot_id, status_data)
            await load_robots()
            show_notification("Estado del robot actualizado con éxito.", "success")
        except Exception as e:
            set_error(f"Error al actualizar estado del robot {robot_id}: {e}")
            show_notification(f"Error al actualizar estado del robot: {e}", "danger")

    total_pages = use_memo(lambda: max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE), [total_count])

    @use_callback
    async def delete_robot(robot_id: int, show_notification):
        try:
            await api_service.delete_robot(robot_id)
            await load_robots()  # Recargar la lista después de eliminar
            show_notification("Robot eliminado con éxito.", "success")
        except Exception as e:
            set_error(f"Error al eliminar el robot {robot_id}: {e}")
            show_notification(f"Error al eliminar el robot: {e}", "danger")

    # --- EXPONEMOS LOS NUEVOS ESTADOS Y MANEJADORES ---
    return {
        "robots": robots,
        "loading": loading,
        "error": error,
        "total_count": total_count,
        "filters": filters,
        "set_filters": handle_set_filters,
        "update_robot_status": update_robot_status,
        "delete_robot": delete_robot,
        "refresh": load_robots,
        "current_page": current_page,
        "set_current_page": set_current_page,
        "total_pages": total_pages,
        "page_size": PAGE_SIZE,
        # Nuevos valores expuestos
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "handle_sort": handle_sort,
    }
