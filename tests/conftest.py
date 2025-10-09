"""Pytest configuration and fixtures"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Añadir src/ al path para que los imports funcionen
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- Inicialización Global para Tests ---
# Esto se ejecuta una sola vez cuando pytest carga este archivo.
from sam.common.config_loader import ConfigLoader

if not ConfigLoader.is_initialized():
    # Seteamos variables de entorno FALSAS que ConfigManager leerá.
    # Esto evita que los tests dependan de un archivo .env.
    os.environ["SQL_SAM_HOST"] = "test_server"
    os.environ["SQL_SAM_DB_NAME"] = "SAM_TEST"
    os.environ["SQL_SAM_UID"] = "test_user"
    os.environ["SQL_SAM_PWD"] = "test_pass"
    os.environ["CALLBACK_TOKEN"] = "test_token_123"
    # Añadimos las variables para el segundo conector de BD del balanceador
    os.environ["SQL_RPA360_HOST"] = "test_server_rpa"
    os.environ["SQL_RPA360_DB_NAME"] = "RPA360_TEST"
    os.environ["SQL_RPA360_UID"] = "test_user_rpa"
    os.environ["SQL_RPA360_PWD"] = "test_pass_rpa"

    # Inicializamos el cargador en un modo de "test"
    ConfigLoader.initialize_service("test")


# --- Fixtures Reutilizables ---


@pytest.fixture
def mock_db_connector(mocker):
    """
    Mock de DatabaseConnector. Se usa en la mayoría de los tests
    para simular la interacción con la base de datos.
    """
    # Usamos `spec=True` para que el mock tenga la misma interfaz que la clase real.
    # Si intentas llamar a un método que no existe en DatabaseConnector, el test fallará.
    mock = mocker.MagicMock(spec=True, instance=True, name="DatabaseConnector()")
    # Configuramos un comportamiento por defecto
    mock.ejecutar_consulta.return_value = []
    # `spec` no mockea métodos mágicos, así que lo hacemos manualmente si es necesario
    mock.__enter__.return_value = mock
    mock.__exit__.return_value = None
    return mock


@pytest.fixture
def mock_aa_client(mocker):
    """
    Mock de AutomationAnywhereClient, preparado para métodos asíncronos.
    """
    # Usamos `AsyncMock` para métodos `async def`.
    mock = mocker.MagicMock(spec=True, instance=True, name="AutomationAnywhereClient()")
    mock.obtener_robots = AsyncMock(return_value=[])
    mock.obtener_devices = AsyncMock(return_value=[])
    mock.obtener_usuarios_detallados = AsyncMock(return_value=[])
    mock.desplegar_bot_v4 = AsyncMock(return_value={"deploymentId": "test-deploy-id"})
    mock.obtener_detalles_por_deployment_ids = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_apigw_client(mocker):
    """Mock de ApiGatewayClient, preparado para métodos asíncronos."""
    mock = mocker.MagicMock(spec=True, instance=True, name="ApiGatewayClient()")
    mock.get_auth_header = AsyncMock(return_value={"Authorization": "Bearer test-gateway-token"})
    return mock
