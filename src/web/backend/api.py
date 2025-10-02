# src/web/api.py
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from common.database.sql_client import DatabaseConnector

# Importa los servicios desde el archivo local de base de datos
from . import database as db_service
from .dependencies import get_db

# Importa los schemas desde el archivo local de schemas
# Agrega estas importaciones al inicio de web/backend/api.py
from .schemas import AssignmentUpdateRequest, PoolAssignmentsRequest, PoolCreate, PoolUpdate, RobotCreateRequest, RobotUpdateRequest, ScheduleData

logger = logging.getLogger(__name__)

# --- Define un ÚNICO router para toda la API ---
router = APIRouter()


# Agrega esta ruta en api.py
@router.post("/api/sync", tags=["Sincronización"])
async def trigger_sync(db: DatabaseConnector = Depends(get_db)):
    """
    Dispara el proceso de sincronización manual con Automation Anywhere A360.
    """
    try:
        summary = await db_service.sync_with_a360(db)
        return summary
    except Exception as e:
        # En caso de error, devuelve un detalle claro al frontend
        raise HTTPException(status_code=500, detail=f"Error durante la sincronización: {str(e)}")


# router = APIRouter(prefix="/api/robots", tags=["Robots"])
# --- Rutas para Robots ---
@router.get("/api/robots", tags=["Robots"])
def get_robots_with_assignments(
    db: DatabaseConnector = Depends(get_db),
    name: Optional[str] = None,
    active: Optional[bool] = None,
    online: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: Optional[str] = Query("Robot"),
    sort_dir: Optional[str] = Query("asc"),
):
    try:
        return db_service.get_robots(db=db, name=name, active=active, online=online, page=page, size=size, sort_by=sort_by, sort_dir=sort_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener robots: {e}")


@router.patch("/api/robots/{robot_id}", tags=["Robots"])
def update_robot_status(robot_id: int, updates: Dict[str, bool] = Body(...), db: DatabaseConnector = Depends(get_db)):
    try:
        field_to_update = next(iter(updates))
        if field_to_update not in ["Activo", "EsOnline"]:
            raise HTTPException(status_code=400, detail="Campo no válido para actualización parcial.")
        success = db_service.update_robot_status(db, robot_id, field_to_update, updates[field_to_update])
        if success:
            return {"message": "Estado del robot actualizado con éxito."}
        raise HTTPException(status_code=404, detail="Robot no encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/robots/{robot_id}", tags=["Robots"])
def update_robot_details(robot_id: int, robot_data: RobotUpdateRequest, db: DatabaseConnector = Depends(get_db)):
    try:
        updated_count = db_service.update_robot_details(db, robot_id, robot_data)
        if updated_count > 0:
            return {"message": f"Robot {robot_id} actualizado con éxito."}
        else:
            raise HTTPException(status_code=404, detail="Robot no encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/robots/{robot_id}", tags=["Robots"], status_code=201)
def create_robot(robot_data: RobotCreateRequest, db: DatabaseConnector = Depends(get_db)):
    try:
        new_robot = db_service.create_robot(db, robot_data)
        if not new_robot:
            raise HTTPException(status_code=500, detail="No se pudo crear el robot.")
        return new_robot
    except ValueError as e:  # Captura el error específico del servicio
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado al crear el robot: {e}")


# router = APIRouter(tags=["Programaciones"])
# --- Rutas para Programaciones ---
@router.get("/api/robots/{robot_id}/programaciones", tags=["Programaciones"])
def get_robot_schedules(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_schedules_for_robot(db, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener programaciones: {e}")


@router.delete("/api/robots/{robot_id}/programaciones/{programacion_id}", tags=["Programaciones"], status_code=204)
def delete_schedule(robot_id: int, programacion_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.delete_schedule_full(db, programacion_id, robot_id)
        # No se devuelve contenido en un 204
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la programación: {e}")


@router.post("/api/programaciones", tags=["Programaciones"])
def create_schedule(data: ScheduleData, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.create_new_schedule(db, data)
        return {"message": "Programación creada con éxito."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la programación: {e}")


@router.put("/api/programaciones/{programacion_id}", tags=["Programaciones"])
def update_schedule(programacion_id: int, data: ScheduleData, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.update_existing_schedule(db, programacion_id, data)
        return {"message": "Programación actualizada con éxito"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la programación: {e}")


# router = APIRouter(prefix="/api/equipos", tags=["Equipos"])
# --- Rutas para Equipos ---
@router.get("/api/equipos/disponibles/{robot_id}", tags=["Equipos"])
def get_available_teams(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    """
    Obtiene la lista de equipos disponibles para ser asignados a un robot.
    """
    try:
        return db_service.get_available_teams_for_robot(db, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener equipos disponibles: {e}")


# router = APIRouter(prefix="/api/robots/{robot_id}/asignaciones", tags=["Asignaciones"])
@router.get("/api/robots/{robot_id}/asignaciones", tags=["Asignaciones"])
def get_robot_asignaciones(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_asignaciones_by_robot(db, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener asignaciones: {e}")


@router.post("/api/robots/{robot_id}/asignaciones", tags=["Asignaciones"])
def update_robot_asignaciones(robot_id: int, update_data: AssignmentUpdateRequest, db: DatabaseConnector = Depends(get_db)):
    try:
        result = db_service.update_asignaciones_robot(db, robot_id, update_data.assign_team_ids, update_data.unassign_team_ids)
        return result
    except ValueError as e:  # Para errores controlados como "Robot no encontrado"
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar asignaciones: {e}")


# --- Rutas para Pools ---
@router.get("/api/pools", tags=["Pools"])
def get_all_pools(db: DatabaseConnector = Depends(get_db)):
    """
    Obtiene la lista completa de pools de recursos.
    """
    try:
        # Aquí registramos el inicio de la acción
        logger.info("Solicitud para obtener todos los pools recibida.")
        pools = db_service.get_pools(db)
        logger.info(f"Se encontraron y devolvieron {len(pools)} pools.")
        return pools
    except Exception as e:
        # Y aquí registramos el error antes de devolverlo
        logger.error(f"Error al obtener los pools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener los pools: {str(e)}")


@router.post("/api/pools", tags=["Pools"], status_code=201)
def create_new_pool(pool_data: PoolCreate, db: DatabaseConnector = Depends(get_db)):
    """
    Crea un nuevo pool de recursos.
    """
    try:
        # Pasamos los datos del modelo Pydantic a la función del servicio
        return db_service.create_pool(db, pool_data.Nombre, pool_data.Descripcion)
    except Exception as e:
        # Capturamos posibles errores (ej. nombre duplicado desde el RAISERROR)
        logger.error(f"Error al obtener los pools: {e}", exc_info=True)
        raise HTTPException(status_code=409, detail=str(e))


# En src/web/api.py


@router.put("/api/pools/{pool_id}", tags=["Pools"])
def update_existing_pool(pool_id: int, pool_data: PoolUpdate, db: DatabaseConnector = Depends(get_db)):
    """
    Actualiza un pool de recursos existente.
    """
    try:
        # La función update_pool ahora simplemente ejecuta el SP.
        # Si el SP lanza un error (RAISERROR), se capturará en el bloque except.
        db_service.update_pool(db, pool_id, pool_data.Nombre, pool_data.Descripcion)
        return {"message": f"Pool {pool_id} actualizado con éxito."}

    # --- CORRECCIÓN: Capturamos HTTPException por separado para no modificarla ---
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        # Este bloque ahora solo captura errores del SP (nombre duplicado, no encontrado)
        # o errores de conexión inesperados.
        error_message = str(e)
        # Intentamos limpiar el mensaje de error de pyodbc
        if "pyodbc.ProgrammingError" in error_message:
            try:
                actual_message = error_message.split("]", 1)[1].strip()
                # Determinamos el código de estado correcto según el mensaje del SP
                if "No se encontró un pool" in actual_message:
                    raise HTTPException(status_code=404, detail=actual_message)
                else:  # Asumimos que es un conflicto de nombre
                    raise HTTPException(status_code=409, detail=actual_message)
            except IndexError:
                pass  # Usar el mensaje completo si no se puede parsear

        raise HTTPException(status_code=500, detail=error_message)


@router.delete("/api/pools/{pool_id}", tags=["Pools"], status_code=204)
def delete_single_pool(pool_id: int, db: DatabaseConnector = Depends(get_db)):
    """
    Elimina un pool de recursos específico.
    """
    try:
        db_service.delete_pool(db, pool_id)
        # Un 204 No Content no debe devolver cuerpo de respuesta
    except Exception as e:
        logger.error(f"Error al eliminar el pool {pool_id}: {e}", exc_info=True)
        # Intenta devolver el mensaje de error del SP
        error_message = str(e)
        if "No se encontró un pool" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Error al eliminar el pool: {error_message}")


@router.get("/api/pools/{pool_id}/asignaciones", tags=["Pools"])
def get_pool_assignments(pool_id: int, db: DatabaseConnector = Depends(get_db)):
    """
    Obtiene los recursos asignados y disponibles para un pool específico.
    """
    try:
        return db_service.get_pool_assignments_and_available_resources(db, pool_id)
    except Exception as e:
        logger.error(f"Error al obtener asignaciones para el pool {pool_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener asignaciones: {str(e)}")


@router.put("/api/pools/{pool_id}/asignaciones", tags=["Pools"])
def set_pool_assignments(pool_id: int, data: PoolAssignmentsRequest, db: DatabaseConnector = Depends(get_db)):
    """
    Establece (sobrescribe) las asignaciones de robots y equipos para un pool.
    """
    try:
        db_service.assign_resources_to_pool(db, pool_id, data.robot_ids, data.team_ids)
        return {"message": f"Asignaciones para el Pool {pool_id} actualizadas correctamente."}
    except Exception as e:
        logger.error(f"Error al actualizar asignaciones para el pool {pool_id}: {e}", exc_info=True)
        error_message = str(e)
        if "No se encontró un pool" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Error al actualizar asignaciones: {error_message}")
