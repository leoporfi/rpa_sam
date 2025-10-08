# src/interfaz_web/utils/exceptions.py
from typing import Dict, List, Optional


class APIException(Exception):
    """Excepción personalizada para errores relacionados con la API."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        if self.status_code:
            return f"[API Error {self.status_code}]: {self.message}"
        return f"[API Error]: {self.message}"


class ValidationException(Exception):
    """Excepción para errores de validación de datos."""

    def __init__(self, message: str, errors: Optional[List[Dict[str, str]]] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)

    def __str__(self):
        return f"[Validation Error]: {self.message} - {self.errors}"
