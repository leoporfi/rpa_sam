# sam/web/api_client.py
import asyncio
from typing import Any, Dict, List, Optional

import httpx

from ..backend.schemas import Robot
from .utils.exceptions import APIException, ValidationException
from .utils.validation import validate_robot_data


# Un cliente simple para comunicarse con nuestra propia API de FastAPI
class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self._client = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url, timeout=30.0, headers={"Content-Type": "application/json"}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=30.0, headers={"Content-Type": "application/json"}
            )
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        retries: int = 3,
    ) -> Any:
        client = self._get_client()
        for attempt in range(retries):
            try:
                response = await client.request(method=method, url=endpoint, params=params, json=json_data)
                if response.status_code >= 400:
                    error_detail = "Error desconocido"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", str(error_data))
                    except Exception:
                        error_detail = response.text or f"Error HTTP {response.status_code}"
                    raise APIException(message=f"Error en la API: {error_detail}", status_code=response.status_code)
                try:
                    return response.json()
                except Exception:
                    return response.text
            except httpx.RequestError as e:
                if attempt == retries - 1:
                    raise APIException(f"Error de conexión: {str(e)}")
                await asyncio.sleep(2**attempt)
            except APIException:
                raise

    # MÉTODOS PARA ROBOTS
    async def get_robots(self, params: Optional[Dict] = None) -> Dict:
        try:
            data = await self._request("GET", "/api/robots", params=params)
            if not isinstance(data, dict):
                error_preview = str(data)[:200]
                raise APIException(f"La respuesta del servidor no es un JSON válido. Contenido: '{error_preview}...'")
            return {"robots": data.get("robots", []), "total_count": data.get("total_count", 0)}
        except Exception as e:
            raise APIException(f"Error al obtener robots: {str(e)}")

    async def create_robot(self, robot_data: Dict) -> Robot:
        validation_result = validate_robot_data(robot_data)
        if not validation_result.is_valid:
            raise ValidationException("Datos inválidos", validation_result.errors)
        return await self._request("POST", "/api/robots", json_data=robot_data)

    async def update_robot(self, robot_id: int, robot_data: Dict) -> Robot:
        validation_result = validate_robot_data(robot_data, is_update=True)
        if not validation_result.is_valid:
            raise ValidationException("Datos inválidos", validation_result.errors)
        return await self._request("PUT", f"/api/robots/{robot_id}", json_data=robot_data)

    async def update_robot_status(self, robot_id: int, status_data: Dict[str, bool]) -> Dict:
        return await self._request("PATCH", f"/api/robots/{robot_id}", json_data=status_data)

    async def delete_robot(self, robot_id: int) -> Dict:
        return await self._request("DELETE", f"/api/robots/{robot_id}")

    # MÉTODOS PARA ASIGNACIONES
    async def get_robot_assignments(self, robot_id: int) -> List[Dict]:
        return await self._request("GET", f"/api/robots/{robot_id}/asignaciones")

    async def get_available_devices(self, robot_id: int) -> List[Dict]:
        return await self._request("GET", f"/api/equipos/disponibles/{robot_id}")

    async def update_robot_assignments(
        self, robot_id: int, assign_ids: List[int], unassign_ids: List[int]
    ) -> Dict:
        # RFR-34: Se usan los nombres de campo en español que el backend espera.
        data = {"asignar_equipo_ids": assign_ids, "desasignar_equipo_ids": unassign_ids}
        return await self._request("POST", f"/api/robots/{robot_id}/asignaciones", json_data=data)

    # MÉTODOS PARA PROGRAMACIONES (SCHEDULES)
    async def get_all_schedules(self) -> List[Dict]:
        return await self._request("GET", "/api/schedules")

    async def get_robot_schedules(self, robot_id: int) -> List[Dict]:
        return await self._request("GET", f"/api/schedules/robot/{robot_id}")

    async def create_schedule(self, schedule_data: Dict) -> Dict:
        return await self._request("POST", "/api/schedules", json_data=schedule_data)

    async def update_schedule(self, schedule_id: int, schedule_data: Dict) -> Dict:
        return await self._request("PUT", f"/api/schedules/{schedule_id}", json_data=schedule_data)

    async def delete_schedule(self, schedule_id: int, robot_id: int) -> Dict:
        return await self._request("DELETE", f"/api/schedules/{schedule_id}/robot/{robot_id}")

    # MÉTODOS PARA POOLS
    async def get_pools(self) -> List[Dict]:
        return await self._request("GET", "/api/pools")

    async def create_pool(self, pool_data: Dict) -> Dict:
        return await self._request("POST", "/api/pools", json_data=pool_data)

    async def update_pool(self, pool_id: int, pool_data: Dict) -> Dict:
        return await self._request("PUT", f"/api/pools/{pool_id}", json_data=pool_data)

    async def delete_pool(self, pool_id: int) -> None:
        await self._request("DELETE", f"/api/pools/{pool_id}")

    async def get_pool_assignments(self, pool_id: int) -> Dict:
        return await self._request("GET", f"/api/pools/{pool_id}/asignaciones")

    async def update_pool_assignments(self, pool_id: int, robot_ids: List[int], equipo_ids: List[int]) -> Dict:
        # RFR-34: Se estandariza el nombre del parámetro y del campo a 'equipo_ids'.
        payload = {"robot_ids": robot_ids, "equipo_ids": equipo_ids}
        return await self._request("PUT", f"/api/pools/{pool_id}/asignaciones", json_data=payload)

    # MÉTODOS UTILITARIOS
    async def trigger_sync(self) -> Dict:
        return await self._request("POST", "/api/sync")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


_api_client_instance = None


def get_api_client() -> ApiClient:
    global _api_client_instance
    if _api_client_instance is None:
        _api_client_instance = ApiClient()
    return _api_client_instance

