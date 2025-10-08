# SAM/src/balanceador/clients/mysql_client.py

import csv
import io
import logging
import socket
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import warnings

import paramiko

# --- Configuración de Path ---
CLIENTS_DIR = Path(__file__).resolve().parent
BALANCEADOR_MODULE_ROOT = CLIENTS_DIR.parent
SAM_PROJECT_ROOT = BALANCEADOR_MODULE_ROOT.parent

if str(SAM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(SAM_PROJECT_ROOT))
# --- Fin Configuración de Path ---

# Configurar el nivel de log para Paramiko para reducir el ruido
logging.getLogger("paramiko").setLevel(logging.WARNING)


@dataclass
class ConnectionConfig:
    """Configuración de conexión SSH y MySQL."""

    # SSH Config
    host_ssh: str
    puerto_ssh: int = 22
    usuario_ssh: str = ""
    password_ssh: str = ""

    # MySQL Config
    db_host_mysql: str = "127.0.0.1"
    db_port_mysql: int = 3306
    usuario_mysql: str = ""
    password_mysql: str = ""

    # Retry Config
    max_reintentos_ssh: int = 3
    delay_reintento_ssh_seg: int = 5
    max_reintentos_mysql: int = 2
    delay_reintento_mysql_query_seg: int = 3

    # Timeout Config
    ssh_timeout: int = 20
    ssh_banner_timeout: int = 30
    ssh_auth_timeout: int = 30
    mysql_command_timeout: int = 30


class ConnectionPool:
    """Pool simple de conexiones SSH para reutilización."""

    def __init__(self, max_connections: int = 3):
        self._connections: Dict[str, paramiko.SSHClient] = {}
        self._lock = threading.Lock()
        self._max_connections = max_connections
        self._connection_count = 0

    def obtener_conexion(self, host_key: str) -> Optional[paramiko.SSHClient]:
        with self._lock:
            return self._connections.get(host_key)

    def agregar_conexion(self, host_key: str, client: paramiko.SSHClient) -> bool:
        with self._lock:
            if self._connection_count >= self._max_connections:
                return False
            self._connections[host_key] = client
            self._connection_count += 1
            return True

    def eliminar_conexion(self, host_key: str):
        with self._lock:
            if host_key in self._connections:
                try:
                    self._connections[host_key].close()
                except Exception as e:
                    self.logger.debug(f"Error durante eliminar conexión: {e}")
                del self._connections[host_key]
                self._connection_count -= 1

    def limpiar_todo(self):
        with self._lock:
            for client in self._connections.values():
                try:
                    client.close()
                except Exception as e:
                    self.logger.debug(f"Error durante limpiar todo: {e}")
            self._connections.clear()
            self._connection_count = 0


