# sam/src/common/logging_setup.py
import logging
import logging.handlers
import os
from pathlib import Path

from .config_loader import ConfigLoader
from .config_manager import ConfigManager


class RelativePathFormatter(logging.Formatter):
    """
    Un formateador de logs que convierte las rutas absolutas de los archivos
    en rutas relativas a la raíz del proyecto, haciendo los logs más limpios.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_root = str(ConfigLoader.get_project_root())

    def format(self, record):
        if hasattr(record, "pathname") and record.pathname.startswith(self.project_root):
            record.pathname = os.path.relpath(record.pathname, self.project_root)
        return super().format(record)


def setup_logging(service_name: str):
    """
    Configura el sistema de logging para un servicio específico.
    Utiliza TimedRotatingFileHandler para rotar los logs diariamente.
    """
    log_config = ConfigManager.get_log_config()
    log_directory = Path(log_config["directory"])
    log_directory.mkdir(parents=True, exist_ok=True)

    # Determinar el nombre del archivo de log para el servicio actual
    log_filename_key = f"app_log_filename_{service_name}"
    log_filename = log_config.get(log_filename_key, f"sam_{service_name}_app.log")
    log_file_path = log_directory / log_filename

    # Configurar el nivel de logging
    log_level_str = log_config.get("level_str", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Crear el formateador con la ruta relativa
    formatter = RelativePathFormatter(log_config["format"], datefmt=log_config["datefmt"])

    # Configurar el handler de rotación de archivos
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file_path,
        when=log_config["when"],
        interval=log_config["interval"],
        backupCount=log_config["backupCount"],
        encoding=log_config["encoding"],
    )
    file_handler.setFormatter(formatter)

    # Configurar el handler de la consola (para ver los logs en la terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configurar el logger raíz para que envíe los logs a ambos handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [file_handler, console_handler]

    # RFR-33: Se añade esta línea para silenciar los logs de INFO de httpx.
    # Esto limpia la consola de mensajes de peticiones HTTP exitosas,
    # pero seguirá mostrando WARNINGS y ERRORS de la librería.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info(f"Logging configurado para el servicio '{service_name}'. Los logs se guardarán en: {log_file_path}")
