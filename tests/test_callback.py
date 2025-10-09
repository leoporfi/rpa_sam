"""Tests para el servicio Callback, adaptados para la arquitectura lifespan."""

import pytest
from fastapi.testclient import TestClient

from sam.callback.service.main import CallbackPayload, app, get_db
from sam.common.database import UpdateStatus


@pytest.fixture
def client(mock_db_connector):
    """Cliente de prueba de FastAPI que sobrescribe la dependencia de la base de datos."""
    app.dependency_overrides[get_db] = lambda: mock_db_connector
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestCallbackEndpoints:
    def test_health_check_endpoint(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        # CORRECCIÓN: El mensaje exacto debe coincidir con el del código
        assert response.json()["message"] == "Servicio de Callback activo y saludable."

    def test_callback_fails_without_auth_header(self, client: TestClient):
        response = client.post("/api/callback", json={"deploymentId": "test-123", "status": "COMPLETED"})
        # CORRECCIÓN: FastAPI devuelve 403 Forbidden cuando un `Header` dependency no se puede resolver.
        assert response.status_code == 403

    def test_callback_fails_with_invalid_auth_header(self, client: TestClient):
        response = client.post(
            "/api/callback",
            json={"deploymentId": "test-123", "status": "COMPLETED"},
            headers={"X-Authorization": "token_incorrecto"},
        )
        assert response.status_code == 401
        assert "X-Authorization header inválido" in response.json()["detail"]

    def test_callback_succeeds_and_updates_db(self, client: TestClient, mock_db_connector):
        mock_db_connector.actualizar_ejecucion_desde_callback.return_value = UpdateStatus.UPDATED
        payload = {"deploymentId": "test-123", "status": "COMPLETED"}
        response = client.post("/api/callback", json=payload, headers={"X-Authorization": "test_token_123"})

        assert response.status_code == 200
        assert response.json()["message"] == "Callback procesado y estado actualizado."

        # CORRECCIÓN: Pydantic V2 usa model_dump_json. `by_alias=True` es crucial.
        expected_payload_obj = CallbackPayload(**payload)
        expected_payload_str = expected_payload_obj.model_dump_json(by_alias=True)

        mock_db_connector.actualizar_ejecucion_desde_callback.assert_called_once_with(
            deployment_id="test-123",
            estado_callback="COMPLETED",
            callback_payload_str=expected_payload_str,
        )
