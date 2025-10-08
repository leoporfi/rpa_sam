import logging
import sys

import uvicorn

# Ya no necesitamos importar dependencias aquí, el lifespan se encarga.
from sam.common.config_manager import ConfigManager

# --- Constantes ---
SERVICE_NAME = "callback"


def main():
    """
    Función principal que lee la configuración del servidor y ejecuta Uvicorn.
    La creación de la app y sus dependencias ahora es gestionada por el 'lifespan' de FastAPI.
    """
    # NOTA: El logging y ConfigLoader ahora se inicializan DENTRO de cada worker
    # a través del lifespan en 'main.py', por lo que no se llaman aquí.

    try:
        # 1. Cargar solo la configuración del servidor necesaria para Uvicorn.
        # Es necesario inicializar ConfigLoader aquí para poder leer la configuración.
        from sam.common.config_loader import ConfigLoader

        if not ConfigLoader.is_initialized():
            ConfigLoader.initialize_service(SERVICE_NAME)

        server_config = ConfigManager.get_callback_server_config()
        log_config = ConfigManager.get_log_config()

        host = server_config.get("host", "0.0.0.0")
        port = server_config.get("port", 8008)
        workers = server_config.get("threads", 5)
        log_level = log_config.get("level_str", "info").lower()

        # Usamos print() porque el logging aún no está configurado en este proceso principal.
        print(f"[{SERVICE_NAME.upper()}] Iniciando Uvicorn en http://{host}:{port} con {workers} worker(s)...")

        # 2. Ejecutar Uvicorn usando el "import string".
        # Uvicorn se encargará de lanzar los workers, y cada worker ejecutará el 'lifespan'.
        uvicorn.run(
            "sam.callback.service.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
        )

    except Exception as e:
        # Error crítico durante el arranque (ej. .env no encontrado)
        print(f"CRÍTICO: Error no controlado al iniciar el servicio {SERVICE_NAME}: {e}", file=sys.stderr)
        # Imprime el traceback para más detalles
        import traceback

        traceback.print_exc()
        sys.exit(1)


# El __main__.py del servicio llamará a esta función main().
