# sam/balanceador/run_balanceador.py (Refactorizado con patrón Fábrica)

import logging
import signal
import sys
from typing import Optional

from sam.balanceador.service.main import BalanceadorService
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging
from sam.common.mail_client import EmailAlertClient

SERVICE_NAME = "balanceador"
service_instance: Optional[BalanceadorService] = None


def graceful_shutdown(signum, frame):
    logging.info(f"Señal de parada recibida (Señal: {signum}). Iniciando cierre ordenado...")
    if service_instance:
        service_instance.stop()


def main():
    """Función principal que inicializa y ejecuta el servicio Balanceador."""
    global service_instance

    setup_logging(service_name=SERVICE_NAME)
    logging.info(f"Iniciando el servicio: {SERVICE_NAME.capitalize()}")

    db_sam = None
    db_rpa360 = None

    try:
        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)

        # --- 1. Creación de Dependencias (Patrón Fábrica) ---
        logging.info("Creando dependencias del servicio Balanceador...")
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
        db_sam = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
        )

        cfg_sql_rpa360 = ConfigManager.get_sql_server_config("SQL_RPA360")
        db_rpa360 = DatabaseConnector(
            servidor=cfg_sql_rpa360["servidor"],
            base_datos=cfg_sql_rpa360["base_datos"],
            usuario=cfg_sql_rpa360["usuario"],
            contrasena=cfg_sql_rpa360["contrasena"],
        )

        notificador = EmailAlertClient(service_name=SERVICE_NAME)

        # --- 2. Inyección de Dependencias ---
        service_instance = BalanceadorService(db_sam=db_sam, db_rpa360=db_rpa360, notificador=notificador)

        logging.info("Iniciando el ciclo principal del servicio Balanceador...")
        service_instance.run()

    except Exception as e:
        logging.critical(f"Error crítico no controlado en el servicio {SERVICE_NAME}: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # --- 3. Limpieza Final de Recursos ---
        logging.info("Iniciando limpieza final de recursos...")
        if db_sam:
            db_sam.cerrar_conexion_hilo_actual()
        if db_rpa360:
            db_rpa360.cerrar_conexion_hilo_actual()
        logging.info(f"El servicio {SERVICE_NAME} ha concluido su ejecución.")

