# src/common/clients/api_gateway_client.py
import asyncio
import logging
import ssl  # <-- 1. Importar el módulo SSL
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ApiGatewayClient:
    """
    Cliente para obtener y gestionar tokens de autenticación del API Gateway.
    """

    def __init__(self, config: Dict):
        self.base_url = config["url"]
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.grant_type = config["grant_type"]
        self.scope = config["scope"]
        self.timeout = config.get("timeout_seconds", 30)
        self.expiration_buffer = timedelta(seconds=config.get("token_expiration_buffer_sec", 300))

        self._token: Optional[str] = None
        self._token_type: str = "Bearer"
        self._expires_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

        # --- INICIO DE LA CORRECCIÓN ---
        # 2. Crear un contexto SSL personalizado para permitir cifrados más antiguos
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")

        # 3. Pasar el contexto al cliente httpx
        self._client = httpx.AsyncClient(timeout=self.timeout, verify=context)
        # --- FIN DE LA CORRECCIÓN ---

        logger.info("Cliente para API Gateway inicializado.")

    async def _fetch_new_token(self):
        """
        Realiza la llamada a la API para obtener un nuevo token.
        Este método debe ser llamado dentro de un lock.
        """
        logger.info("Solicitando nuevo token al API Gateway...")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": self.grant_type,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        try:
            response = await self._client.post(self.base_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()

            self._token = token_data["access_token"]
            self._token_type = token_data.get("token_type", "Bearer")
            expires_in_seconds = token_data.get("expires_in", 3600)

            # Calculamos el tiempo de expiración real con un margen de seguridad
            self._expires_at = datetime.now() + timedelta(seconds=expires_in_seconds) - self.expiration_buffer

            logger.info(f"Nuevo token de API Gateway obtenido. Válido hasta: {self._expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al obtener token del API Gateway: {e.response.status_code} - {e.response.text}")
            raise
        except (KeyError, Exception) as e:
            logger.error(f"Error al procesar la respuesta del token del API Gateway: {e}", exc_info=True)
            raise

    def is_token_valid(self) -> bool:
        """Verifica si el token actual existe y no ha expirado."""
        return self._token is not None and self._expires_at is not None and datetime.now() < self._expires_at

    async def get_valid_token(self) -> Optional[str]:
        """
        Devuelve un token válido, solicitando uno nuevo si es necesario.
        Es seguro para ser llamado concurrentemente desde múltiples tareas.
        """
        if self.is_token_valid():
            return self._token

        async with self._lock:
            # Doble chequeo para evitar peticiones redundantes si varias tareas esperan el lock
            if self.is_token_valid():
                return self._token

            await self._fetch_new_token()
            return self._token

    async def get_auth_header(self) -> Dict[str, str]:
        """
        Construye el diccionario de cabecera de autorización completo.
        """
        token = await self.get_valid_token()
        if not token:
            return {}

        headers = {"Authorization": f"{self._token_type} {token}", "x-ibm-client-id": self.client_id}

        # Devolver solo las cabeceras que tienen un valor asignado
        return {k: v for k, v in headers.items() if v is not None}

    async def close(self):
        """Cierra la sesión del cliente httpx."""
        if not self._client.is_closed:
            await self._client.aclose()
            logger.info("Cliente API de Gateway cerrado.")
