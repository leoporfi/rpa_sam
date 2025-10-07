# src/interfaz_web/dependencies.py
from typing import Optional

from fastapi import HTTPException

from sam.common.database import DatabaseConnector


class DBDependencyProvider:
    """
    Clase que actúa como un contenedor para nuestra dependencia de base de datos.
    Esto resuelve el problema de cómo pasar la instancia creada en run_dashboard.py
    a los endpoints de la API que la necesitan a través de FastAPI `Depends`.
    """

    def __init__(self):
        self._db_connector: Optional[DatabaseConnector] = None

    def set_db_connector(self, db_connector: DatabaseConnector):
        """Este método es llamado una vez al inicio desde run_dashboard.py."""
        self._db_connector = db_connector

    def get_db_connector(self) -> DatabaseConnector:
        """Esta es la función que FastAPI usará con `Depends`."""
        if self._db_connector is None:
            raise HTTPException(
                status_code=503,
                detail="La conexión a la base de datos no está disponible.",
            )
        return self._db_connector


# Creamos una instancia única que será compartida por toda la aplicación.
db_dependency_provider = DBDependencyProvider()

# Creamos el objeto `Depends` para usar en los endpoints.
# Es una convención útil para no tener que importar la instancia en cada archivo de ruta.
get_db = db_dependency_provider.get_db_connector
