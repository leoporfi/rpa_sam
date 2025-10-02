# src\balanceador\clients\clouders_client.py
import logging
from typing import Any, Dict, List

import requests
import urllib3

from src.common.utils.config_manager import ConfigManager

# Suprimir advertencias de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Obtener el logger de la forma estandarizada
logger = logging.getLogger(__name__)


class CloudersClient:
    """Cliente para acceder a la API de Clouders y obtener tickets pendientes."""

    def __init__(self):
        """
        Inicializa el cliente de Clouders.
        La configuración se obtiene directamente del ConfigManager.
        """
        config = ConfigManager.get_clouders_api_config()

        self.base_url = config.get("clouders_api_url")
        self.auth_header = config.get("clouders_auth")
        self.timeout = config.get("clouders_api_timeout", 30)
        self.verify_ssl = config.get("clouders_verify_ssl", False)
        self.mapa_robots = ConfigManager.get_mapa_robots()

        if not self.base_url or not self.auth_header:
            raise ValueError("La configuración para Clouders API (URL y Auth) es requerida.")

        if not self.verify_ssl:
            logger.warning("La verificación SSL está deshabilitada. No recomendado para producción.")

    def obtener_tickets_pendientes(self) -> List[Dict[str, Any]]:
        """
        Obtiene la cantidad de tickets pendientes por robot desde la API de Clouders.
        """
        endpoint = f"{self.base_url}/automatizacion/task/api/stats/pending_by_robot"
        headers = {"Accept": "application/json", "Authorization": self.auth_header}

        try:
            logger.debug(f"Consultando tickets pendientes en: {endpoint}")
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()

            data = response.json()
            resultados = []

            for item in data:
                for robot_name, cantidad in item.items():
                    resultado = {
                        "robot_name": robot_name,
                        "CantidadTickets": cantidad,
                    }
                    # Aplicar mapeo de robots si existe
                    robot_sam = self.mapa_robots.get(robot_name)
                    if robot_sam:
                        resultado["robot_name_sam"] = robot_sam
                        logger.debug(f"Robot mapeado: {robot_name} → {robot_sam}")
                    resultados.append(resultado)

            logger.info(f"Obtenidos {len(resultados)} robots con tickets pendientes desde Clouders.")
            return resultados

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener tickets pendientes de Clouders: {e}", exc_info=True)
            # Devolver una lista vacía en caso de error para no detener el ciclo de balanceo
            return []
