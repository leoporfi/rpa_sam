# SAM/src/common/utils/config_loader.py
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigLoader:
    """
    Cargador de configuración estandarizado para todos los servicios SAM.

    Jerarquía de configuración:
    1. .env específico del servicio (src/{servicio}/.env)
    2. .env general del proyecto (SAM_PROJECT_ROOT/.env)
    3. Variables de entorno del sistema
    """

    _initialized = False
    _project_root: Optional[Path] = None
    _src_root: Optional[Path] = None

    @classmethod
    def initialize_service(cls, service_name: str, run_script_path: Optional[str] = None) -> None:
        """
        Inicializa la configuración para un servicio específico.

        Args:
            service_name: Nombre del servicio (ej: 'lanzador', 'balanceador', 'callback', 'interfaz_web')
            run_script_path: Ruta del script run_*.py (opcional, se detecta automáticamente)
        """
        # --- NUEVA COMPROBACIÓN ---
        # Si la variable de entorno está presente, significa que el proceso padre
        # ya realizó esta inicialización. Los procesos hijos (workers) heredarán
        # esta variable y no repetirán el proceso.
        if os.getenv("SAM_CONFIG_INITIALIZED") == "True":
            cls._initialized = True  # Aseguramos que el estado interno sea consistente
            return

        if cls._initialized:
            return

        # Determinar rutas del proyecto
        if run_script_path:
            script_path = Path(run_script_path).resolve()
        else:
            # Detectar automáticamente desde el stack de llamadas
            import inspect

            frame = inspect.currentframe()
            try:
                # Buscar el frame que contiene 'run_' en el nombre del archivo
                while frame:
                    filename = frame.f_code.co_filename
                    if "run_" in Path(filename).name:
                        script_path = Path(filename).resolve()
                        break
                    frame = frame.f_back
                else:
                    # Fallback: usar el frame del caller
                    caller_frame = inspect.currentframe().f_back
                    script_path = Path(caller_frame.f_code.co_filename).resolve()
            finally:
                del frame

        # Establecer rutas del proyecto
        cls._src_root = script_path.parent  # src/{servicio}/
        cls._project_root = cls._src_root.parent.parent  # SAM_PROJECT_ROOT/

        # Configurar sys.path
        cls._setup_python_path()

        # Cargar variables de entorno
        cls._load_environment_variables(service_name)

        cls._initialized = True

        # Marcar en el entorno que la inicialización se completó
        os.environ["SAM_CONFIG_INITIALIZED"] = "True"

        # Log de inicialización
        print(f"CONFIG_LOADER: Servicio '{service_name}' inicializado", file=sys.stderr)
        print(f"CONFIG_LOADER: Proyecto root: {cls._project_root}", file=sys.stderr)
        print(f"CONFIG_LOADER: Src root: {cls._src_root}", file=sys.stderr)

    @classmethod
    def _setup_python_path(cls) -> None:
        """Configura el sys.path para importaciones correctas."""
        paths_to_add = [
            str(cls._src_root),  # Para importar módulos del servicio
            str(cls._project_root / "src"),  # Para importar common y otros servicios
        ]

        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)

    @classmethod
    def _load_environment_variables(cls, service_name: str) -> None:
        """
        Carga variables de entorno con jerarquía definida.

        Orden de precedencia (mayor a menor):
        1. Variables ya existentes en el entorno
        2. .env específico del servicio
        3. .env general del proyecto
        """
        # 1. .env específico del servicio
        service_env_path = cls._src_root / ".env"
        service_env_loaded = False

        if service_env_path.exists():
            print(f"CONFIG_LOADER: Cargando .env específico desde {service_env_path}", file=sys.stderr)
            load_dotenv(dotenv_path=service_env_path, override=False)  # No sobreescribir variables existentes
            service_env_loaded = True

        # 2. .env general del proyecto
        project_env_path = cls._project_root / ".env"
        project_env_loaded = False

        if project_env_path.exists():
            print(f"CONFIG_LOADER: Cargando .env general desde {project_env_path}", file=sys.stderr)
            load_dotenv(dotenv_path=project_env_path, override=False)  # No sobreescribir variables existentes
            project_env_loaded = True

        # 3. Fallback a load_dotenv() sin argumentos (busca en directorios padre)
        if not service_env_loaded and not project_env_loaded:
            print("CONFIG_LOADER: No se encontraron archivos .env específicos, usando búsqueda automática", file=sys.stderr)
            load_dotenv()

        # Validar configuración crítica si es necesario
        cls._validate_critical_config(service_name)

    @classmethod
    def _validate_critical_config(cls, service_name: str) -> None:
        """Valida que las configuraciones críticas estén presentes."""
        critical_vars = {
            "lanzador": ["AA_CR_URL", "AA_CR_USER", "AA_CR_PWD","SQL_SAM_HOST", "SQL_SAM_DB_NAME"],
            "balanceador": ["SQL_SAM_HOST", "SQL_RPA360_HOST", "CLOUDERS_SSH_HOST"],
            "callback": ["CALLBACK_SERVER_HOST", "CALLBACK_SERVER_PORT"],
            "interfaz_web": ["SQL_SAM_HOST", "SQL_SAM_DB_NAME"],
        }

        if service_name in critical_vars:
            missing_vars = []
            for var in critical_vars[service_name]:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                print(f"ADVERTENCIA CONFIG_LOADER: Variables críticas faltantes para {service_name}: {missing_vars}", file=sys.stderr)

    @classmethod
    def get_project_root(cls) -> Path:
        """Retorna la ruta raíz del proyecto."""
        if not cls._initialized:
            raise RuntimeError("ConfigLoader no ha sido inicializado. Llama a initialize_service() primero.")
        return cls._project_root

    @classmethod
    def get_src_root(cls) -> Path:
        """Retorna la ruta del directorio src."""
        if not cls._initialized:
            raise RuntimeError("ConfigLoader no ha sido inicializado. Llama a initialize_service() primero.")
        return cls._src_root

    @classmethod
    def is_initialized(cls) -> bool:
        """Retorna True si el ConfigLoader ya fue inicializado."""
        return cls._initialized

    @classmethod
    def reset(cls) -> None:
        """Resetea el estado del ConfigLoader (útil para testing)."""
        cls._initialized = False
        cls._project_root = None
        cls._src_root = None


# Función de conveniencia para inicialización automática
def auto_initialize_config() -> None:
    """
    Inicializa automáticamente la configuración detectando el servicio desde el stack de llamadas.
    """
    if ConfigLoader.is_initialized():
        return

    import inspect

    # Detectar el servicio desde el stack de llamadas
    frame = inspect.currentframe()
    service_name = None

    try:
        while frame:
            filename = frame.f_code.co_filename
            path = Path(filename)

            # Buscar patrones de servicio
            if "run_" in path.name:
                # Extraer nombre del servicio del archivo run_*.py
                service_name = path.name.replace("run_", "").replace(".py", "")
                break
            elif path.parent.name in ["lanzador", "balanceador", "callback", "interfaz_web"]:
                service_name = path.parent.name
                break

            frame = frame.f_back
    finally:
        del frame

    if not service_name:
        raise RuntimeError(
            "No se pudo detectar automáticamente el nombre del servicio. Usa ConfigLoader.initialize_service(service_name) manualmente."
        )

    ConfigLoader.initialize_service(service_name)


# Inicialización automática al importar este módulo
# Comentar esta línea si prefieres inicialización manual
# auto_initialize_config()
