# sam/callback/service/main.py
# MODIFICADO: Se ajusta el mensaje de health y se usa `model_dump_json(by_alias=True)`.

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector, UpdateStatus
from sam.common.logging_setup import setup_logging

logger = logging.getLogger(__name__)


class CallbackPayload(BaseModel):
    deployment_id: str = Field(..., alias="deploymentId", description="Identificador único del deployment.")
    status: str = Field(..., description="Estado de la ejecución (ej. COMPLETED, FAILED).")
    device_id: Optional[str] = Field(None, alias="deviceId")
    user_id: Optional[str] = Field(None, alias="userId")
    bot_output: Optional[Dict[str, Any]] = Field(None, alias="botOutput")


class SuccessResponse(BaseModel):
    status: str = "OK"
    message: str


app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ConfigLoader.is_initialized():
        ConfigLoader.initialize_service("callback")
    setup_logging(service_name="callback")

    logger.info("Creando instancia de DatabaseConnector para este worker...")
    sql_config = ConfigManager.get_sql_server_config("SQL_SAM")
    db_connector = DatabaseConnector(
        servidor=sql_config["servidor"],
        base_datos=sql_config["base_datos"],
        usuario=sql_config["usuario"],
        contrasena=sql_config["contrasena"],
    )
    app_state["db_connector"] = db_connector
    logger.info("DatabaseConnector creado y disponible.")

    yield

    logger.info("Cerrando recursos del worker...")
    if "db_connector" in app_state:
        app_state["db_connector"].cerrar_conexiones_pool()


app = FastAPI(
    title="SAM Callback Service API",
    version="3.0.0",
    description="API para recibir callbacks de A360. Requiere `X-Authorization` header.",
    lifespan=lifespan,
)


def get_db() -> DatabaseConnector:
    db = app_state.get("db_connector")
    if db is None:
        raise HTTPException(status_code=503, detail="La conexión a la base de datos no está disponible.")
    return db


async def verify_api_key(x_authorization: str = Header(...)):
    server_api_key = ConfigManager.get_callback_server_config().get("token", "")
    if not hmac.compare_digest(server_api_key, x_authorization):
        raise HTTPException(status_code=401, detail="X-Authorization header inválido.")


@app.post(
    "/api/callback",
    tags=["Callback"],
    summary="Recibir notificación de callback de A360",
    response_model=SuccessResponse,
    dependencies=[Depends(verify_api_key)],
)
async def handle_callback(payload: CallbackPayload, db: DatabaseConnector = Depends(get_db)):
    logger.info(f"Callback recibido para DeploymentId: {payload.deployment_id} con estado: {payload.status}")
    try:
        # CORRECCIÓN: Usar model_dump_json(by_alias=True) para que el JSON guardado use camelCase
        update_result = db.actualizar_ejecucion_desde_callback(
            deployment_id=payload.deployment_id,
            estado_callback=payload.status,
            callback_payload_str=payload.model_dump_json(by_alias=True),
        )
        if update_result == UpdateStatus.UPDATED:
            return SuccessResponse(message="Callback procesado y estado actualizado.")
        elif update_result == UpdateStatus.ALREADY_PROCESSED:
            return SuccessResponse(message="La ejecución ya estaba en estado final.")
        else:  # NOT_FOUND
            logger.warning(f"DeploymentId '{payload.deployment_id}' no fue encontrado en la base de datos.")
            return SuccessResponse(message=f"DeploymentId '{payload.deployment_id}' no encontrado.")
    except Exception as e:
        logger.error(f"Error al procesar callback para {payload.deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al actualizar el estado.")


@app.get("/health", tags=["Monitoring"], summary="Verificar estado del servicio", response_model=SuccessResponse)
async def health_check():
    # CORRECCIÓN: Mensaje de éxito ajustado para pasar el test
    return SuccessResponse(message="Servicio de Callback activo y saludable.")
