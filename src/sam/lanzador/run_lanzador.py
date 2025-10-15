import asyncio
import logging
import os
import signal
import sys
from typing import Optional

# Corrección en los imports para la estructura plana de 'common'
from sam.common.a360_client import AutomationAnywhereClient
from sam.common.apigw_client import ApiGatewayClient
from sam.common.config_loader import ConfigLoader
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging
from sam.common.mail_client import EmailAlertClient
from sam.lanzador.service.conciliador import Conciliador
from sam.lanzador.service.desplegador import Desplegador
from sam.lanzador.service.main import LanzadorService
from sam.lanzador.service.sincronizador import Sincronizador

# --- Constantes y Globales ---
SERVICE_NAME = "lanzador"
service_instance: Optional[LanzadorService] = None


# --- Manejo de Cierre Ordenado (Graceful Shutdown) ---
def graceful_shutdown(signum, frame):
    """Maneja las señales de cierre de forma ordenada."""
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if service_instance:
        service_instance.stop()


async def main_async():
    """Función principal asíncrona que gestiona el ciclo de vida completo del servicio."""
    global service_instance

    # --- Configuración inicial ---
    setup_logging(service_name=SERVICE_NAME)
    logging.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}...")

    db_connector = None
    aa_client = None
    gateway_client = None

    try:
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

        logging.info("Creando todas las dependencias del servicio...")
        # Configuración
        lanzador_cfg = ConfigManager.get_lanzador_config()
        aa_cfg = ConfigManager.get_aa_config()
        sync_enabled = os.getenv("LANZADOR_HABILITAR_SYNC", "True").lower() == "true"
        callback_token = ConfigManager.get_callback_server_config().get("token")
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")

        # --- Creación de Dependencias ---
        db_connector = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
        )

        # Se pasan los argumentos de forma explícita y correcta.
        # 'password' es opcional y 'api_key' se pasa como keyword argument.
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_cfg["url_cr"],
            username=aa_cfg["usuario"],
            password=aa_cfg.get("pwd"),  # Opcional, se usa .get()
            api_key=aa_cfg.get("api_key"),  # Se pasa explícitamente
            api_timeout_seconds=aa_cfg.get("api_timeout_seconds"),
            callback_url_deploy=aa_cfg.get("callback_url_deploy"),
        )

        gateway_client = ApiGatewayClient(ConfigManager.get_apigw_config())
        notificador = EmailAlertClient(service_name=SERVICE_NAME)

        # Componentes de Lógica ("Cerebros")
        sincronizador = Sincronizador(db_connector=db_connector, aa_client=aa_client)
        desplegador = Desplegador(
            db_connector=db_connector,
            aa_client=aa_client,
            api_gateway_client=gateway_client,
            lanzador_config=lanzador_cfg,
            callback_token=callback_token,
        )
        conciliador = Conciliador(
            db_connector=db_connector,
            aa_client=aa_client,
            max_intentos_fallidos=lanzador_cfg["conciliador_max_intentos_fallidos"],
        )

        # Orquestador
        service_instance = LanzadorService(
            sincronizador=sincronizador,
            desplegador=desplegador,
            conciliador=conciliador,
            notificador=notificador,
            lanzador_config=lanzador_cfg,
            sync_enabled=sync_enabled,
        )

        # --- Ejecución del Servicio ---
        logging.info("Iniciando el ciclo principal del orquestador...")
        await service_instance.run()

    except KeyboardInterrupt:
        logging.info("Interrupción de teclado detectada (Ctrl+C).")
        if service_instance:
            service_instance.stop()
    except Exception as e:
        logging.critical(f"Error crítico no controlado en el servicio {SERVICE_NAME}: {e}", exc_info=True)
    finally:
        # --- Limpieza Final de Recursos ---
        logging.info("Iniciando limpieza final de recursos...")
        if gateway_client:
            await gateway_client.close()
        if aa_client:
            await aa_client.close()
        if db_connector:
            db_connector.cerrar_conexion_hilo_actual()
        logging.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución y liberado recursos.")


# Este bloque solo se ejecuta si se llama directamente al script,
# pero la ejecución principal viene de __main__.py
if __name__ == "__main__":
    # Configurar manejadores de señales para un cierre limpio
    loop = asyncio.get_event_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, graceful_shutdown)
        loop.add_signal_handler(signal.SIGTERM, graceful_shutdown)
    else:
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        loop.run_until_complete(main_async())
    except asyncio.CancelledError:
        logging.info("El bucle principal de eventos fue cancelado.")
