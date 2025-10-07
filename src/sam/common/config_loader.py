import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigLoader:
    """
    Cargador de configuración estandarizado para todos los servicios SAM.
    Jerarquía: .env de servicio > .env general > variables de entorno.
    """

    _initialized = False
    _project_root: Optional[Path] = None

    @classmethod
    def initialize_service(cls, service_name: str) -> None:
        """
        Inicializa la configuración para un servicio. Encuentra la raíz del proyecto
        buscando 'pyproject.toml' para ser robusto ante diferentes métodos de ejecución.
        """
        if cls._initialized:
            return

        # --- Lógica robusta para encontrar la raíz del proyecto ---
        try:
            # Empezamos desde la ubicación de este mismo archivo
            current_file = Path(__file__).resolve()
            # Subimos por el árbol de directorios hasta encontrar pyproject.toml
            project_root = current_file
            while not (project_root / "pyproject.toml").exists():
                if project_root.parent == project_root:  # Si llegamos a la raíz del sistema (/)
                    raise FileNotFoundError
                project_root = project_root.parent
            cls._project_root = project_root
        except (FileNotFoundError, AttributeError):
            # Fallback si todo lo demás falla (ej. en entornos extraños)
            cls._project_root = Path.cwd()
            print(
                f"ADVERTENCIA CONFIG_LOADER: No se pudo encontrar 'pyproject.toml'. Usando el directorio actual como raíz del proyecto: {cls._project_root}",
                file=sys.stderr,
            )

        cls._load_environment_variables(service_name)
        cls._initialized = True
        os.environ["SAM_CONFIG_INITIALIZED"] = "True"

        print(f"CONFIG_LOADER: Servicio '{service_name}' inicializado", file=sys.stderr)
        print(f"CONFIG_LOADER: Proyecto root: {cls._project_root}", file=sys.stderr)

    @classmethod
    def _load_environment_variables(cls, service_name: str) -> None:
        """
        Carga variables de entorno con la jerarquía correcta.
        """
        # 1. .env general del proyecto (el más bajo en precedencia)
        project_env_path = cls._project_root / ".env"
        if project_env_path.exists():
            print(f"CONFIG_LOADER: Cargando .env general desde {project_env_path}", file=sys.stderr)
            # `override=False` asegura que no sobreescriba variables ya existentes
            load_dotenv(dotenv_path=project_env_path, override=False)

        # 2. .env específico del servicio (mayor precedencia que el general)
        # Asume la estructura src/sam/{nombre_servicio}/.env
        service_env_path = cls._project_root / "src" / "sam" / service_name / ".env"
        if service_env_path.exists():
            print(f"CONFIG_LOADER: Cargando .env específico desde {service_env_path}", file=sys.stderr)
            # `override=True` para que la config específica del servicio pueda sobreescribir la general
            load_dotenv(dotenv_path=service_env_path, override=True)

        # Las variables de entorno del sistema operativo siempre tienen la máxima precedencia
        # y no son sobreescritas por `load_dotenv` por defecto.

    @classmethod
    def get_project_root(cls) -> Path:
        """Retorna la ruta raíz del proyecto."""
        if not cls._initialized:
            raise RuntimeError("ConfigLoader no ha sido inicializado. Llama a initialize_service() primero.")
        return cls._project_root

    @classmethod
    def is_initialized(cls) -> bool:
        """Retorna True si el ConfigLoader ya fue inicializado."""
        return cls._initialized

    @classmethod
    def reset(cls) -> None:
        """Resetea el estado del ConfigLoader (útil para testing)."""
        cls._initialized = False
        cls._project_root = None
        if "SAM_CONFIG_INITIALIZED" in os.environ:
            del os.environ["SAM_CONFIG_INITIALIZED"]
