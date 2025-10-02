# src/web/api_client.py
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from backend.schemas import Robot

from .utils.exceptions import APIException, ValidationException
from .utils.validation import validate_robot_data


# Un cliente simple para comunicarse con nuestra propia API de FastAPI
class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        # Usamos un cliente asíncrono que se reutilizará
        self._client = None  # httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def __aenter__(self):
        """Context manager para uso con async with"""
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0, headers={"Content-Type": "application/json"})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cierra el cliente al salir del context manager"""
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        """Obtiene el cliente HTTP, creándolo si es necesario"""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0, headers={"Content-Type": "application/json"})
        return self._client

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None, retries: int = 3) -> Any:
        """
        Realiza una petición HTTP con reintentos y manejo de errores
        """
        client = self._get_client()

        for attempt in range(retries):
            try:
                response = await client.request(method=method, url=endpoint, params=params, json=json_data)

                # Verificar código de estado
                if response.status_code >= 400:
                    error_detail = "Error desconocido"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", str(error_data))
                    except:
                        error_detail = response.text or f"Error HTTP {response.status_code}"

                    raise APIException(message=f"Error en la API: {error_detail}", status_code=response.status_code)

                # Intentar parsear JSON, devolver texto si falla
                try:
                    return response.json()
                except:
                    return response.text

            except httpx.RequestError as e:
                if attempt == retries - 1:  # Último intento
                    raise APIException(f"Error de conexión: {str(e)}")

                # Esperar antes del siguiente intento (exponential backoff)
                await asyncio.sleep(2**attempt)

            except APIException:
                # Re-lanzar errores de API sin reintentar
                raise

    # MÉTODOS PARA ROBOTS
    # ====================
    async def get_robots(self, params: Optional[Dict] = None) -> Dict:
        """
        Obtiene la lista de robots con filtros y parámetros de ordenación opcionales.
        Retorna: {"robots": List[Robot], "total_count": int, ...}
        """
        try:
            # Ahora simplemente pasamos el diccionario de parámetros directamente.
            data = await self._request("GET", "/api/robots", params=params)
            if not isinstance(data, dict):
                # Si la respuesta no es un diccionario, es un error inesperado del backend.
                # Lanza una excepción clara.
                error_preview = str(data)[:200]  # Muestra los primeros 200 caracteres del error
                raise APIException(f"La respuesta del servidor no es un JSON válido. Contenido: '{error_preview}...'")

            if isinstance(data, list):
                return {"robots": data, "total_count": len(data)}

            return {
                "robots": data.get("robots", []),
                "total_count": data.get("total_count", 0),
            }
        except Exception as e:
            raise APIException(f"Error al obtener robots: {str(e)}")

    async def get_robot(self, robot_id: int) -> Robot:
        """Obtiene un robot específico por ID"""
        try:
            return await self._request("GET", f"/api/robots/{robot_id}")
        except Exception as e:
            raise APIException(f"Error al obtener robot {robot_id}: {str(e)}")

    async def create_robot(self, robot_data: Dict) -> Robot:
        """Crea un nuevo robot"""
        # Validar datos antes de enviar
        validation_result = validate_robot_data(robot_data)

        if not validation_result.is_valid:
            raise ValidationException("Datos inválidos", validation_result.errors)

        try:
            return await self._request("POST", "/api/robots", json_data=robot_data)
        except Exception as e:
            raise APIException(f"Error al crear robot: {str(e)}")

    async def update_robot(self, robot_id: int, robot_data: Dict) -> Robot:
        """Actualiza un robot existente"""
        # Validar datos antes de enviar
        validation_result = validate_robot_data(robot_data, is_update=True)
        if not validation_result.is_valid:
            raise ValidationException("Datos inválidos", validation_result.errors)

        try:
            return await self._request("PUT", f"/api/robots/{robot_id}", json_data=robot_data)
        except Exception as e:
            raise APIException(f"Error al actualizar robot {robot_id}: {str(e)}")

    async def update_robot_status(self, robot_id: int, status_data: Dict[str, bool]) -> Dict:
        """Actualiza el estado de un robot (Activo/Online)"""
        try:
            return await self._request("PATCH", f"/api/robots/{robot_id}", json_data=status_data)
        except Exception as e:
            raise APIException(f"Error al actualizar estado del robot {robot_id}: {str(e)}")

    async def delete_robot(self, robot_id: int) -> Dict:
        """Elimina un robot"""
        try:
            return await self._request("DELETE", f"/api/robots/{robot_id}")
        except Exception as e:
            raise APIException(f"Error al eliminar robot {robot_id}: {str(e)}")

    # MÉTODOS PARA ASIGNACIONES
    # =========================
    async def get_robot_assignments(self, robot_id: int) -> List[Dict]:
        """Obtiene las asignaciones de un robot"""
        try:
            return await self._request("GET", f"/api/robots/{robot_id}/asignaciones")
        except Exception as e:
            raise APIException(f"Error al obtener asignaciones del robot {robot_id}: {str(e)}")

    async def get_available_teams(self, robot_id: int) -> List[Dict]:
        """Obtiene los equipos disponibles para asignar a un robot"""
        try:
            return await self._request("GET", f"/api/equipos/disponibles/{robot_id}")
        except Exception as e:
            raise APIException(f"Error al obtener equipos disponibles: {str(e)}")

    async def update_robot_assignments(self, robot_id: int, assign_team_ids: List[int], unassign_team_ids: List[int]) -> Dict:
        """Actualiza las asignaciones de un robot"""
        try:
            data = {"assign_team_ids": assign_team_ids, "unassign_team_ids": unassign_team_ids}
            return await self._request("POST", f"/api/robots/{robot_id}/asignaciones", json_data=data)
        except Exception as e:
            raise APIException(f"Error al actualizar asignaciones del robot {robot_id}: {str(e)}")

    # MÉTODOS PARA PROGRAMACIONES
    # ===========================
    async def get_robot_schedules(self, robot_id: int) -> List[Dict]:
        """Obtiene las programaciones de un robot"""
        try:
            return await self._request("GET", f"/api/robots/{robot_id}/programaciones")
        except Exception as e:
            raise APIException(f"Error al obtener programaciones del robot {robot_id}: {str(e)}")

    async def create_schedule(self, schedule_data: Dict) -> Dict:
        """Crea una nueva programación"""
        try:
            return await self._request("POST", "/api/programaciones", json_data=schedule_data)
        except Exception as e:
            raise APIException(f"Error al crear programación: {str(e)}")

    async def update_schedule(self, schedule_id: int, schedule_data: Dict) -> Dict:
        """Actualiza una programación existente"""
        try:
            return await self._request("PUT", f"/api/programaciones/{schedule_id}", json_data=schedule_data)
        except Exception as e:
            raise APIException(f"Error al actualizar programación {schedule_id}: {str(e)}")

    async def delete_schedule(self, robot_id: int, schedule_id: int) -> Dict:
        """Elimina una programación"""
        try:
            return await self._request("DELETE", f"/api/robots/{robot_id}/programaciones/{schedule_id}")
        except Exception as e:
            raise APIException(f"Error al eliminar programación {schedule_id}: {str(e)}")

    # MÉTODOS PARA POOL
    # =========================

    async def get_pools(self) -> List[Dict]:
        """Obtiene la lista de todos los pools de recursos."""
        return await self._request("GET", "/api/pools")

    async def create_pool(self, pool_data: Dict) -> Dict:
        """Crea un nuevo pool de recursos."""
        return await self._request("POST", "/api/pools", json_data=pool_data)

    async def update_pool(self, pool_id: int, pool_data: Dict) -> Dict:
        """Actualiza un pool de recursos existente."""
        return await self._request("PUT", f"/api/pools/{pool_id}", json_data=pool_data)

    async def delete_pool(self, pool_id: int) -> None:
        """Elimina un pool de recursos. No devuelve contenido en caso de éxito."""
        await self._request("DELETE", f"/api/pools/{pool_id}")

    async def get_pool_assignments(self, pool_id: int) -> Dict:
        """Obtiene los recursos asignados y disponibles para un pool."""
        return await self._request("GET", f"/api/pools/{pool_id}/asignaciones")

    async def update_pool_assignments(self, pool_id: int, robot_ids: List[int], team_ids: List[int]) -> Dict:
        """Actualiza las asignaciones de un pool."""
        payload = {"robot_ids": robot_ids, "team_ids": team_ids}
        return await self._request("PUT", f"/api/pools/{pool_id}/asignaciones", json_data=payload)

    # MÉTODOS UTILITARIOS
    # =========================
    async def health_check(self) -> Dict:
        """Verifica el estado de la API"""
        try:
            return await self._request("GET", "/health/")
        except Exception as e:
            raise APIException(f"Error en health check: {str(e)}")

    async def trigger_sync(self) -> Dict:
        """Dispara el proceso de sincronización en el backend."""
        try:
            return await self._request("POST", "/api/sync")
        except Exception as e:
            raise APIException(f"Error al iniciar la sincronización: {str(e)}")

    async def close(self):
        """Cierra el cliente HTTP"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Instancia Singleton del cliente
_api_client_instance = None


def get_api_client() -> ApiClient:
    global _api_client_instance
    if _api_client_instance is None:
        _api_client_instance = ApiClient()
    return _api_client_instance
