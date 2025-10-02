# src/web/features/pools/hooks.py
from reactpy import use_callback, use_effect, use_state

from ...api_client import get_api_client


def use_pools():
    pools, set_pools = use_state([])
    loading, set_loading = use_state(True)
    error, set_error = use_state(None)
    api_client = get_api_client()

    @use_callback
    async def load_pools():
        set_loading(True)
        set_error(None)
        try:
            # Asumimos que el api_client tendrá un método get_pools
            data = await api_client.get_pools()
            set_pools(data)
        except Exception as e:
            set_error(str(e))
        finally:
            set_loading(False)

    use_effect(load_pools, [])

    return {
        "pools": pools,
        "loading": loading,
        "error": error,
        "refresh": load_pools,
    }
