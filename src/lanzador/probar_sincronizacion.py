import asyncio
import logging
import os
import sys
from typing import Optional

# --- Configuración del Path y Carga de Configuración ---
# Este bloque es idéntico al de run_lanzador.py para asegurar que
# el entorno se configure correctamente.
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.common.utils.config_loader import ConfigLoader

    ConfigLoader.initialize_service("lanzador", __file__)

except Exception as e:
    print(f"Error crítico durante la inicialización de la configuración: {e}")
    sys.exit(1)

# --- Importaciones de los componentes necesarios ---
from src.common.clients.aa_client import AutomationAnywhereClient
from src.common.database.sql_client import DatabaseConnector
from src.common.utils.config_manager import ConfigManager
from src.common.utils.logging_setup import setup_logging
from src.lanzador.service.sincronizador import Sincronizador


async def main():
    """
    Función principal que ejecuta una única vez el ciclo de sincronización.
    """
    # Usamos un nombre de logger diferente para no mezclar con los logs del servicio
    setup_logging(service_name="prueba_sincro")
    logging.info("--- INICIANDO PRUEBA DE SINCRONIZACIÓN AISLADA ---")

    db_connector: Optional[DatabaseConnector] = None
    aa_client: Optional[AutomationAnywhereClient] = None

    try:
        # 1. Crear las dependencias necesarias (igual que en run_lanzador.py)
        logging.info("Creando dependencias (clientes y conectores)...")
        cfg_sql_sam = ConfigManager.get_sql_server_config("SQL_SAM")
        db_connector = DatabaseConnector(
            servidor=cfg_sql_sam["servidor"],
            base_datos=cfg_sql_sam["base_datos"],
            usuario=cfg_sql_sam["usuario"],
            contrasena=cfg_sql_sam["contrasena"],
        )

        aa_cfg = ConfigManager.get_aa_config()
        aa_client = AutomationAnywhereClient(
            control_room_url=aa_cfg["url_cr"],
            username=aa_cfg["usuario"],
            password=aa_cfg.get("pwd"),
            **aa_cfg,
        )

        # 2. Crear la instancia del "cerebro" de sincronización
        sincronizador = Sincronizador(db_connector=db_connector, aa_client=aa_client)

        # 3. Ejecutar el método de sincronización
        logging.info("Ejecutando el método 'sincronizar_entidades'...")
        await sincronizador.sincronizar_entidades()
        logging.info("Sincronización finalizada exitosamente.")

    except Exception as e:
        logging.critical(f"Error durante la prueba de sincronización: {e}", exc_info=True)
    finally:
        # 4. Limpieza de recursos
        logging.info("Iniciando limpieza de recursos...")
        if aa_client:
            await aa_client.close()
        if db_connector:
            db_connector.cerrar_conexion()
        logging.info("--- PRUEBA DE SINCRONIZACIÓN TERMINADA ---")


if __name__ == "__main__":
    asyncio.run(main())
