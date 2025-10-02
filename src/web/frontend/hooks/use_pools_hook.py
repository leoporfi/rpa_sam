# ---------------------------------------------------------------------------
# ARCHIVO: src/interfaz_web/hooks/use_pools_hook.py
# ---------------------------------------------------------------------------
# NOTA: He consolidado la lógica de los dos archivos de hooks que me pasaste
# en este único hook más completo, siguiendo el patrón de `use_robots_hook.py`.
# ---------------------------------------------------------------------------
from reactpy import use_callback, use_effect, use_state

from ..api_client import get_api_client


def use_pools_management():
    """
    Hook completo para la gestión de pools (CRUD y refresh).
    Centraliza toda la lógica de estado y las llamadas a la API para los pools.
    """
    api_client = get_api_client()
    pools, set_pools = use_state([])
    loading, set_loading = use_state(True)
    error, set_error = use_state(None)

    @use_callback
    async def load_pools():
        """Carga o recarga la lista de pools desde el backend."""
        set_loading(True)
        set_error(None)
        try:
            data = await api_client.get_pools()
            set_pools(data)
        except Exception as e:
            set_error(str(e))
        finally:
            set_loading(False)

    # Efecto para cargar los datos iniciales cuando el componente se monta
    use_effect(load_pools, [])

    @use_callback
    async def add_pool(pool_data):
        """Crea un nuevo pool y recarga la lista."""
        await api_client.create_pool(pool_data)
        await load_pools()

    @use_callback
    async def edit_pool(pool_id, pool_data):
        """Actualiza un pool existente y recarga la lista."""
        await api_client.update_pool(pool_id, pool_data)
        await load_pools()

    @use_callback
    async def remove_pool(pool_id):
        """Elimina un pool y recarga la lista."""
        await api_client.delete_pool(pool_id)
        await load_pools()

    return {
        "pools": pools,
        "loading": loading,
        "error": error,
        "refresh": load_pools,
        "add_pool": add_pool,
        "edit_pool": edit_pool,
        "remove_pool": remove_pool,
    }
