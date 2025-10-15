# common/a360_client.py
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class AutomationAnywhereClient:
    _ENDPOINT_AUTH_V2 = "/v2/authentication"
    _ENDPOINT_ACTIVITY_LIST_V3 = "/v3/activity/list"
    _ENDPOINT_AUTOMATIONS_DEPLOY_V3 = "/v3/automations/deploy"
    _ENDPOINT_AUTOMATIONS_DEPLOY_V4 = "/v4/automations/deploy"
    _ENDPOINT_USERS_LIST_V2 = "/v2/usermanagement/users/list"
    _ENDPOINT_DEVICES_LIST_V2 = "/v2/devices/list"
    _ENDPOINT_FILES_LIST_V2 = "/v2/repository/workspaces/public/files/list"

    CONCILIADOR_BATCH_SIZE = 50  # Procesar de 50 en 50 para evitar timeouts

    def __init__(self, control_room_url: str, username: str, password: Optional[str] = None, **kwargs):
        self.url_base = control_room_url.strip("/")
        self.username = username
        self.password = password
        self.api_key = kwargs.get("api_key")
        self.api_timeout = kwargs.get("api_timeout_seconds", 60)
        self.callback_url_deploy = kwargs.get("callback_url_deploy")

        self._token: Optional[str] = None
        self._token_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(base_url=self.url_base, verify=False, timeout=self.api_timeout)
        logger.info(f"Cliente API Asíncrono inicializado para CR: {self.url_base}")

    # --- Métodos Internos: Gestión de Token y Peticiones ---

    async def _obtener_token(self, is_retry: bool = False):
        """Obtiene un nuevo token de autenticación, priorizando apiKey sobre password."""
        if is_retry:
            logger.warning("Intentando obtener un nuevo token de A360...")
        else:
            logger.info("Obteniendo token de A360...")

        payload = {"username": self.username}

        # Priorizar apiKey si está disponible y no es una cadena vacía
        if self.api_key:
            payload["apiKey"] = self.api_key
            logger.info("Intentando autenticación con apiKey.")
        # Si no hay apiKey, usar la contraseña como fallback
        elif self.password:
            payload["password"] = self.password
            logger.info("Intentando autenticación con contraseña.")
        else:
            # Si no hay ni apiKey ni contraseña, es un error de configuración
            error_msg = (
                "No se proporcionó ni AA_CR_API_KEY ni AA_CR_PWD para la autenticación en A360."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        response = await self._client.post(self._ENDPOINT_AUTH_V2, json=payload)
        response.raise_for_status()

        self._token = response.json().get("token")
        if self._token:
            self._client.headers["X-Authorization"] = self._token
            logger.info("Token de A360 obtenido/refrescado exitosamente.")
        else:
            logger.error("La autenticación fue exitosa pero no se recibió un token.")
            raise ValueError("No se recibió un token de la API de A360.")

    async def _asegurar_validez_del_token(self, is_retry: bool = False):
        """Asegura que tenemos un token. Se llama solo si no hay token o si ha expirado."""
        async with self._token_lock:
            # Doble chequeo para evitar que múltiples corutinas pidan token a la vez
            if not self._token or is_retry:
                await self._obtener_token(is_retry=is_retry)

    async def _realizar_peticion_api(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Realiza una petición a la API, manejando la obtención y refresco del token.
        """
        # Asegurarse de tener un token inicial si es la primera vez
        if not self._token:
            await self._asegurar_validez_del_token()

        try:
            # Primer intento de la petición
            response = await self._client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            # --- LÓGICA DE REFRESCO DE TOKEN ---
            # Si el error es 401 (No Autorizado), el token probablemente expiró.
            if e.response.status_code == 401:
                logger.warning(
                    "Recibido error 401 (No Autorizado). El token puede haber expirado. Intentando reautenticar..."
                )

                # Forzar la obtención de un nuevo token
                await self._asegurar_validez_del_token(is_retry=True)

                # Reintentar la petición original UNA VEZ MÁS con el nuevo token
                logger.info(f"Reintentando la petición a {endpoint} con el nuevo token...")
                response_retry = await self._client.request(method, endpoint, **kwargs)
                response_retry.raise_for_status()
                return response_retry.json() if response_retry.content else {}
            else:
                # Si es otro error HTTP, simplemente lo relanzamos
                raise

    async def _obtener_lista_paginada_entidades(self, endpoint: str, payload: Dict) -> List[Dict]:
        """
        Obtiene todas las entidades de un endpoint que soporta paginación.
        """
        lista_completa = []
        offset = 0
        page_size = 100
        payload["page"] = payload.get("page", {})

        while True:
            payload["page"]["offset"] = offset
            payload["page"]["length"] = page_size
            response_json = await self._realizar_peticion_api("POST", endpoint, json=payload)
            entidades_pagina = response_json.get("list", [])
            if not entidades_pagina:
                break
            lista_completa.extend(entidades_pagina)
            if len(entidades_pagina) < page_size:
                break
            offset += page_size

        logger.info(f"Paginación: Se obtuvieron un total de {len(lista_completa)} entidades de {endpoint}.")
        return lista_completa

    def _crear_filtro_deployment_ids(self, deployment_ids: List[str]) -> Dict:
        """Crea el payload de filtro para buscar por deployment IDs."""
        return {
            "sort": [{"field": "startDateTime", "direction": "desc"}],
            "filter": {
                "operator": "or",
                "operands": [{"operator": "eq", "field": "deploymentId", "value": dep_id} for dep_id in deployment_ids],
            },
        }

    # --- Métodos Públicos Asíncronos ---

    async def obtener_devices(self) -> List[Dict]:
        logger.info("Obteniendo devices de A360...")
        payload = {"filter": {"operator": "eq", "field": "status", "value": "CONNECTED"}}
        # RFR-27: Se elimina el mapeo. El cliente devuelve los datos en bruto de la API.
        devices_api = await self._obtener_lista_paginada_entidades(self._ENDPOINT_DEVICES_LIST_V2, payload)
        logger.info(f"Se encontraron {len(devices_api)} devices conectados.")
        return devices_api

    async def obtener_usuarios_detallados(self) -> List[Dict]:
        logger.info("Obteniendo usuarios detallados de A360...")
        # RFR-27: Se elimina el mapeo. El cliente devuelve los datos en bruto de la API.
        usuarios_api = await self._obtener_lista_paginada_entidades(self._ENDPOINT_USERS_LIST_V2, {})
        logger.info(f"Se encontraron {len(usuarios_api)} usuarios.")
        return usuarios_api

    async def obtener_devices_old(self) -> List[Dict]:
        logger.info("Obteniendo devices de A360...")
        payload = {"filter": {"operator": "eq", "field": "status", "value": "CONNECTED"}}
        devices_api = await self._obtener_lista_paginada_entidades(self._ENDPOINT_DEVICES_LIST_V2, payload)

        devices_mapeados = []
        for device in devices_api:
            user_info = (device.get("defaultUsers") or [{}])[0]
            devices_mapeados.append(
                {
                    "EquipoId": device.get("id"),
                    "Equipo": device.get("hostName"),
                    "UserId": user_info.get("id"),
                    "UserName": user_info.get("username"),
                }
            )
        logger.info(f"Se encontraron {len(devices_mapeados)} devices conectados.")
        return devices_mapeados

    async def obtener_usuarios_detallados_old(self) -> List[Dict]:
        logger.info("Obteniendo usuarios detallados de A360...")
        usuarios_api = await self._obtener_lista_paginada_entidades(self._ENDPOINT_USERS_LIST_V2, {})

        usuarios_mapeados = []
        for user in usuarios_api:
            licencia = "SIN_LICENCIA"
            if user.get("licenseFeatures"):
                licencia = user["licenseFeatures"][0]
            usuarios_mapeados.append(
                {
                    "UserId": user.get("id"),
                    "UserName": user.get("username"),
                    "Licencia": licencia,
                }
            )
        logger.info(f"Se encontraron {len(usuarios_mapeados)} usuarios.")
        return usuarios_mapeados

    async def obtener_robots(self) -> List[Dict]:
        logger.info("Obteniendo robots de A360...")
        payload = {
            "filter": {
                "operator": "and",
                "operands": [
                    {"operator": "substring", "field": "path", "value": "RPA"},
                    {"operator": "eq", "field": "type", "value": "application/vnd.aa.taskbot"},
                ],
            },
            "sort": [{"field": "id", "direction": "desc"}],
        }
        robots_api = await self._obtener_lista_paginada_entidades(self._ENDPOINT_FILES_LIST_V2, payload)

        expression = r"^P[A-Z0-9]*[0-9].*_.*"  # ^(P|CP)\S+[0-9]+_.+$
        patron_nombre = re.compile(expression)
        robots_mapeados = []
        for bot in robots_api:
            nombre = bot.get("name")
            if nombre and patron_nombre.match(nombre) and "loop" not in nombre.lower():
                robots_mapeados.append(
                    {"RobotId": bot.get("id"), "Robot": nombre, "Descripcion": bot.get("description")}
                )
        logger.info(f"Se encontraron y filtraron {len(robots_mapeados)} robots.")
        return robots_mapeados

    async def obtener_detalles_por_deployment_ids(self, deployment_ids: List[str]) -> List[Dict]:
        """Obtiene detalles de deployments procesando los IDs en lotes para evitar timeouts."""
        if not deployment_ids:
            return []
        all_details = []
        logger.info(
            f"Obteniendo detalles de {len(deployment_ids)} deployments en lotes de {self.CONCILIADOR_BATCH_SIZE}..."
        )

        for i in range(0, len(deployment_ids), self.CONCILIADOR_BATCH_SIZE):
            batch_ids = deployment_ids[i : i + self.CONCILIADOR_BATCH_SIZE]
            logger.debug(f"Procesando lote {i // self.CONCILIADOR_BATCH_SIZE + 1} con {len(batch_ids)} IDs.")
            payload = self._crear_filtro_deployment_ids(batch_ids)
            # payload = {
            #     "sort": [{"field": "startDateTime", "direction": "desc"}],
            #     "filter": {
            #         "operator": "or",
            #         "operands": [{"operator": "eq", "field": "deploymentId", "value": dep_id} for dep_id in batch_ids],
            #     },
            # }
            try:
                response_json = await self._realizar_peticion_api("POST", self._ENDPOINT_ACTIVITY_LIST_V3, json=payload)
                all_details.extend(response_json.get("list", []))
            except httpx.ReadTimeout as e:
                logger.error(
                    f"Timeout ({self.api_timeout}s) al procesar un lote de {len(batch_ids)} deployment IDs. Lote omitido. IDs: {batch_ids}."
                )
            except Exception as e:
                logger.error(
                    f"Error al procesar un lote de deployment IDs. Lote omitido. Error: {e}", exc_info=True
                )
        logger.info(f"Se obtuvieron detalles para {len(all_details)} de {len(deployment_ids)} deployments solicitados.")
        return all_details

    async def desplegar_bot_v3(
        self,
        file_id: int,
        user_ids: List[int],
        bot_input: Optional[Dict] = None,
        callback_auth_headers: Optional[Dict[str, str]] = None,
    ) -> Dict:
        logger.info(f"Desplegando bot v3 con FileID: {file_id} en UserIDs: {user_ids}")
        payload = dict(fileId=file_id, runAsUserIds=user_ids)
        if bot_input:
            payload["botInput"] = bot_input

        # Crear la sección callbackInfo solo si se ha definido una URL de callback.
        if self.callback_url_deploy:
            payload["callbackInfo"] = {"url": self.callback_url_deploy}
            logger.debug(f"Callback URL de despliegue configurada: {self.callback_url_deploy}")

            # Si además hay cabeceras, las añadimos al objeto ya creado.
            if callback_auth_headers:
                payload["callbackInfo"]["headers"] = callback_auth_headers
                logger.debug("Cabeceras de autorización añadidas al callback.")

        try:
            logger.debug(f"Payload de despliegue: {payload}")
            response = await self._realizar_peticion_api("POST", self._ENDPOINT_AUTOMATIONS_DEPLOY_V3, json=payload)
            logger.info(f"Bot desplegado exitosamente. DeploymentId: {response.get('deploymentId')}")
            return response
        except Exception as e:
            logger.error(f"Fallo en el despliegue del bot {file_id}: {e}", exc_info=True)
            return {"error": str(e)}

    async def desplegar_bot_v4(
        self,
        file_id: int,
        user_ids: List[int],
        bot_input: Optional[Dict] = None,
        callback_auth_headers: Optional[Dict[str, str]] = None,
    ) -> Dict:
        logger.info(f"Desplegando bot v4 con FileID: {file_id} en UserIDs: {user_ids}")

        unattendedRequest = dict(runAsUserIds=user_ids, deviceUsageType="RUN_ONLY_ON_DEFAULT_DEVICE")
        payload = dict(botId=file_id, unattendedRequest=unattendedRequest)

        if bot_input:
            payload["botInput"] = bot_input

        # Crear la sección callbackInfo solo si se ha definido una URL de callback.
        if self.callback_url_deploy:
            payload["callbackInfo"] = {"url": self.callback_url_deploy}
            logger.debug(f"Callback URL de despliegue configurada: {self.callback_url_deploy}")

            # Si además hay cabeceras, las añadimos al objeto ya creado.
            if callback_auth_headers:
                payload["callbackInfo"]["headers"] = callback_auth_headers
                logger.debug("Cabeceras de autorización añadidas al callback.")

        try:
            logger.debug(f"Payload de despliegue: {payload}")
            response = await self._realizar_peticion_api("POST", self._ENDPOINT_AUTOMATIONS_DEPLOY_V4, json=payload)
            logger.info(f"Bot desplegado exitosamente. DeploymentId: {response.get('deploymentId')}")
            return response
        except Exception as e:
            logger.error(f"Fallo en el despliegue del bot {file_id}: {e}", exc_info=True)
            return {"error": str(e)}

    async def close(self):
        """Cierra la sesión del cliente httpx de forma segura."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Cliente API de A360 cerrado.")
