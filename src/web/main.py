# src/web/main.py
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from reactpy.backend.fastapi import Options, configure
from starlette.staticfiles import StaticFiles

from src.common.database.sql_client import DatabaseConnector

# Importa el router de la API y el nuevo proveedor de dependencias
from .backend.api import router as api_router
from .backend.dependencies import db_dependency_provider

# Importa el componente raíz y la cabecera de ReactPy
from .frontend.app import App, head

# --- App Global ---
# Se crea la instancia de FastAPI a nivel de módulo para que Uvicorn pueda importarla.
app = FastAPI(title="SAM Interfaz Web API")


def create_app(db_connector: DatabaseConnector) -> FastAPI:
    """
    Configura la instancia global de la aplicación, inyectando las dependencias.
    """
    # Hacemos que el conector de la BD esté disponible para el proveedor de dependencias
    db_dependency_provider.set_db_connector(db_connector)

    # --- Montar Rutas y Archivos ---
    app.include_router(api_router)

    static_files_path = Path(__file__).parent / "static"
    if static_files_path.exists():
        app.mount("/static", StaticFiles(directory=static_files_path), name="static")

    # Configura ReactPy
    configure(app, App, options=Options(head=head))

    return app
