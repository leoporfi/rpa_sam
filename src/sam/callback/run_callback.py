import logging
import sys

import uvicorn

# --- Constantes ---
SERVICE_NAME = "callback"


def main():
    """
    Función principal que lee la configuración del servidor y ejecuta Uvicorn.
    La creación de la app y sus dependencias ahora es gestionada por el 'lifespan' de FastAPI.
    """
    try:
        # Es necesario inicializar ConfigLoader aquí para poder leer la configuración de uvicorn del .env
        from sam.common.config_loader import ConfigLoader

        if not ConfigLoader.is_initialized():
            ConfigLoader.initialize_service(SERVICE_NAME)

        from sam.common.config_manager import ConfigManager

        server_config = ConfigManager.get_callback_server_config()
        log_config = ConfigManager.get_log_config()

        host = server_config.get("host", "0.0.0.0")
        port = server_config.get("port", 8008)
        workers = server_config.get("threads", 1)
        log_level = log_config.get("level_str", "info").lower()

        # Usamos print() porque el logging para este proceso principal no es necesario.
        # El logging real se configura en cada worker a través del lifespan.
        print(f"[{SERVICE_NAME.upper()}] Iniciando Uvicorn en http://{host}:{port} con {workers} worker(s)...")

        # Ejecutar Uvicorn usando el "import string".
        # Uvicorn lanzará los workers, y cada worker ejecutará el 'lifespan' definido en main.py
        uvicorn.run(
            "sam.callback.service.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
        )

    except Exception as e:
        # Este bloque captura errores críticos durante el arranque (ej. .env no encontrado)
        print(f"CRÍTICO: Error no controlado al iniciar el servicio {SERVICE_NAME}: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


# El __main__.py del servicio llamará a esta función main()
# if __name__ == "__main__":
#     main()
# (No es necesario, __main__.py ya se encarga de esto)
