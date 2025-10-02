import logging
import os
import sys

import uvicorn

# --- Configuración del Path y Carga de Configuración ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.common.utils.config_loader import ConfigLoader

    ConfigLoader.initialize_service("interfaz_web", __file__)

except Exception as e:
    print(f"Error crítico durante la inicialización de la configuración: {e}")
    sys.exit(1)

# --- Importaciones del Proyecto ---
from src.common.database.sql_client import DatabaseConnector
from src.common.utils.config_manager import ConfigManager
from src.common.utils.logging_setup import setup_logging

# Importamos la app y la fábrica desde main
from src.web.main import app, create_app

# --- Constantes ---
SERVICE_NAME = "interfaz_web"


def main():
    """
    Función principal que construye las dependencias, crea la app
    y la sirve con Uvicorn.
    """
    setup_logging(service_name=SERVICE_NAME)
    logger = logging.getLogger(__name__)
    logger.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}")

    try:
        # 1. Cargar la configuración.
        web_config = ConfigManager.get_interfaz_web_config()
        sql_config = ConfigManager.get_sql_server_config("SQL_SAM")

        # 2. Validación "Falla Rápido".
        if not all([sql_config.get("servidor"), sql_config.get("base_datos")]):
            raise ValueError("Configuración crítica de la base de datos SAM faltante.")

        logger.info("Validación de configuración completada.")

        # 3. Crear la dependencia DatabaseConnector.
        db_connector = DatabaseConnector(
            servidor=sql_config["servidor"],
            base_datos=sql_config["base_datos"],
            usuario=sql_config["usuario"],
            contrasena=sql_config["contrasena"],
        )

        # 4. Configurar la aplicación global inyectando la dependencia.
        create_app(db_connector=db_connector)

        # 5. Ejecutar Uvicorn usando el "import string".
        host = web_config.get("host", "127.0.0.1")
        port = web_config.get("port", 8000)
        reload = web_config.get("debug", False)

        logger.info(f"Servidor Uvicorn se iniciará en http://{host}:{port} (Reload: {reload})")
        uvicorn.run("src.web.main:app", host=host, port=port, reload=reload)

    except Exception as e:
        logger.critical(f"Error crítico no controlado al iniciar el servicio: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
