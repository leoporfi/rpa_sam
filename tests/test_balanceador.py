"""Tests para la lógica de negocio del servicio Balanceador."""

from unittest.mock import MagicMock

import pytest

from sam.balanceador.service.algoritmo_balanceo import Balanceo


@pytest.fixture
def mock_notificador():
    """Fixture para mockear el cliente de email."""
    return MagicMock()


class TestAlgoritmoBalanceo:
    """Tests unitarios para la clase Balanceo, el 'cerebro' del servicio."""

    def test_asignar_equipos_minimos_necesarios(self, mock_db_connector: MagicMock, mock_notificador: MagicMock):
        """Verifica que se asigna un equipo a un robot por debajo de su mínimo."""
        config = {"cooling_period_seg": 300, "aislamiento_estricto_pool": True}
        # CORRECCIÓN: El constructor de Balanceo ahora recibe las dependencias explícitamente.
        algoritmo = Balanceo(db_connector=mock_db_connector, notificador=mock_notificador, config_balanceador=config)

        estado_global = {
            "mapa_config_robots": {
                1: {"RobotId": 1, "MinEquipos": 2, "MaxEquipos": 5, "PoolId": 1, "TicketsPorEquipoAdicional": 10}
            },
            "mapa_equipos_validos_por_pool": {1: {101, 102}},
            "mapa_asignaciones_dinamicas": {1: [101]},
            "equipos_con_asignacion_fija": set(),
            "carga_trabajo_por_robot": {1: 10},
        }

        algoritmo.ejecutar_balanceo_interno_de_pool(pool_id=1, estado_global=estado_global)

        mock_db_connector.ejecutar_consulta.assert_called()
        args, _ = mock_db_connector.ejecutar_consulta.call_args
        assert "INSERT INTO dbo.Asignaciones" in args[0]
        assert args[1][0] == 1
        assert args[1][1] == 102

    def test_desasignar_equipos_excedentes(self, mock_db_connector: MagicMock, mock_notificador: MagicMock):
        """Verifica que se desasigna un equipo de un robot sin carga de trabajo."""
        config = {"cooling_period_seg": 300, "aislamiento_estricto_pool": True}
        algoritmo = Balanceo(db_connector=mock_db_connector, notificador=mock_notificador, config_balanceador=config)

        estado_global = {
            "mapa_config_robots": {2: {"RobotId": 2, "MinEquipos": 1, "MaxEquipos": 3, "PoolId": 1, "EsOnline": False}},
            "mapa_equipos_validos_por_pool": {1: {201, 202}},
            "mapa_asignaciones_dinamicas": {2: [201, 202]},
            "equipos_con_asignacion_fija": set(),
            "carga_trabajo_por_robot": {},
        }

        algoritmo.ejecutar_limpieza_global(estado_global=estado_global)

        mock_db_connector.ejecutar_consulta.assert_called()
        args, _ = mock_db_connector.ejecutar_consulta.call_args
        assert "DELETE FROM dbo.Asignaciones" in args[0]
        assert args[1][0] == 2
        assert args[1][1] in [201, 202]
