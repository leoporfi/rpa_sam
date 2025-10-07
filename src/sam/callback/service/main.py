# sam/callback/service/main.py
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector, UpdateStatus

logger = logging.getLogger(__name__)


# --- Modelos de Datos (Pydantic) ---
class CallbackPayload(BaseModel):
    deployment_id: str = Field(..., alias="deploymentId")
    status: str = Field(...)
    device_id: Optional[str] = Field(None, alias="deviceId")
    user_id: Optional[str] = Field(None, alias="userId")
    bot_output: Optional[Dict[str, Any]] = Field(None, alias="botOutput")


class SuccessResponse(BaseModel):
    status: str = "OK"
    message: str


class ErrorResponse(BaseModel):
    status: str = "ERROR"
    message: str


# --- Función Fábrica para la App FastAPI ---
def create_app(db_connector: DatabaseConnector) -> FastAPI:
    """
    Crea y configura una instancia de FastAPI con todas las dependencias.
    """
    app = FastAPI(
        title="SAM Callback Service API",
        version="3.0.0",
        description="API para recibir callbacks desde Control Room.",
        servers=[
            {"url": "http://10.167.181.41:8008", "description": "Producción"},
            {"url": "http://10.167.181.42:8008", "description": "Desarrollo"},
        ],
    )

    cb_config = ConfigManager.get_callback_server_config()

    # --- Manejadores de Excepciones ---
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"status": "ERROR", "message": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        error_message = exc.errors()[0]["msg"] if exc.errors() else "Error de validación"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "ERROR", "message": f"Petición inválida: {error_message}"},
        )

    # --- Dependencias ---
    def get_db() -> DatabaseConnector:
        return db_connector

    async def verify_api_key(x_authorization: Optional[str] = Header(None, alias="X-Authorization")):
        auth_mode = cb_config.get("auth_mode", "strict")
        server_api_key = cb_config.get("token")

        if auth_mode == "optional" and not x_authorization:
            return

        if not server_api_key:
            logger.error("CALLBACK_TOKEN no está definido.")
            raise HTTPException(status_code=500, detail="Error de configuración del servidor.")

        if not x_authorization or not hmac.compare_digest(server_api_key, x_authorization):
            logger.warning("Intento de acceso con API Key inválida.")
            raise HTTPException(status_code=401, detail="Clave de API inválida o ausente.")

    # --- Eventos de Ciclo de Vida ---
    @app.on_event("shutdown")
    def shutdown_event():
        logger.info("Cerrando la conexión de la base de datos.")
        db_connector.cerrar_conexion()

    # --- Endpoints ---
    endpoint_path = cb_config.get("endpoint_path", "/api/callback").strip("/")

    @app.post(
        f"/{endpoint_path}",
        tags=["Callback"],
        response_model=SuccessResponse,
        dependencies=[Depends(verify_api_key)],
    )
    async def handle_callback(payload: CallbackPayload, request: Request, db: DatabaseConnector = Depends(get_db)):
        raw_payload = await request.body()
        payload_str = raw_payload.decode("utf-8")
        logger.info(f"Callback recibido para DeploymentId: {payload.deployment_id}")

        update_result = db.actualizar_ejecucion_desde_callback(
            deployment_id=payload.deployment_id,
            estado_callback=payload.status,
            callback_payload_str=payload_str,
        )

        if update_result == UpdateStatus.UPDATED:
            return SuccessResponse(message="Callback procesado y estado actualizado.")
        elif update_result == UpdateStatus.ALREADY_PROCESSED:
            return SuccessResponse(message="La ejecución ya estaba en un estado final.")
        elif update_result == UpdateStatus.NOT_FOUND:
            return SuccessResponse(message=f"DeploymentId '{payload.deployment_id}' no encontrado.")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar el estado en la base de datos.",
            )

    @app.get("/health", tags=["Monitoring"], response_model=SuccessResponse)
    async def health_check():
        return SuccessResponse(message="Servicio de Callback activo.")

    return app
