import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector, UpdateStatus
from sam.common.logging_setup import setup_logging

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


# --- Contenedor de Dependencias ---
# Usamos un simple diccionario para mantener las dependencias que se crearán al inicio.
app_state: Dict[str, Any] = {}


# --- Eventos de Ciclo de Vida (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación. Se ejecuta una vez por worker.
    Aquí se inicializan todos los recursos (config, db, logging).
    """
    # --- ARRANQUE DEL WORKER ---
    # 1. Cargar la configuración desde .env (cada worker lo necesita)
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
    # Aquí iría la lógica de limpieza si fuera necesaria, ej: db_connector.close()


# --- App Global con Lifespan ---
app = FastAPI(
    title="SAM Callback Service API",
    version="3.1.0",
    description="API para recibir notificaciones de estado de ejecuciones de A360.",
    lifespan=lifespan,
)


# --- Inyección de Dependencias de FastAPI ---
def get_db() -> DatabaseConnector:
    """Función de dependencia de FastAPI para obtener el conector de BD."""
    db = app_state.get("db_connector")
    if db is None:
        # Esto solo debería ocurrir si el lifespan falla catastróficamente
        raise HTTPException(
            status_code=503,
            detail="La conexión a la base de datos no está disponible.",
        )
    return db


# --- Manejadores de Errores ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"status": "ERROR", "message": f"Payload inválido: {exc.errors()}"},
    )


# --- Lógica de Autenticación ---
def verify_api_key(x_authorization: str = Header(..., description="API Key para autenticación")):
    callback_config = ConfigManager.get_callback_server_config()
    token_esperado = callback_config.get("token")
    if not token_esperado:
        logger.error("CRÍTICO: El token de callback (CALLBACK_TOKEN) no está configurado en el servidor.")
        raise HTTPException(status_code=500, detail="El servidor no tiene configurado un token de seguridad.")
    if not hmac.compare_digest(x_authorization, token_esperado):
        logger.warning(f"Intento de acceso no autorizado al callback desde IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="X-Authorization header inválido.")


# --- Endpoints de la API ---
@app.post(
    "/api/callback",
    tags=["Callback"],
    response_model=SuccessResponse,
    dependencies=[Depends(verify_api_key)],
)
async def handle_callback(payload: CallbackPayload, request: Request, db: DatabaseConnector = Depends(get_db)):
    raw_payload = await request.body()
    payload_str = raw_payload.decode("utf-8")
    logger.info(f"Callback recibido para DeploymentId: {payload.deployment_id} con estado: {payload.status}")

    try:
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
            # Aún respondemos con 200 OK porque el request fue válido, aunque no se encontró el ID.
            logger.warning(f"DeploymentId '{payload.deployment_id}' no fue encontrado en la base de datos.")
            return SuccessResponse(message=f"DeploymentId '{payload.deployment_id}' no encontrado.")

    except Exception as e:
        logger.error(f"Error de base de datos al procesar callback para {payload.deployment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al actualizar el estado en la base de datos.",
        )


@app.get("/health", tags=["Monitoring"], response_model=SuccessResponse)
async def health_check():
    return SuccessResponse(message="Servicio de Callback activo y saludable.")
