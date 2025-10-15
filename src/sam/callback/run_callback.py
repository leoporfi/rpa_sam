import logging
import signal
import sys

import uvicorn

# --- Constantes ---
SERVICE_NAME = "callback"
server_instance = None


def graceful_shutdown(signum, frame):
    """Maneja las señales de cierre de forma ordenada."""
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if server_instance:
        server_instance.should_exit = True


def main():
    """
    Función principal que lee la configuración del servidor y ejecuta Uvicorn.
    La creación de la app y sus dependencias ahora es gestionada por el 'lifespan' de FastAPI.
    """
    global server_instance

    try:
        # Es necesario inicializar ConfigLoader aquí para poder leer la configuración de uvicorn del .env
        from sam.common.config_loader import ConfigLoader

        if not ConfigLoader.is_initialized():
            ConfigLoader.initialize_service(SERVICE_NAME)

        from sam.common.config_manager import ConfigManager
        from sam.common.logging_setup import setup_logging

        setup_logging(service_name=SERVICE_NAME)
        logging.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}...")

        # Configurar manejadores de señales
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

        server_config = ConfigManager.get_callback_server_config()
        log_config = ConfigManager.get_log_config()

        host = server_config.get("host", "0.0.0.0")
        port = server_config.get("port", 8008)
        workers = server_config.get("threads", 1)
        log_level = log_config.get("level_str", "info").lower()

        logging.info(f"Configuración del servidor: http://{host}:{port} con {workers} worker(s)...")

        # Crear configuración de servidor
        config = uvicorn.Config(
            "sam.callback.service.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
        )
        server_instance = uvicorn.Server(config)

        logging.info("Servidor Uvicorn iniciado correctamente.")
        server_instance.run()

    except KeyboardInterrupt:
        logging.info("Interrupción de teclado detectada (Ctrl+C).")
    except Exception as e:
        logging.critical(f"Error crítico no controlado al iniciar el servicio {SERVICE_NAME}: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logging.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución.")
        sys.exit(1)


# El __main__.py del servicio llamará a esta función main()
# if __name__ == "__main__":
#     main()
# (No es necesario, __main__.py ya se encarga de esto)
