import asyncio
import logging
import os
import signal
import sys
from typing import Optional

# --- 1. Inicialización de Configuración y Path ---
# Esto debe ser lo primero que se ejecute para que el resto de importaciones funcionen.
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.common.utils.config_loader import ConfigLoader

    ConfigLoader.initialize_service("lanzador", __file__)
except Exception as e:
    # Usamos print porque el logger aún no está configurado
    print(f"FATAL: Error crítico durante la inicialización de la configuración: {e}", file=sys.stderr)
    sys.exit(1)

# --- 2. Importaciones del Proyecto (Ahora seguras) ---
from src.common.clients.aa_client import AutomationAnywhereClient
from src.common.clients.api_gateway_client import ApiGatewayClient
from src.common.database.sql_client import DatabaseConnector
from src.common.utils.config_manager import ConfigManager
from src.common.utils.logging_setup import setup_logging
from src.common.utils.mail_client import EmailAlertClient
from src.lanzador.service.conciliador import Conciliador
from src.lanzador.service.desplegador import Desplegador
from src.lanzador.service.main import LanzadorService
from src.lanzador.service.sincronizador import Sincronizador

# --- 3. Constantes y Globales ---
SERVICE_NAME = "lanzador"
service_instance: Optional[LanzadorService] = None


# --- 4. Manejo de Cierre Ordenado (Graceful Shutdown) ---
def graceful_shutdown(signum, frame):
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if service_instance:
        service_instance.stop()
    # El bucle principal en main() se encargará de la limpieza final.


async def main_async():
    """Función principal asíncrona que gestiona el ciclo de vida completo del servicio."""
    global service_instance

    # --- 5. Creación de Dependencias (Inyección de Dependencias) ---
    # Este script es ahora el "ensamblador" o "fábrica" del servicio.
    db_connector = None
    aa_client = None
    gateway_client = None

    try:
        logging.info("Creando todas las dependencias del servicio...")
        # Configuración
        lanzador_cfg = ConfigManager.get_lanzador_config()
        sync_enabled = os.getenv("LANZADOR_HABILITAR_SYNC", "True").lower() == "true"
        callback_token = ConfigManager.get_callback_server_config().get("token")

        # Clientes y Conectores
        # --- INICIO DE LA CORRECCIÓN ---
        # Obtenemos el diccionario completo de configuración
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
        # Pero pasamos solo los argumentos que el constructor espera
        db_connector = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
        )
        # --- FIN DE LA CORRECCIÓN ---
        # --- INICIO DE LA CORRECCIÓN ---
        # Obtenemos la configuración de AA
        aa_cfg = ConfigManager.get_aa_config()
        # Mapeamos manualmente las claves de config a los parámetros del constructor
        # y pasamos el resto como kwargs.
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_cfg["url_cr"],
            username=aa_cfg["usuario"],
            password=aa_cfg["api_key"],  # El API Key actúa como la contraseña para la autenticación
            **aa_cfg,  # Pasamos el resto de la config (timeout, etc.)
        )
        # --- FIN DE LA CORRECCIÓN ---
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
            db_connector=db_connector, aa_client=aa_client, max_intentos_fallidos=lanzador_cfg["conciliador_max_intentos_fallidos"]
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

        # --- 6. Ejecución del Servicio ---
        logging.info("Iniciando el ciclo principal del orquestador...")
        await service_instance.run()

    except Exception as e:
        logging.critical(f"Error crítico no controlado en el servicio {SERVICE_NAME}: {e}", exc_info=True)
    finally:
        # --- 7. Limpieza Final de Recursos ---
        logging.info("Iniciando limpieza final de recursos...")
        if gateway_client:
            await gateway_client.close()
        if aa_client:
            await aa_client.close()
        if db_connector:
            db_connector.cerrar_conexion_hilo_actual()
        logging.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución y liberado recursos.")


if __name__ == "__main__":
    # Configurar logging ANTES que nada
    setup_logging(service_name=SERVICE_NAME)
    logging.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}...")

    # Configurar manejadores de señales para un cierre limpio
    if sys.platform == "win32":
        # Windows no soporta add_signal_handler de asyncio.
        # Usamos signal.signal, que es suficiente para capturar Ctrl+C.
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)
        loop = asyncio.get_event_loop()
    else:
        # Lógica original para sistemas Unix-like (Linux, macOS)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, graceful_shutdown)
        loop.add_signal_handler(signal.SIGTERM, graceful_shutdown)

    try:
        loop.run_until_complete(main_async())
    except asyncio.CancelledError:
        logging.info("El bucle principal de eventos fue cancelado.")
