"""Tests para el backend de la Interfaz Web."""

import pytest
from fastapi.testclient import TestClient

from sam.web.backend.dependencies import get_db
from sam.web.main import app


@pytest.fixture
def client(mock_db_connector):
    """Cliente de prueba de FastAPI para la interfaz web, adaptado para Lifespan."""
    app.dependency_overrides[get_db] = lambda: mock_db_connector
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestWebAPIEndpoints:
    def test_get_robots_endpoint(self, client: TestClient, mock_db_connector):
        """Verifica que el endpoint para obtener robots funciona correctamente."""
        mock_db_connector.ejecutar_consulta.side_effect = [
            [{"total_count": 1}],
            [{"RobotId": 1, "Robot": "TestBot", "Activo": True, "EsOnline": False}],
        ]
        response = client.get("/api/robots", params={"page": 1, "size": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["robots"]) == 1
        assert data["robots"][0]["Robot"] == "TestBot"

    def test_update_robot_status_endpoint(self, client: TestClient, mock_db_connector):
        """Verifica que el endpoint para actualizar el estado de un robot funciona."""
        mock_db_connector.ejecutar_consulta.return_value = 1
        response = client.patch("/api/robots/1", json={"Activo": False})
        assert response.status_code == 200
        assert "actualizado con éxito" in response.json()["message"]

    def test_update_robot_status_not_found(self, client: TestClient, mock_db_connector):
        """Verifica que se devuelve un 404 si el robot a actualizar no existe."""
        mock_db_connector.ejecutar_consulta.return_value = 0
        response = client.patch("/api/robots/999", json={"Activo": False})
        assert response.status_code == 404
        assert "Robot no encontrado" in response.json()["detail"]
