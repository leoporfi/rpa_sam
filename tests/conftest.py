from unittest.mock import MagicMock, patch

import pytest

# Esta importación es necesaria para que la fixture de configuración funcione.
from sam.common.config_loader import ConfigLoader


@pytest.fixture(scope="session", autouse=True)
def setup_and_mock_config(pytestconfig):
    """
    Se ejecuta una sola vez por sesión para asegurar que la configuración
    esté 'mockeada' antes de que cualquier prueba se ejecute.
    Esto previene que los tests intenten leer archivos .env.
    """
    # Inicializa el cargador para asegurar que sys.path sea correcto.
    ConfigLoader.initialize_service("sam_test_session")

    # Usamos patch para interceptar las llamadas al ConfigManager.
    # Esto reemplaza la necesidad de un archivo .env durante las pruebas.
    mock_settings = {
        "CALLBACK_AUTH_TOKEN": "test-token",
        "A360_CONTROL_ROOM_URL": "https://test.a360.com",
        "A360_API_KEY": "test-key",
        "A360_USER": "test-user",
        "SQL_SAM_SERVER": "test-server",
        "SQL_SAM_DATABASE": "test-db",
        "SQL_SAM_USER": "test-user",
        "SQL_SAM_PASSWORD": "test-password",
    }

    # Creamos un 'side effect' para simular la obtención de valores.
    def mock_get(key, default=None):
        return mock_settings.get(key, default)

    # Aplicamos el patch a los métodos de ConfigManager
    patch("sam.common.config_manager.ConfigManager.get_str", side_effect=mock_get).start()
    patch("sam.common.config_manager.ConfigManager.get_int", return_value=30).start()
    patch("sam.common.config_manager.ConfigManager.get_bool", return_value=True).start()


@pytest.fixture
def mock_db_connector():
    """
    Crea un mock autocontenido del DatabaseConnector para inyectar en los tests.
    """
    connector = MagicMock()
    # Usamos AsyncMock para los métodos que son `async`
    connector.connect = MagicMock()
    connector.close = MagicMock()
    connector.fetch_all = MagicMock(return_value=[])
    connector.fetch_one = MagicMock(return_value=None)
    connector.execute = MagicMock(return_value=None)
    return connector
