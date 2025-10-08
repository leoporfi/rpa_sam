import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Estos módulos son necesarios para el arranque de cada worker
from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector, UpdateStatus
from sam.common.logging_setup import setup_logging

logger = logging.getLogger(__name__)


# --- Modelos de Datos (Pydantic) con descripciones para Swagger ---
class CallbackPayload(BaseModel):
    deployment_id: str = Field(..., alias="deploymentId", description="Identificador único del deployment.")
    status: str = Field(..., description="Estado de la ejecución (ej. COMPLETED, FAILED).")
    device_id: Optional[str] = Field(None, alias="deviceId", description="(Opcional) Identificador del dispositivo.")
    user_id: Optional[str] = Field(None, alias="userId", description="(Opcional) Identificador del usuario.")
    bot_output: Optional[Dict[str, Any]] = Field(None, alias="botOutput", description="(Opcional) Salida del bot.")


class SuccessResponse(BaseModel):
    status: str = "OK"
    message: str


class ErrorResponse(BaseModel):
    status: str = "ERROR"
    message: str


# --- Contenedor de Estado para Dependencias ---
app_state: Dict[str, Any] = {}


# --- Eventos de Ciclo de Vida (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida. Se ejecuta una vez por worker al iniciar y finalizar.
    Aquí se inicializan todos los recursos (config, db, logging).
    """
    # --- ARRANQUE DEL WORKER ---
    # 1. Cargar configuración desde .env para este worker
    ConfigLoader.initialize_service("callback")

    # 2. Configurar el logging para este worker
    setup_logging(service_name="callback")

    # 3. Crear y almacenar la conexión a la base de datos
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

    yield  # La aplicación se ejecuta aquí

    # --- CIERRE DEL WORKER ---
    logger.info("Cerrando recursos del worker...")
    db = app_state.get("db_connector")
    if db:
        db.cerrar_conexion()


# --- App Global con Metadatos para Swagger/OpenAPI ---
app = FastAPI(
    title="SAM Callback Service API",
    version="3.1.0",
    description="""
API para recibir callbacks desde Control Room a través del API Gateway.
**Requiere obligatoriamente una Clave de API (API Key) en el header `X-Authorization`.**

Este endpoint es **idempotente**: si se recibe una notificación para una ejecución que ya se encuentra en un estado final, el servicio responderá con un éxito (`200 OK`) sin realizar cambios.
    """,
    servers=[
        {"url": "http://10.167.181.41:8008", "description": "Servidor de Producción"},
        {"url": "http://10.167.181.42:8008", "description": "Servidor de Desarrollo"},
    ],
    lifespan=lifespan,
)


# --- Inyección de Dependencias de FastAPI ---
def get_db() -> DatabaseConnector:
    """Función de dependencia para obtener el conector de BD en los endpoints."""
    db = app_state.get("db_connector")
    if db is None:
        raise HTTPException(status_code=503, detail="La conexión a la base de datos no está disponible.")
    return db


# --- Lógica de Autenticación ---
async def verify_api_key(
    request: Request, x_authorization: str = Header(..., description="API Key para autenticación")
):
    server_api_key = ConfigManager.get_callback_server_config().get("token")
    if not server_api_key:
        logger.error("CRÍTICO: CALLBACK_TOKEN no está configurado en el servidor.")
        raise HTTPException(status_code=500, detail="Error de configuración de seguridad del servidor.")
    if not hmac.compare_digest(x_authorization, server_api_key):
        logger.warning(f"Intento de acceso no autorizado al callback desde IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="X-Authorization header inválido.")


# --- Endpoints de la API con Documentación Detallada ---
@app.post(
    "/api/callback",
    tags=["Callback"],
    summary="Recibir notificación de callback de A360",
    response_model=SuccessResponse,
    responses={
        200: {
            "description": "Callback procesado correctamente.",
            "content": {
                "application/json": {
                    "examples": {
                        "update_ok": {
                            "summary": "Actualización Exitosa",
                            "value": {"status": "OK", "message": "Callback procesado y estado actualizado."},
                        },
                        "already_processed": {
                            "summary": "Ya Procesado",
                            "value": {"status": "OK", "message": "La ejecución ya estaba en estado final."},
                        },
                    }
                }
            },
        },
        400: {
            "description": "Petición inválida (JSON malformado o campos requeridos faltantes).",
            "model": ErrorResponse,
        },
        401: {
            "description": "Autenticación fallida (X-Authorization header inválido o ausente).",
            "model": ErrorResponse,
        },
        500: {"description": "Error interno del servidor.", "model": ErrorResponse},
    },
    dependencies=[Depends(verify_api_key)],
)
async def handle_callback(payload: CallbackPayload, db: DatabaseConnector = Depends(get_db)):
    logger.info(f"Callback recibido para DeploymentId: {payload.deployment_id} con estado: {payload.status}")

    try:
        update_result = db.actualizar_ejecucion_desde_callback(
            deployment_id=payload.deployment_id,
            estado_callback=payload.status,
            callback_payload_str=payload.model_dump_json(),
        )

        if update_result == UpdateStatus.UPDATED:
            return SuccessResponse(message="Callback procesado y estado actualizado.")
        elif update_result == UpdateStatus.ALREADY_PROCESSED:
            return SuccessResponse(message="La ejecución ya estaba en estado final.")
        elif update_result == UpdateStatus.NOT_FOUND:
            logger.warning(f"DeploymentId '{payload.deployment_id}' no fue encontrado en la base de datos.")
            return SuccessResponse(message=f"DeploymentId '{payload.deployment_id}' no encontrado.")
    except Exception as e:
        logger.error(f"Error de base de datos al procesar callback para {payload.deployment_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al actualizar el estado en la base de datos.")


@app.get("/health", tags=["Monitoring"], summary="Verificar estado del servicio", response_model=SuccessResponse)
async def health_check():
    return SuccessResponse(message="Servicio de Callback activo y saludable.")
