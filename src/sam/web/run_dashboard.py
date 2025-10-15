# sam/web/run_dashboard.py
import logging
import signal
import sys

import uvicorn

# --- Importaciones del Proyecto ---
from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging

# Importamos la app y la fábrica desde main
from sam.web.main import create_app

# --- Constantes ---
SERVICE_NAME = "interfaz_web"
server_instance = None


def graceful_shutdown(signum, frame):
    """Maneja las señales de cierre de forma ordenada."""
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if server_instance:
        server_instance.should_exit = True


def main():
    """
    Función principal que construye las dependencias, crea la app
    y la sirve con Uvicorn.
    """
    global server_instance

    setup_logging(service_name=SERVICE_NAME)
    logger = logging.getLogger(__name__)
    logger.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}...")

    db_connector = None

    try:
        # Configurar manejadores de señales
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

        # 1. Cargar la configuración
        web_config = ConfigManager.get_interfaz_web_config()
        sql_config = ConfigManager.get_sql_server_config("SQL_SAM")

        # 2. Validación "Falla Rápido"
        if not all([sql_config.get("servidor"), sql_config.get("base_datos")]):
            raise ValueError("Configuración crítica de la base de datos SAM faltante.")

        logger.info("Validación de configuración completada.")

        # 3. Crear la dependencia DatabaseConnector
        db_connector = DatabaseConnector(
            servidor=sql_config["servidor"],
            base_datos=sql_config["base_datos"],
            usuario=sql_config["usuario"],
            contrasena=sql_config["contrasena"],
        )

        # 4. Configurar la aplicación global inyectando la dependencia
        app = create_app(db_connector=db_connector)

        # 5. Ejecutar Uvicorn
        host = web_config.get("host", "127.0.0.1")
        port = web_config.get("port", 8000)
        reload = web_config.get("debug", False)

        logger.info(f"Configuración del servidor: http://{host}:{port} (Reload: {reload})")

        config = uvicorn.Config(app, host=host, port=port, reload=reload)
        server_instance = uvicorn.Server(config)

        logger.info("Servidor Uvicorn iniciado correctamente.")
        server_instance.run()

    except KeyboardInterrupt:
        logger.info("Interrupción de teclado detectada (Ctrl+C).")
    except Exception as e:
        logger.critical(f"Error crítico no controlado al iniciar el servicio: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Iniciando limpieza final de recursos...")
        if db_connector:
            db_connector.cerrar_conexion_hilo_actual()
        logger.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución y liberado recursos.")


if __name__ == "__main__":
    if not ConfigLoader.is_initialized():
        ConfigLoader.initialize_service(SERVICE_NAME)
    main()
