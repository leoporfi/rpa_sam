# sam/callback/run_callback.py
import logging
import sys

import uvicorn

from sam.callback.service.main import create_app

# --- Importaciones del Proyecto ---
from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging

# --- Constantes ---
SERVICE_NAME = "callback"


def main():
    """
    Función principal que construye las dependencias, crea la app FastAPI
    y la ejecuta con Uvicorn.
    """
    setup_logging(service_name=SERVICE_NAME)
    logger = logging.getLogger(__name__)

    logger.info(f"Iniciando el servicio FastAPI: {SERVICE_NAME.capitalize()}")

    try:
        # 1. Cargar la configuración necesaria.
        server_config = ConfigManager.get_callback_server_config()
        sql_config = ConfigManager.get_sql_server_config("SQL_SAM")

        # 2. Validación "Falla Rápido" (Fail-Fast).
        if not all([sql_config.get("servidor"), sql_config.get("base_datos")]):
            raise ValueError("Configuración crítica de la base de datos SAM faltante.")

        logger.info("Validación de configuración completada.")

        # 3. Crear las dependencias una sola vez (Inyección de Dependencias).
        logger.info("Creando instancia del conector de base de datos...")
        db_connector = DatabaseConnector(
            servidor=sql_config["servidor"],
            base_datos=sql_config["base_datos"],
            usuario=sql_config["usuario"],
            contrasena=sql_config["contrasena"],
        )

        # 4. Crear la aplicación FastAPI, inyectando la dependencia.
        app = create_app(db_connector=db_connector)

        # 5. Configurar y ejecutar Uvicorn.
        host = server_config.get("host", "0.0.0.0")
        port = server_config.get("port", 8008)
        workers = server_config.get("threads", 1)

        logger.info(f"Iniciando Uvicorn en http://{host}:{port} con {workers} worker(s)...")
        uvicorn.run(
            app, #"sam.callback.service.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level=logging.getLogger().getEffectiveLevel(),
        )

    except Exception as e:
        logger.critical(f"Error crítico no controlado al iniciar el servicio {SERVICE_NAME}: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    if not ConfigLoader.is_initialized():
        ConfigLoader.initialize_service(SERVICE_NAME)
    main()
