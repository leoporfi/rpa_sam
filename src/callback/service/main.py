# src/callback/service/main.py
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from src.common.database.sql_client import DatabaseConnector, UpdateStatus
from src.common.utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Se crea la instancia de FastAPI a nivel de módulo para que Uvicorn pueda importarla.
app = FastAPI(
    title="SAM Callback Service API",
    version="3.0.0",
    description="""
        API para recibir callbacks desde Control Room a través del API Gateway.
        **Requiere obligatoriamente una Clave de API en el header `X-Authorization`.**
        """,
    servers=[
        {"url": "http://10.167.181.41:8008", "description": "Servidor de Producción"},
        {"url": "http://10.167.181.42:8008", "description": "Servidor de Desarrollo"},
    ],
)

# Se usará para "pasar" la dependencia a la app.
_db_connector: Optional[DatabaseConnector] = None

# --- Definición de Seguridad  ---
api_key_scheme = APIKeyHeader(name="X-Authorization", auto_error=False, description="Clave de API para la autenticación del callback.")


# --- Modelos de Datos (Pydantic) ---
class CallbackPayload(BaseModel):
    deployment_id: str = Field(..., alias="deploymentId", description="Identificador único del deployment.")
    status: str = Field(..., description="Estado de la ejecución (ej. COMPLETED, FAILED).")
    device_id: Optional[str] = Field(None, alias="deviceId", description="(Opcional) Identificador del dispositivo que ejecutó el bot.")
    user_id: Optional[str] = Field(None, alias="userId", description="(Opcional) Identificador del usuario asociado a la ejecución.")
    bot_output: Optional[Dict[str, Any]] = Field(None, alias="botOutput", description="(Opcional) Salida generada por el bot.")


class SuccessResponse(BaseModel):
    """
    Define el formato de respuesta JSON estándar para toda la API.
    """

    status: str = "OK"
    message: str


class ErrorResponse(BaseModel):
    status: str = "ERROR"
    message: str


# --- Función Fábrica para la App FastAPI ---
def create_app(db_connector: DatabaseConnector) -> FastAPI:
    """
    Configura la instancia global de la aplicación FastAPI, inyectando las dependencias.
    """
    global _db_connector
    _db_connector = db_connector

    cb_config = ConfigManager.get_callback_server_config()

    # --- Manejadores de Excepciones ---
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        Captura las excepciones HTTP y formatea la respuesta para que coincida con el formato estándar.
        """
        return JSONResponse(status_code=exc.status_code, content={"status": "ERROR", "message": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Captura los errores de validación de Pydantic y los formatea.
        """
        error_message = exc.errors()[0]["msg"] if exc.errors() else "Error de validación"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "ERROR", "message": f"Petición inválida: {error_message}"},
        )

    # --- Dependencias de FastAPI ---
    def get_db() -> DatabaseConnector:
        if not _db_connector:
            raise HTTPException(status_code=503, detail="Conexión a BD no disponible.")
        return _db_connector

    async def verify_api_key(x_authorization: Optional[str] = Header(None, alias="X-Authorization")):
        auth_mode = cb_config.get("auth_mode", "strict")
        server_api_key = cb_config.get("token")

        if auth_mode == "optional" and not x_authorization:
            return

        if not server_api_key:
            logger.error("Configuración del servidor incompleta: CALLBACK_TOKEN no está definido.")
            raise HTTPException(status_code=500, detail="Error de configuración del servidor.")

        if not x_authorization or not hmac.compare_digest(server_api_key, x_authorization):
            logger.warning("Intento de acceso con API Key inválida.")
            raise HTTPException(status_code=401, detail="Clave de API inválida o ausente.")

    # --- Eventos de Ciclo de Vida ---
    @app.on_event("shutdown")
    def shutdown_event():
        logger.info("Cerrando la conexión de la base de datos al detener el servicio.")
        db_connector.cerrar_conexion()

    # --- Endpoints ---
    endpoint_path = cb_config.get("endpoint_path", "/api/callback").strip("/")

    @app.post(
        f"/{endpoint_path}",
        tags=["Callback"],
        summary="Recibir notificación de callback de A360",
        response_model=SuccessResponse,
        responses={
            200: {"description": "Callback procesado correctamente.", "model": SuccessResponse},
            400: {"description": "Petición inválida (JSON malformado o faltan campos requeridos).", "model": ErrorResponse},
            401: {
                "description": "Autenticación Fallida. La Clave de API en 'X-Authorization' es inválida o no fue proporcionada.",
                "model": ErrorResponse,
            },
            500: {"description": "Error interno del servidor.", "model": ErrorResponse},
        },
        dependencies=[Depends(verify_api_key)],
    )
    async def handle_callback(payload: CallbackPayload, request: Request, db: DatabaseConnector = Depends(get_db)):
        """
        Procesa el callback de A360. Es idempotente: maneja correctamente los callbacks duplicados.
        """
        raw_payload = await request.body()
        payload_str = raw_payload.decode("utf-8")
        logger.info(f"Callback recibido para DeploymentId: {payload.deployment_id}")

        update_result = db.actualizar_ejecucion_desde_callback(
            deployment_id=payload.deployment_id,
            estado_callback=payload.status,
            callback_payload_str=payload_str,
        )
        try:
            if update_result == UpdateStatus.UPDATED:
                return SuccessResponse(message="Callback procesado y estado actualizado.")
            elif update_result == UpdateStatus.ALREADY_PROCESSED:
                return SuccessResponse(message="La ejecución ya estaba en un estado final. No se realizaron cambios.")
            elif update_result == UpdateStatus.NOT_FOUND:
                return SuccessResponse(message=f"DeploymentId '{payload.deployment_id}' no encontrado.")
            else:  # update_result == UpdateStatus.ERROR
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Ocurrió un error al intentar actualizar el estado en la base de datos.",
                )
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.error(f"Error inesperado no controlado en el endpoint de callback: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

    @app.get("/health", tags=["Monitoring"], summary="Verifica el estado del servicio", response_model=SuccessResponse)
    async def health_check():
        """
        Endpoint simple para verificar que el servicio está en línea.
        """
        return SuccessResponse(message="Servicio de Callback activo.")

    return app
