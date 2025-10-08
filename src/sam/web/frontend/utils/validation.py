# src/interfaz_web/utils/validation.py
from typing import Any, Dict, List, NamedTuple


# Usamos una NamedTuple para devolver un resultado de validación claro y estructurado
class ValidationResult(NamedTuple):
    is_valid: bool
    errors: List[str]


def validate_robot_data(data: Dict[str, Any], is_update: bool = False) -> ValidationResult:
    """
    Valida los datos de un robot antes de enviarlos a la API.
    """
    errors: List[str] = []

    # El nombre del robot es siempre requerido
    if not data.get("Robot", "").strip():
        errors.append("El nombre del robot es un campo requerido.")

    # Validar campos numéricos
    numeric_fields = ["MinEquipos", "MaxEquipos", "PrioridadBalanceo"]
    for field in numeric_fields:
        value = data.get(field)
        if value is None or not isinstance(value, int):
            errors.append(f"El campo '{field}' debe ser un número entero.")

    if not errors:
        return ValidationResult(is_valid=True, errors=[])

    return ValidationResult(is_valid=False, errors=errors)
