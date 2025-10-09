"""Tests para los componentes 'cerebro' del servicio Lanzador."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sam.lanzador.service.conciliador import Conciliador
from sam.lanzador.service.desplegador import Desplegador
from sam.lanzador.service.sincronizador import Sincronizador


@pytest.mark.asyncio
class TestSincronizador:
    """Tests para la lógica de sincronización de entidades."""

    async def test_sincronizar_entidades_happy_path(self, mock_db_connector, mock_aa_client):
        """Verifica el flujo de sincronización exitoso."""
        # Configuración de mocks para devolver datos
        mock_aa_client.obtener_robots.return_value = [{"RobotId": 1, "Robot": "Bot1"}]
        mock_aa_client.obtener_devices.return_value = [{"EquipoId": 101, "Equipo": "VM01", "UserId": 201}]
        mock_aa_client.obtener_usuarios_detallados.return_value = [{"UserId": 201, "Licencia": "ATTENDED"}]

        sincronizador = Sincronizador(db_connector=mock_db_connector, aa_client=mock_aa_client)
        await sincronizador.sincronizar_entidades()

        # Verificaciones
        mock_aa_client.obtener_robots.assert_awaited_once()
        mock_aa_client.obtener_devices.assert_awaited_once()
        mock_aa_client.obtener_usuarios_detallados.assert_awaited_once()

        mock_db_connector.merge_robots.assert_called_once_with([{"RobotId": 1, "Robot": "Bot1"}])
        # Verificamos que el device fue enriquecido con la licencia
        mock_db_connector.merge_equipos.assert_called_once_with(
            [{"EquipoId": 101, "Equipo": "VM01", "UserId": 201, "Licencia": "ATTENDED"}]
        )

    async def test_sincronizar_entidades_api_failure(self, mock_db_connector, mock_aa_client, caplog):
        """Verifica que un fallo en la API se maneja correctamente."""
        mock_aa_client.obtener_robots.side_effect = Exception("Fallo de red")

        sincronizador = Sincronizador(db_connector=mock_db_connector, aa_client=mock_aa_client)
        await sincronizador.sincronizar_entidades()

        # Verificamos que se registró el error
        assert "Error grave durante el ciclo de sincronización" in caplog.text
        # Verificamos que no se intentó actualizar la BD
        mock_db_connector.merge_robots.assert_not_called()
        mock_db_connector.merge_equipos.assert_not_called()


@pytest.mark.asyncio
class TestDesplegador:
    """Tests para la lógica de despliegue de robots."""

    @pytest.fixture
    def desplegador_instance(self, mock_db_connector, mock_aa_client, mock_apigw_client):
        """Crea una instancia de Desplegador para los tests."""
        config = {
            "repeticiones": 1,
            "max_workers_lanzador": 5,
            "max_reintentos_deploy": 1,
            "delay_reintento_deploy_seg": 1,
            "pausa_lanzamiento": ("23:00", "05:00"),
        }
        return Desplegador(
            db_connector=mock_db_connector,
            aa_client=mock_aa_client,
            api_gateway_client=mock_apigw_client,
            lanzador_config=config,
            callback_token="test_token",
        )

    async def test_desplegar_cuando_hay_robots_pendientes(
        self, desplegador_instance, mock_db_connector, mock_aa_client
    ):
        """Verifica que se despliegan los robots devueltos por la BD."""
        mock_db_connector.obtener_robots_ejecutables.return_value = [{"RobotId": 1, "UserId": 101, "EquipoId": 201}]
        await desplegador_instance.desplegar_robots_pendientes()

        mock_aa_client.desplegar_bot_v4.assert_awaited_once()
        mock_db_connector.insertar_registro_ejecucion.assert_called_once()

    async def test_no_desplegar_cuando_no_hay_robots(self, desplegador_instance, mock_db_connector, mock_aa_client):
        """Verifica que no se hace nada si no hay robots para ejecutar."""
        # CORRECCIÓN: El método que se llama es de mock_db_connector
        mock_db_connector.obtener_robots_ejecutables.return_value = []
        await desplegador_instance.desplegar_robots_pendientes()
        mock_aa_client.desplegar_bot_v4.assert_not_awaited()

    async def test_reintento_en_fallo_de_dispositivo_no_activo(
        self, desplegador_instance, mock_aa_client, mock_db_connector, caplog
    ):
        """Verifica la lógica de reintento si el dispositivo no está activo."""
        mock_db_connector.obtener_robots_ejecutables.return_value = [{"RobotId": 1, "UserId": 101}]
        # Simular que el primer intento falla y el segundo tiene éxito
        mock_aa_client.desplegar_bot_v4.side_effect = [
            httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=httpx.Response(400, text="Devices [101] are not active"),
            ),
            {"deploymentId": "test-deploy-id-retry"},
        ]
        await desplegador_instance.desplegar_robots_pendientes()

        assert "El dispositivo no está activo. Reintentando" in caplog.text
        assert mock_aa_client.desplegar_bot_v4.await_count == 2
        mock_db_connector.insertar_registro_ejecucion.assert_called_once_with(
            id_despliegue="test-deploy-id-retry",
            db_robot_id=1,
            db_equipo_id=None,
            a360_user_id=101,
            marca_tiempo_programada=None,
            estado="DEPLOYED",
        )


@pytest.mark.asyncio
class TestConciliador:
    """Tests para la lógica de conciliación de estados."""

    @pytest.fixture
    def conciliador_instance(self, mock_db_connector, mock_aa_client):
        """Crea una instancia de Conciliador para los tests."""
        return Conciliador(db_connector=mock_db_connector, aa_client=mock_aa_client, max_intentos_fallidos=3)

    async def test_conciliar_ejecucion_encontrada(self, conciliador_instance, mock_db_connector, mock_aa_client):
        """Verifica que se actualiza una ejecución encontrada en la API."""
        mock_db_connector.obtener_ejecuciones_en_curso.return_value = [{"EjecucionId": 1, "DeploymentId": "abc-123"}]
        mock_aa_client.obtener_detalles_por_deployment_ids.return_value = [
            {"deploymentId": "abc-123", "status": "COMPLETED", "endDateTime": "2025-10-08T18:30:00Z"}
        ]
        await conciliador_instance.conciliar_ejecuciones()

        # Verifica que se intentó actualizar con los datos correctos
        mock_db_connector.ejecutar_consulta_multiple.assert_called_once()
        # El primer argumento de la llamada es la query, el segundo son los parámetros
        args, _ = mock_db_connector.ejecutar_consulta_multiple.call_args
        # args[1] es la lista de tuplas con los parámetros
        assert args[1][0][0] == "COMPLETED"  # Estado
        assert args[1][0][2] == 1  # EjecucionId

    async def test_conciliar_ejecucion_no_encontrada(
        self, conciliador_instance, mock_db_connector, mock_aa_client, caplog
    ):
        """Verifica que se incrementa el contador de intentos para una ejecución no encontrada."""
        mock_db_connector.obtener_ejecuciones_en_curso.return_value = [{"EjecucionId": 2, "DeploymentId": "def-456"}]
        mock_aa_client.obtener_detalles_por_deployment_ids.return_value = []  # La API no devuelve nada
        await conciliador_instance.conciliar_ejecuciones()

        assert "Incrementado contador de intentos para 1 deployment(s)" in caplog.text
        # Verifica que se llamó para incrementar el contador
        update_query = mock_db_connector.ejecutar_consulta.call_args_list[0].args[0]
        assert "IntentosConciliadorFallidos = IntentosConciliadorFallidos + 1" in update_query

    async def test_marcar_como_unknown_al_superar_intentos(
        self, conciliador_instance, mock_db_connector, mock_aa_client, caplog
    ):
        """Verifica que una ejecución se marca como UNKNOWN al superar el umbral de reintentos."""
        mock_db_connector.obtener_ejecuciones_en_curso.return_value = [{"EjecucionId": 3, "DeploymentId": "ghi-789"}]
        mock_aa_client.obtener_detalles_por_deployment_ids.return_value = []
        # Mock para que la segunda llamada a ejecutar_consulta (la de marcar UNKNOWN) devuelva 1 fila afectada.
        mock_db_connector.ejecutar_consulta.side_effect = [0, 1]

        await conciliador_instance.conciliar_ejecuciones()

        assert "Se marcaron 1 deployment(s) como UNKNOWN" in caplog.text
        update_query = mock_db_connector.ejecutar_consulta.call_args_list[1].args[0]
        params = mock_db_connector.ejecutar_consulta.call_args_list[1].args[1]
        assert "SET Estado = 'UNKNOWN'" in update_query
        assert params[1] == 3  # El umbral de max_intentos_fallidos
