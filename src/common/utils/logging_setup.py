# SAM/src/common/utils/logging_setup.py
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Dict

# Importar ConfigManager para obtener la configuración
from src.common.utils.config_manager import ConfigManager

# Variable para asegurar que la configuración se aplique solo una vez
_is_configured = False


class RelativePathFormatter(logging.Formatter):
    """
    Un formateador de logs que acorta el path del módulo para mayor legibilidad.
    Transforma 'src.balanceador.service.main' en 'service.main'.
    """

    def __init__(self, *args, service_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
        self.common_prefix = "src.common."
        self.service_prefix = f"src.{service_name}."

    def format(self, record):
        # Hacemos una copia para no modificar el registro original
        original_name = record.name

        if original_name.startswith(self.service_prefix):
            record.name = original_name[len(self.service_prefix) :]
        elif original_name.startswith(self.common_prefix):
            record.name = original_name[len(self.common_prefix) :]

        # Llamamos al formateador original con el nombre modificado
        result = super().format(record)

        # Restauramos el nombre original por si el registro se usa en otro lugar
        record.name = original_name
        return result


class RobustTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Una versión más robusta de TimedRotatingFileHandler que maneja errores de permisos
    en entornos Windows, reintentando la rotación del archivo de log.
    """

    def doRollover(self):
        """Sobrescribe el método doRollover para manejar errores de permisos."""
        try:
            super().doRollover()
        except (OSError, PermissionError) as e:
            # En Windows, si el archivo está en uso, puede lanzar PermissionError.
            # Se registra el error en stderr y se continúa sin rotar.
            sys.stderr.write(f"LOGGING_SETUP: No se pudo rotar el archivo de log. Error: {e}\n")
        except Exception as e:
            sys.stderr.write(f"LOGGING_SETUP: Error inesperado al rotar el archivo de log: {e}\n")


def setup_logging(service_name: str):
    """
    Configura el logger raíz para un servicio específico.
    """
    global _is_configured
    if _is_configured:
        return

    log_config = ConfigManager.get_log_config()
    log_filename = log_config.get(f"app_log_filename_{service_name}", f"sam_{service_name}_app.log")
    log_directory = Path(log_config.get("directory", "C:/RPA/Logs/SAM"))
    log_file_path = log_directory / log_filename
    log_directory.mkdir(parents=True, exist_ok=True)

    # CORREGIDO: Usamos nuestro nuevo formateador personalizado
    log_formatter = RelativePathFormatter(
        fmt=log_config.get("format"),
        datefmt=log_config.get("datefmt"),
        service_name=service_name,  # Le pasamos el nombre del servicio
    )

    file_handler = RobustTimedRotatingFileHandler(
        filename=log_file_path,
        when=log_config.get("when", "midnight"),
        interval=log_config.get("interval", 1),
        backupCount=log_config.get("backupCount", 7),
        encoding=log_config.get("encoding", "utf-8"),
    )
    file_handler.setFormatter(log_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_config.get("level_str", "INFO").upper())

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _is_configured = True
    # Usamos print para este mensaje inicial, ya que el logger acaba de ser configurado.
    print(f"Logging configurado para el servicio '{service_name}'. Los logs se guardarán en: {log_file_path}")