def reintentar_si_falla(max_retries: int = 3, delay: float = 1.0, backoff_multiplier: float = 2.0):
    """Decorador para reintentos con backoff exponencial."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = delay * (backoff_multiplier**attempt)
                        time.sleep(sleep_time)
                    else:
                        break
            raise last_exception

        return wrapper

    return decorator


class MySQLSSHClient:
    """
    @deprecated: Esta clase será reemplazada por CloudersClient
    """

    # Pool compartido entre instancias
    _connection_pool = ConnectionPool()

    def __init__(self, config_ssh_mysql: Dict[str, Any], mapa_robots: Dict[str, str], logger_instance: Optional[logging.Logger] = None):
        # Configurar logger
        self.logger = logger_instance or logging.getLogger(f"SAM.{BALANCEADOR_MODULE_ROOT.name}.clients.{Path(__file__).stem}")

        # Crear configuración estructurada
        self.config = self._cargar_configuracion(config_ssh_mysql)
        self.mapa_robots = mapa_robots or {}

        # Clave única para el pool de conexiones
        self.host_key = f"{self.config.host_ssh}:{self.config.puerto_ssh}:{self.config.usuario_ssh}"

        # Lock para operaciones thread-safe
        self._lock = threading.Lock()

        self.logger.debug(f"MySQLSSHClient inicializado para: {self.config.host_ssh}")

        # Validar configuración
        self._validar_config()

    def _cargar_configuracion(self, config_dict: Dict[str, Any]) -> ConnectionConfig:
        """Construye la configuración desde el diccionario."""
        return ConnectionConfig(
            host_ssh=config_dict.get("host_ssh", ""),
            puerto_ssh=int(config_dict.get("puerto_ssh", 22)),
            usuario_ssh=config_dict.get("usuario_ssh", ""),
            password_ssh=config_dict.get("pass_ssh", ""),
            db_host_mysql=config_dict.get("db_host_mysql", "127.0.0.1"),
            db_port_mysql=int(config_dict.get("db_port_mysql", 3306)),
            usuario_mysql=config_dict.get("usuario_mysql", ""),
            password_mysql=config_dict.get("pass_mysql", ""),
            max_reintentos_ssh=int(config_dict.get("max_reintentos_ssh_connect", 3)),
            delay_reintento_ssh_seg=int(config_dict.get("delay_reintento_ssh_seg", 5)),
            max_reintentos_mysql=int(config_dict.get("max_reintentos_mysql_query", 2)),
            delay_reintento_mysql_query_seg=int(config_dict.get("delay_reintento_mysql_query_seg", 3)),
            ssh_timeout=int(config_dict.get("ssh_timeout", 20)),
            ssh_banner_timeout=int(config_dict.get("ssh_banner_timeout", 30)),
            ssh_auth_timeout=int(config_dict.get("ssh_auth_timeout", 30)),
            mysql_command_timeout=int(config_dict.get("mysql_command_timeout", 30)),
        )

    def _validar_config(self):
        """Valida la configuración esencial."""
        required_fields: Dict[str, str] = {
            "host_ssh": self.config.host_ssh,
            "usuario_ssh": self.config.usuario_ssh,
            "password_ssh": self.config.password_ssh,
        }

        missing: List[str] = [field for field, value in required_fields.items() if not value]
        if missing:
            error_msg = f"Configuración SSH incompleta. Faltan: {missing}"
            self.logger.critical(error_msg)
            raise ValueError(error_msg)

    @contextmanager
    def _obtener_conexion_ssh(self):
        """Context manager para obtener/liberar conexiones SSH."""
        client = None
        try:
            client = self._obtener_cliente_ssh()
            yield client
        finally:
            # No cerramos la conexión aquí ya que se reutiliza
            pass

    def _obtener_cliente_ssh(self) -> paramiko.SSHClient:
        """Obtiene un cliente SSH, reutilizando conexión existente si es válida."""
        with self._lock:
            # Intentar obtener conexión existente del pool
            client = self._connection_pool.obtener_conexion(self.host_key)

            if client and self._conexion_activa(client):
                self.logger.debug(f"Reutilizando conexión SSH existente a {self.config.host_ssh}")
                return client

            # Crear nueva conexión
            self.logger.info(f"Creando nueva conexión SSH a {self.config.host_ssh}")
            client = self._crear_nueva_conexion_ssh()

            # Agregar al pool si es posible
            if not self._connection_pool.agregar_conexion(self.host_key, client):
                self.logger.warning("Pool de conexiones lleno, usando conexión temporal")

            return client

    def _conexion_activa(self, client: paramiko.SSHClient) -> bool:
        """Verifica si una conexión SSH está activa."""
        try:
            if not client:
                return False

            transport = client.get_transport()
            if not transport or not transport.is_active():
                return False

            # Test rápido con comando echo
            stdin, stdout, stderr = client.exec_command('echo "test"', timeout=5)
            result: str = stdout.read().decode().strip()
            return result == "test"

        except Exception as e:
            self.logger.debug(f"Conexión SSH no válida: {e}")
            return False

    @reintentar_si_falla(max_retries=3, delay=2.0)
    def _crear_nueva_conexion_ssh(self) -> paramiko.SSHClient:
        """Crea una nueva conexión SSH."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.config.host_ssh,
                port=self.config.puerto_ssh,
                username=self.config.usuario_ssh,
                password=self.config.password_ssh,
                timeout=self.config.ssh_timeout,
                banner_timeout=self.config.ssh_banner_timeout,
                auth_timeout=self.config.ssh_auth_timeout,
            )
            self.logger.info(f"Conexión SSH establecida con éxito a {self.config.host_ssh}")
            return client

        except paramiko.AuthenticationException as e:
            self.logger.error(f"Error de autenticación SSH a {self.config.host_ssh}: {e}")
            raise
        except (OSError, paramiko.SSHException, socket.timeout, EOFError) as e:
            self.logger.error(f"Error de conexión SSH a {self.config.host_ssh}: {e}")
            raise

    def ejecutar_consulta_mysql(self, base_datos: str, consulta: str) -> List[Dict[str, Any]]:
        """Ejecuta una consulta MySQL a través del túnel SSH."""
        if not base_datos or not consulta:
            raise ValueError("Base de datos y consulta son requeridos")

        # Sanitizar consulta para el comando shell
        consulta_escapada = consulta.replace('"', r"\"").replace("`", r"\`")

        # Construir comando MySQL
        comando = self._crear_comando_mysql(base_datos, consulta_escapada)

        return self._ejecutar_mysql_con_reintentos(comando, consulta)

    def _crear_comando_mysql(self, base_datos: str, consulta_escapada: str) -> str:
        """Construye el comando MySQL."""
        # Preferir .my.cnf si está disponible, sino usar credenciales explícitas
        if self.config.usuario_mysql and self.config.password_mysql:
            return (
                f"mysql -h {self.config.db_host_mysql} "
                f"-P {self.config.db_port_mysql} "
                f"-u {self.config.usuario_mysql} "
                f"-p'{self.config.password_mysql}' "
                f'-D {base_datos} -B -e "{consulta_escapada}"'
            )
        else:
            return (
                f"mysql --defaults-file=~/.my.cnf "
                f"-h {self.config.db_host_mysql} "
                f"-P {self.config.db_port_mysql} "
                f'-D {base_datos} -B -e "{consulta_escapada}"'
            )

    def _ejecutar_mysql_con_reintentos(self, comando: str, consulta_original: str) -> List[Dict[str, Any]]:
        """Ejecuta comando MySQL con lógica de reintentos."""
        for intento in range(1, self.config.max_reintentos_mysql + 1):
            try:
                with self._obtener_conexion_ssh() as ssh_client:
                    self.logger.debug(f"Ejecutando MySQL (intento {intento}): {consulta_original[:100]}...")

                    stdin, stdout, stderr = ssh_client.exec_command(comando, timeout=self.config.mysql_command_timeout)

                    # Leer resultados
                    salida_bytes = stdout.read()
                    error_bytes = stderr.read()
                    exit_status = stdout.channel.recv_exit_status()

                    salida_str = salida_bytes.decode("utf-8", errors="replace")
                    error_str = error_bytes.decode("utf-8", errors="replace")

                    if exit_status != 0:
                        if self._error_mysql_reintentable(error_str) and intento < self.config.max_reintentos_mysql:
                            self.logger.warning(f"Error MySQL reintentable (intento {intento}): {error_str.strip()}")
                            self._manejar_error_de_conexion()
                            time.sleep(self.config.delay_reintento_mysql_query_seg * intento)
                            continue
                        else:
                            raise Exception(f"Error MySQL (status {exit_status}): {error_str.strip()}")

                    self.logger.info(f"Consulta MySQL ejecutada exitosamente (intento {intento})")
                    return self._parsear_salida_mysql(salida_str)

            except (OSError, paramiko.SSHException, socket.timeout, EOFError) as e:
                self.logger.warning(f"Error SSH durante consulta MySQL (intento {intento}): {e}")
                self._manejar_error_de_conexion()
                if intento >= self.config.max_reintentos_mysql:
                    raise
                time.sleep(self.config.delay_reintento_mysql_query_seg * intento)

        raise Exception(f"No se pudo ejecutar consulta MySQL después de {self.config.max_reintentos_mysql} intentos")

    def _error_mysql_reintentable(self, error_str: str) -> bool:
        """Determina si un error MySQL es reintentable."""
        retryable_errors = [
            "2006",
            "2013",  # Códigos de error MySQL
            "gone away",
            "lost connection",
            "broken pipe",
            "connection reset",
            "timeout",
        ]
        error_lower = error_str.lower()
        return any(error in error_lower for error in retryable_errors)

    def _manejar_error_de_conexion(self):
        """Maneja errores de conexión removiendo del pool."""
        self._connection_pool.eliminar_conexion(self.host_key)

    def _parsear_salida_mysql(self, salida_tsv: str) -> List[Dict[str, Any]]:
        """Parsea la salida TSV de MySQL de forma optimizada."""
        if not salida_tsv.strip():
            return []

        try:
            resultados = []
            reader = csv.DictReader(io.StringIO(salida_tsv), delimiter="\t")

            for fila in reader:
                # Limpiar espacios y aplicar mapeo de robots
                fila_procesada = self._procesar_fila(fila)
                resultados.append(fila_procesada)

            self.logger.debug(f"Procesadas {len(resultados)} filas del resultado MySQL")
            return resultados

        except csv.Error as e:
            self.logger.error(f"Error parseando CSV/TSV: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error inesperado parseando salida MySQL: {e}")
            return []

    def _procesar_fila(self, fila: Dict[str, str]) -> Dict[str, Any]:
        """Procesa una fila individual aplicando limpieza y transformaciones."""
        # Limpiar espacios
        fila_limpia = {k.strip() if k else k: v.strip() if isinstance(v, str) else v for k, v in fila.items()}

        # Aplicar mapeo de robots
        if "robot_name" in fila_limpia and self.mapa_robots:
            robot_clouders = fila_limpia["robot_name"]
            robot_sam = self.mapa_robots.get(robot_clouders)
            if robot_sam:
                fila_limpia["robot_name_sam"] = robot_sam
                self.logger.debug(f"Robot '{robot_clouders}' mapeado a '{robot_sam}'")

        # Conversión de tipos
        self._convertir_campos_numericos(fila_limpia)

        return fila_limpia

    def _convertir_campos_numericos(self, fila: Dict[str, Any]):
        """Convierte campos numéricos conocidos."""
        numeric_fields = ["CantidadTickets", "id", "count"]

        for field in numeric_fields:
            if field in fila:
                try:
                    fila[field] = int(fila[field])
                except (ValueError, TypeError):
                    self.logger.warning(f"Valor no numérico para '{field}': '{fila[field]}'")
                    fila[field] = 0

    def test_connection(self) -> bool:
        """Prueba la conexión SSH y MySQL."""
        try:
            with self._obtener_conexion_ssh() as ssh_client:
                # Test SSH
                stdin, stdout, stderr = ssh_client.exec_command('echo "SSH OK"', timeout=10)
                if stdout.read().decode().strip() != "SSH OK":
                    return False

                # Test MySQL
                test_command = f"mysql --defaults-file=~/.my.cnf -h {self.config.db_host_mysql} -P {self.config.db_port_mysql} -e 'SELECT 1;'"
                stdin, stdout, stderr = ssh_client.exec_command(test_command, timeout=10)
                return stdout.channel.recv_exit_status() == 0

        except Exception as e:
            self.logger.error(f"Test de conexión falló: {e}")
            return False

    def cerrar_conexion(self):
        """Cierra la conexión específica de esta instancia."""
        self._connection_pool.eliminar_conexion(self.host_key)

    @classmethod
    def cerrar_todas_las_conecciones(cls):
        """Cierra todas las conexiones del pool (método de clase)."""
        cls._connection_pool.limpiar_todo()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # No cerrar automáticamente para permitir reutilización
        pass

    def __del__(self):
        """Cleanup al destruir la instancia."""
        try:
            self.cerrar_conexion()
        except Exception as e:
            self.logger.debug(f"Error durante limpieza de conexión: {e}")
