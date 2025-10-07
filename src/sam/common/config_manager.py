# SAM/src/common/config_manager.py
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Esta función auxiliar no pertenece a la clase y se mantiene separada.
def get_ip_local():
    """Obtiene la dirección IP local de la máquina."""
    import socket

    try:
        return socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        return "127.0.0.1"


class ConfigManager:
    """
    Gestor de Configuración Centralizado para el Proyecto SAM.

    Todos los métodos públicos son @classmethod para mantener la consistencia,
    centralizar la lógica y permitir la extensibilidad futura.
    """

    @classmethod
    def _get_env_with_warning(cls, key: str, default: Any = None, warning_msg: str = None) -> Any:
        """
        Método de ayuda interno para obtener una variable de entorno.
        Advierte si la variable no está definida y se esperaba que lo estuviera.
        """
        value = os.getenv(key, default)
        if value is None or (isinstance(value, str) and not value.strip()):
            if warning_msg:
                logger.warning(f"ADVERTENCIA ConfigManager: {warning_msg}", file=sys.stderr)
            # Devuelve el valor por defecto si el valor encontrado es una cadena vacía
            return default
        return value

    # --- CONFIGURACIONES GENERALES ---

    @classmethod
    def get_log_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración de logging de forma unificada."""
        return {
            "directory": cls._get_env_with_warning("LOG_DIRECTORY", "C:/RPA/Logs/SAM"),
            "level_str": cls._get_env_with_warning("LOG_LEVEL", "INFO"),
            "format": cls._get_env_with_warning(
                "LOG_FORMAT", "%(asctime)s - PID:%(process)d - %(name)s - %(levelname)s - %(funcName)s - %(message)s"
            ),
            "datefmt": cls._get_env_with_warning("LOG_DATEFMT", "%Y-%m-%d %H:%M:%S"),
            "backupCount": int(cls._get_env_with_warning("LOG_BACKUP_COUNT", 7)),
            # Nombres de archivo específicos para cada servicio
            "app_log_filename_lanzador": cls._get_env_with_warning("APP_LOG_FILENAME_LANZADOR", "sam_lanzador_app.log"),
            "app_log_filename_balanceador": cls._get_env_with_warning("APP_LOG_FILENAME_BALANCEADOR", "sam_balanceador_app.log"),
            "app_log_filename_callback": cls._get_env_with_warning("APP_LOG_FILENAME_CALLBACK", "sam_callback_server.log"),
            "app_log_filename_interfaz_web": cls._get_env_with_warning("APP_LOG_FILENAME_INTERFAZ_WEB", "sam_interfaz_web.log"),
            # Parámetros fijos de rotación
            "when": "midnight",
            "interval": 1,
            "encoding": "utf-8",
        }

    @classmethod
    def get_email_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración de email para alertas."""
        return {
            "smtp_server": cls._get_env_with_warning("EMAIL_SMTP_SERVER"),
            "smtp_port": int(cls._get_env_with_warning("EMAIL_SMTP_PORT", 587)),
            "from_email": cls._get_env_with_warning("EMAIL_FROM"),
            "recipients": [email.strip() for email in cls._get_env_with_warning("EMAIL_RECIPIENTS", "").split(",")],
            "use_tls": cls._get_env_with_warning("EMAIL_USE_TLS", "True").lower() == "true",
            "smtp_user": cls._get_env_with_warning("EMAIL_USER"),
            "smtp_password": cls._get_env_with_warning("EMAIL_PASSWORD"),
        }

    @classmethod
    def get_sql_server_config(cls, prefix: str) -> Dict[str, Any]:
        """Obtiene la configuración para una conexión a SQL Server usando un prefijo (ej: 'SQL_SAM')."""
        return {
            "servidor": cls._get_env_with_warning(f"{prefix}_HOST"),
            "base_datos": cls._get_env_with_warning(f"{prefix}_DB_NAME"),
            "usuario": cls._get_env_with_warning(f"{prefix}_UID"),
            "contrasena": cls._get_env_with_warning(f"{prefix}_PWD"),
            "driver": cls._get_env_with_warning(f"{prefix}_DRIVER", "{ODBC Driver 17 for SQL Server}"),
            "timeout": int(cls._get_env_with_warning(f"{prefix}_TIMEOUT_CONEXION_INICIAL", 30)),
            "max_retries": int(cls._get_env_with_warning(f"{prefix}_MAX_REINTENTOS_QUERY", 3)),
            "initial_delay": float(cls._get_env_with_warning(f"{prefix}_DELAY_REINTENTO_QUERY_BASE_SEG", 2)),
            "retryable_sqlstates": cls._get_env_with_warning(f"{prefix}_CODIGOS_SQLSTATE_REINTENTABLES", "40001,HYT00,HYT01,08S01").split(","),
        }

    # --- CONFIGURACIONES ESPECÍFICAS POR SERVICIO ---

    @classmethod
    def get_lanzador_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración específica para el servicio Lanzador."""
        pausa_inicio = cls._get_env_with_warning("LANZADOR_PAUSA_INICIO_HHMM", "22:00")
        pausa_fin = cls._get_env_with_warning("LANZADOR_PAUSA_FIN_HHMM", "06:00")
        default_params_str = cls._get_env_with_warning("LANZADOR_PARAMETROS_DEFAULT_JSON", "{}")
        default_params = {}
        try:
            default_params = json.loads(default_params_str)
            if not isinstance(default_params, dict):
                logger.error("LANZADOR_PARAMETROS_DEFAULT_JSON no es un objeto JSON válido. Se usarán parámetros vacíos.")
                default_params = {}
        except json.JSONDecodeError:
            logger.error("Error al decodificar LANZADOR_PARAMETROS_DEFAULT_JSON. Se usarán parámetros vacíos.", exc_info=True)
            default_params = {}
        return {
            "intervalo_lanzamiento": int(cls._get_env_with_warning("LANZADOR_INTERVALO_LANZAMIENTO_SEG", 120)),
            "intervalo_sincronizacion": int(cls._get_env_with_warning("LANZADOR_INTERVALO_SINCRONIZACION_SEG", 3600)),
            "intervalo_conciliacion": int(cls._get_env_with_warning("LANZADOR_INTERVALO_CONCILIACION_SEG", 300)),
            "pausa_lanzamiento": (pausa_inicio, pausa_fin),
            "max_workers_lanzador": int(cls._get_env_with_warning("LANZADOR_MAX_WORKERS", 10)),
            "conciliador_max_intentos_fallidos": int(cls._get_env_with_warning("CONCILIADOR_MAX_INTENTOS_FALLIDOS", 3)),
            "parametros_default": default_params,
        }

    @classmethod
    def get_balanceador_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración específica para el servicio Balanceador."""
        return {
            "cooling_period_seg": int(cls._get_env_with_warning("BALANCEADOR_COOLING_PERIOD_SEG", 300)),
            "intervalo_ciclo_seg": int(cls._get_env_with_warning("BALANCEADOR_INTERVALO_CICLO_SEG", 120)),
            "aislamiento_estricto_pool": cls._get_env_with_warning("BALANCEADOR_POOL_AISLAMIENTO_ESTRICTO", "True").lower() == "true",
            "proveedores_carga": [p.strip() for p in cls._get_env_with_warning("BALANCEADOR_PROVEEDORES_CARGA", "clouders,rpa360").split(",")],
        }

    @classmethod
    def get_callback_server_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración para el servidor de Callbacks."""
        return {
            "host": cls._get_env_with_warning("CALLBACK_SERVER_HOST", "0.0.0.0"),
            "port": int(cls._get_env_with_warning("CALLBACK_SERVER_PORT", 8008)),
            "threads": int(cls._get_env_with_warning("CALLBACK_SERVER_THREADS", 8)),
            "token": cls._get_env_with_warning("CALLBACK_TOKEN"),
            "auth_mode": cls._get_env_with_warning("CALLBACK_AUTH_MODE", "strict").lower(),
            "public_host": cls._get_env_with_warning("CALLBACK_SERVER_PUBLIC_HOST", os.getenv("CALLBACK_SERVER_HOST", "localhost")),
            "endpoint_path": cls._get_env_with_warning("CALLBACK_ENDPOINT_PATH", "/api/callback").strip("/"),
        }

    @classmethod
    def get_interfaz_web_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración para la Interfaz Web."""
        return {
            "host": cls._get_env_with_warning("INTERFAZ_WEB_HOST", "0.0.0.0"),
            "port": int(cls._get_env_with_warning("INTERFAZ_WEB_PORT", 8000)),
            "debug": cls._get_env_with_warning("INTERFAZ_WEB_DEBUG", "False").lower() == "true",
            "session_timeout_min": int(cls._get_env_with_warning("INTERFAZ_WEB_SESSION_TIMEOUT_MIN", 30)),
            "max_upload_size_mb": int(cls._get_env_with_warning("INTERFAZ_WEB_MAX_UPLOAD_SIZE_MB", 16)),
        }

    # --- CONFIGURACIONES DE CLIENTES EXTERNOS ---
    @classmethod
    def get_mapa_robots(cls) -> Dict[str, str]:
        """
        Obtiene el mapeo de nombres de robots desde la variable de entorno MAPA_ROBOTS.
        La variable debe contener un string JSON válido.
        """
        mapa_str = cls._get_env_with_warning("MAPA_ROBOTS", "{}")
        try:
            mapa = json.loads(mapa_str)
            if not isinstance(mapa, dict):
                logger.warning("MAPA_ROBOTS no es un diccionario JSON válido. Se usará un mapa vacío.")
                return {}
            return mapa
        except json.JSONDecodeError:
            logger.error("Error al decodificar MAPA_ROBOTS. Asegúrese de que es un JSON válido. Se usará un mapa vacío.", exc_info=True)
            return {}

    @classmethod
    def get_clouders_api_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración para la API de Clouders."""
        return {
            "clouders_api_url": cls._get_env_with_warning("CLOUDERS_API_URL"),
            "clouders_auth": cls._get_env_with_warning("CLOUDERS_AUTH"),
            "clouders_api_timeout": int(cls._get_env_with_warning("CLOUDERS_API_TIMEOUT", 30)),
            "clouders_verify_ssl": cls._get_env_with_warning("CLOUDERS_VERIFY_SSL", "False").lower() == "true",
        }

    @classmethod
    def get_aa_config(cls) -> Dict[str, Any]:
        return {
            "url_cr": cls._get_env_with_warning("AA_CR_URL"),
            "usuario": cls._get_env_with_warning("AA_CR_USER"),
            "pwd": cls._get_env_with_warning("AA_CR_PWD"),  # Optional
            "api_key": cls._get_env_with_warning("AA_CR_API_KEY"),
            "verify_ssl": cls._get_env_with_warning("AA_VERIFY_SSL", "false").lower() == "false",
            "api_timeout_seconds": int(cls._get_env_with_warning("AA_API_TIMEOUT_SECONDS", 60)),
            "callback_url_deploy": cls._get_env_with_warning("AA_URL_CALLBACK"),
        }

    @classmethod
    def get_apigw_config(cls) -> Dict[str, Any]:
        """Obtiene la configuración para el API Gateway."""
        return {
            "url": cls._get_env_with_warning("API_GATEWAY_URL"),
            "client_id": cls._get_env_with_warning("API_GATEWAY_CLIENT_ID"),
            "client_secret": cls._get_env_with_warning("API_GATEWAY_CLIENT_SECRET"),
            "grant_type": cls._get_env_with_warning("API_GATEWAY_GRANT_TYPE", "client_credentials"),
            "scope": cls._get_env_with_warning("API_GATEWAY_SCOPE", "scope1"),
            "timeout_seconds": int(cls._get_env_with_warning("API_GATEWAY_TIMEOUT_SECONDS", 30)),
            "token_expiration_buffer_sec": int(cls._get_env_with_warning("API_GATEWAY_TOKEN_EXPIRATION_BUFFER_SEC", 300)),
        }

    # --- UTILIDADES ---

    @classmethod
    def check_and_display_config(cls, service_name: Optional[str] = None):
        """Muestra la configuración cargada y valida la presencia de variables críticas."""
        logger.info("=" * 60, file=sys.stderr)
        logger.info(" VERIFICACIÓN DE CONFIGURACIÓN ".center(60, "="), file=sys.stderr)
        logger.info(f"Servicio: {service_name or 'No especificado'}", file=sys.stderr)
        logger.info(f"IP Local: {get_ip_local()}", file=sys.stderr)
        logger.info("=" * 60, file=sys.stderr)

        # Mapeo de configuraciones a verificar
        configs_a_verificar = {
            "SQL SAM": (["SQL_SAM_HOST", "SQL_SAM_DB_NAME", "SQL_SAM_UID", "SQL_SAM_PWD"], True),
            "SQL RPA360": (["SQL_RPA360_HOST", "SQL_RPA360_DB_NAME", "SQL_RPA360_UID", "SQL_RPA360_PWD"], True),
            "EMAIL": (["EMAIL_SMTP_SERVER", "EMAIL_FROM_EMAIL", "EMAIL_RECIPIENTS"], False),
            "Clouders API": (["CLOUDERS_API_URL", "CLOUDERS_AUTH"], False),
            "Callback": (["CALLBACK_TOKEN"], False),
            "API Gateway": (["API_GATEWAY_URL", "API_GATEWAY_CLIENT_ID", "API_GATEWAY_CLIENT_SECRET"], False),
        }

        for config_name, (keys, is_critical) in configs_a_verificar.items():
            faltantes = [key for key in keys if not os.getenv(key)]
            if faltantes:
                estado = "FALTAN VARIABLES CRÍTICAS" if is_critical else "OK (con opcionales faltantes)"
                logger.warning(f"\n[ {config_name} ]", file=sys.stderr)
                logger.warning(f"  - Estado: {estado}", file=sys.stderr)
                logger.warning(f"  - Faltantes: {', '.join(faltantes)}", file=sys.stderr)

        # Mapeo de métodos de configuración específica del servicio
        config_method_map = {
            "lanzador": cls.get_lanzador_config,
            "balanceador": cls.get_balanceador_config,
            "callback": cls.get_callback_server_config,
            "interfaz_web": cls.get_interfaz_web_config,
        }

        if service_name and service_name in config_method_map:
            logger.info(f"\nConfiguración específica de '{service_name}':", file=sys.stderr)
            try:
                config_method = config_method_map[service_name]
                config = config_method()
                for key, value in config.items():
                    # Ocultar contraseñas y datos sensibles
                    if any(sensitive in key.lower() for sensitive in ["pass", "pwd", "secret", "token", "auth"]):
                        display_value = ("*" * 8) if value else "No configurado"
                    else:
                        display_value = value
                    logger.warning(f"  - {key}: {display_value}", file=sys.stderr)

            except Exception as e:
                logger.warning(f"  Error al obtener configuración específica: {e}", file=sys.stderr)

        logger.info("=" * 60, file=sys.stderr)
        logger.info("=" * 60, file=sys.stderr)
