import asyncio
import logging
import os
import sys
from typing import Optional

# --- Configuración del Path y Carga de Configuración ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from sam.common.config_loader import ConfigLoader

    # RFR-31: Se elimina el segundo argumento `__file__` que causaba el TypeError.
    # La nueva versión de ConfigLoader no requiere este parámetro.
    ConfigLoader.initialize_service("lanzador")

except Exception as e:
    print(f"Error crítico durante la inicialización de la configuración: {e}")
    sys.exit(1)

# --- Importaciones de los componentes necesarios ---
from sam.common.a360_client import AutomationAnywhereClient
from sam.common.config_manager import ConfigManager
from sam.common.database import DatabaseConnector
from sam.common.logging_setup import setup_logging
from sam.common.sincronizador_comun import SincronizadorComun


async def main():
    """
    Función principal que ejecuta una única vez el ciclo de sincronización
    utilizando el nuevo componente común.
    """
    setup_logging(service_name="prueba_sincro")
    logging.info("--- INICIANDO PRUEBA DE SINCRONIZACIÓN AISLADA ---")

    db_connector: Optional[DatabaseConnector] = None
    aa_client: Optional[AutomationAnywhereClient] = None

    try:
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
            api_key=aa_cfg.get("api_key"),
            api_timeout_seconds=aa_cfg.get("api_timeout_seconds"),
        )

        sincronizador = SincronizadorComun(db_connector=db_connector, aa_client=aa_client)

        logging.info("Ejecutando el método 'sincronizar_entidades' del componente común...")
        resultado = await sincronizador.sincronizar_entidades()
        logging.info(f"Sincronización finalizada exitosamente: {resultado}")

    except Exception as e:
        logging.critical(f"Error durante la prueba de sincronización: {e}", exc_info=True)
    finally:
        logging.info("Iniciando limpieza de recursos...")
        if aa_client:
            await aa_client.close()
        if db_connector:
            db_connector.cerrar_conexiones_pool()
        logging.info("--- PRUEBA DE SINCRONIZACIÓN TERMINADA ---")


if __name__ == "__main__":
    asyncio.run(main())

