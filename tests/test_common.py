"""Tests para los módulos de `common`."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sam.common.a360_client import AutomationAnywhereClient
from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager


class TestConfigLoading:
    def test_config_loader_initialized(self, mock_db_connector):
        assert ConfigLoader.is_initialized()
        project_root = ConfigLoader.get_project_root()
        assert project_root.is_dir()
        assert (project_root / "pyproject.toml").exists()

    def test_config_manager_reads_mock_env(self, mock_db_connector):
        sql_config = ConfigManager.get_sql_server_config("SQL_SAM")
        assert sql_config["servidor"] == "test_server"
        callback_config = ConfigManager.get_callback_server_config()
        assert callback_config["token"] == "test_token_123"


@pytest.mark.asyncio
class TestAutomationAnywhereClient:
    async def test_token_refresh_on_401(self):
        """
        Verifica que el cliente intenta obtener un nuevo token y reintentar la llamada
        cuando recibe un error 401 (Unauthorized).
        """
        mock_async_client = AsyncMock(spec=httpx.AsyncClient)

        mock_auth_response = MagicMock(spec=httpx.Response)
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "new_fresh_token"}

        mock_data_response = MagicMock(spec=httpx.Response)
        mock_data_response.status_code = 200
        mock_data_response.json.return_value = {"list": [{"id": 1, "name": "TestBot"}]}

        # CORRECCIÓN: Simplificamos la simulación del side_effect
        mock_async_client.request.side_effect = [
            httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=httpx.Response(401)),
            mock_data_response,
        ]
        mock_async_client.post.return_value = mock_auth_response

        with patch("sam.common.a360_client.httpx.AsyncClient", return_value=mock_async_client):
            aa_client = AutomationAnywhereClient(
                control_room_url="https://fake-cr.com", username="test", api_key="fake_key"
            )
            aa_client._token = "old_expired_token"

            robots = await aa_client.obtener_robots()

            assert aa_client._token == "new_fresh_token"
            assert robots is not None
            assert mock_async_client.post.call_count == 1
            assert mock_async_client.request.call_count == 2
