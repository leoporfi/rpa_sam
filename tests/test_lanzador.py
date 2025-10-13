from unittest.mock import AsyncMock, MagicMock

import pytest

from sam.common.a360_client import AutomationAnywhereClient

# Importaciones corregidas y necesarias para las pruebas
from sam.lanzador.service.desplegador import Desplegador
from sam.lanzador.service.sincronizador import Sincronizador

# La fixture 'mock_db_connector' se inyecta automáticamente, no se importa.

# Marcamos todas las pruebas en este módulo para que usen asyncio.
pytestmark = pytest.mark.asyncio


async def test_desplegador_deploys_pending_robot(mock_db_connector):
    """
    Verifica que el Desplegador intenta lanzar un robot que está pendiente.
    """
    # 1. Arrange: Preparamos el escenario de la prueba
    mock_robot_pendiente = (1, "TestBot", None, "PENDIENTE", None)
    mock_db_connector.fetch_one.return_value = mock_robot_pendiente

    mock_a360_client = AsyncMock(spec=AutomationAnywhereClient)
    mock_a360_client.deploy_bot.return_value = {"deploymentId": "test-deployment-123"}

    desplegador = Desplegador(db_connector=mock_db_connector, a360_client=mock_a360_client)

    # 2. Act: Ejecutamos la lógica que queremos probar
    await desplegador.run()

    # 3. Assert: Verificamos que el resultado es el esperado
    mock_db_connector.fetch_one.assert_called_once()
    mock_a360_client.deploy_bot.assert_called_once()
    mock_db_connector.execute.assert_called_once()


async def test_desplegador_handles_no_robots_to_deploy(mock_db_connector):
    """
    Verifica que el Desplegador no hace nada si no hay robots pendientes.
    """
    # Arrange
    mock_db_connector.fetch_one.return_value = None
    mock_a360_client = AsyncMock(spec=AutomationAnywhereClient)
    desplegador = Desplegador(db_connector=mock_db_connector, a360_client=mock_a360_client)

    # Act
    await desplegador.run()

    # Assert
    mock_a360_client.deploy_bot.assert_not_called()


async def test_sincronizador_updates_running_deployment(mock_db_connector):
    """
    Verifica que el Sincronizador actualiza el estado de un robot 'EN_CURSO'.
    """
    # Arrange
    mock_robot_en_curso = (1, "TestBot", "dep-123", "EN_CURSO", None)
    mock_db_connector.fetch_all.return_value = [mock_robot_en_curso]

    mock_a360_client = AsyncMock(spec=AutomationAnywhereClient)
    mock_a360_client.get_deployment_status.return_value = {"status": "COMPLETED"}

    sincronizador = Sincronizador(db_connector=mock_db_connector, a360_client=mock_a360_client)

    # Act
    await sincronizador.run()

    # Assert
    mock_a360_client.get_deployment_status.assert_called_once_with("dep-123")
    mock_db_connector.execute.assert_called_once()
