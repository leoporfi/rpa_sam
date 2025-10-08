import asyncio
import logging
import os
import signal
import sys
from typing import Optional

# --- Importaciones de Módulos Comunes ---
# Asume que common/ ha sido aplanado y los imports son directos
from sam.common.a360_client import AutomationAnywhereClient
from sam.common.apigw_client import ApiGatewayClient
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging
from sam.common.mail_client import EmailAlertClient

# --- Importaciones de Componentes del Servicio ---
from sam.lanzador.service.conciliador import Conciliador
from sam.lanzador.service.desplegador import Desplegador
from sam.lanzador.service.main import LanzadorService
from sam.lanzador.service.sincronizador import Sincronizador

# --- Constantes y Globales ---
SERVICE_NAME = "lanzador"
service_instance: Optional[LanzadorService] = None


def graceful_shutdown(signum, frame):
    """
    Manejador de señales para un cierre ordenado del servicio.
    Establece el evento de parada en la instancia del servicio.
    """
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if service_instance:
        service_instance.stop()
    # El bucle principal en main_async() se encargará de la limpieza final.


async def main_async():
    """
    Función principal asíncrona que gestiona el ciclo de vida completo del servicio.
    Actúa como una "Fábrica" que crea e inyecta todas las dependencias.
    """
    global service_instance

    # Configurar logging al inicio.
    setup_logging(service_name=SERVICE_NAME)
    logging.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}...")

    # Configurar manejadores de señales para un cierre limpio
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, graceful_shutdown, signal.SIGINT, None)
        loop.add_signal_handler(signal.SIGTERM, graceful_shutdown, signal.SIGTERM, None)
    else:
        # Enfoque simplificado para Windows
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

    db_connector = None
    aa_client = None
    gateway_client = None

    try:
        logging.info("Creando todas las dependencias del servicio...")

        # --- 1. Cargar Configuración ---
        lanzador_cfg = ConfigManager.get_lanzador_config()
        sync_enabled = os.getenv("LANZADOR_HABILITAR_SYNC", "True").lower() == "true"
        callback_token = ConfigManager.get_callback_server_config().get("token")
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
        aa_cfg = ConfigManager.get_aa_config()
        apigw_cfg = ConfigManager.get_apigw_config()

        # --- 2. Crear Clientes y Conectores (Dependencias) ---
        db_connector = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
        )
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_cfg["url_cr"],
            username=aa_cfg["usuario"],
            api_key=aa_cfg["api_key"],
            **aa_cfg,
        )
        gateway_client = ApiGatewayClient(apigw_cfg)
        notificador = EmailAlertClient(service_name=SERVICE_NAME)

        # --- 3. Crear Componentes de Lógica ("Cerebros") ---
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

        # --- 4. Crear e Inyectar en el Orquestador ---
        service_instance = LanzadorService(
            sincronizador=sincronizador,
            desplegador=desplegador,
            conciliador=conciliador,
            notificador=notificador,
            lanzador_config=lanzador_cfg,
            sync_enabled=sync_enabled,
        )

        # --- 5. Ejecutar el Servicio ---
        logging.info("Iniciando el ciclo principal del orquestador...")
        await service_instance.run()

    except Exception as e:
        logging.critical(f"Error crítico no controlado en el servicio {SERVICE_NAME}: {e}", exc_info=True)
    finally:
        # --- 6. Limpieza Final de Recursos ---
        logging.info("Iniciando limpieza final de recursos...")
        if gateway_client:
            await gateway_client.close()
        if aa_client:
            await aa_client.close()
        if db_connector:
            db_connector.cerrar_conexion_hilo_actual()
        logging.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución y liberado recursos.")
