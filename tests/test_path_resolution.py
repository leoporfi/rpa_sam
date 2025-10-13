"""
Esta prueba sirve únicamente para verificar que pytest está resolviendo
correctamente las rutas de importación desde el directorio `src`.
"""

import pytest


def test_can_import_common_module():
    """
    Intenta importar un módulo común. Si esto tiene éxito,
    significa que la configuración `pythonpath` en `pyproject.toml`
    está funcionando como se espera.
    """
    try:
        from sam.common.config_loader import ConfigLoader

        assert True, "La importación desde sam.common fue exitosa."
    except ImportError as e:
        pytest.fail(f"No se pudo importar el módulo: {e}. Revisa la configuración de pythonpath.")


def test_can_import_service_module():
    """
    Intenta importar un módulo de un servicio específico para asegurar
    que la resolución de rutas es completa.
    """
    try:
        from sam.lanzador.service.desplegador import Desplegador

        assert True, "La importación desde sam.lanzador.service fue exitosa."
    except ImportError as e:
        pytest.fail(f"No se pudo importar el módulo del servicio: {e}. Revisa la configuración de pythonpath.")
