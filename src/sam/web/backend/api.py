# sam/web/api.py
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from sam.common.database import DatabaseConnector

# Importa los servicios desde el archivo local de base de datos
from . import database as db_service
from .dependencies import get_db

# Importa los schemas desde el archivo local de schemas
from .schemas import (
    AssignmentUpdateRequest,
    PoolAssignmentsRequest,
    PoolCreate,
    PoolUpdate,
    RobotCreateRequest,
    RobotUpdateRequest,
    ScheduleData,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/sync", tags=["Sincronización"])
async def trigger_sync(db: DatabaseConnector = Depends(get_db)):
    """
    Dispara el proceso de sincronización manual con Automation Anywhere A360.
    """
    try:
        summary = await db_service.sync_with_a360(db)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la sincronización: {str(e)}")


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
        return db_service.get_robots(
            db=db, name=name, active=active, online=online, page=page, size=size, sort_by=sort_by, sort_dir=sort_dir
        )
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


@router.post("/api/robots", tags=["Robots"], status_code=201)
def create_robot(robot_data: RobotCreateRequest, db: DatabaseConnector = Depends(get_db)):
    try:
        new_robot = db_service.create_robot(db, robot_data)
        if not new_robot:
            raise HTTPException(status_code=500, detail="No se pudo crear el robot.")
        return new_robot
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado al crear el robot: {e}")


# --- Rutas para Programaciones ---
@router.get("/api/schedules", tags=["Programaciones"])
def get_all_schedules(db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_all_schedules(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener programaciones: {e}")


@router.get("/api/schedules/robot/{robot_id}", tags=["Programaciones"])
def get_robot_schedules(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_robot_schedules(db, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener programaciones: {str(e)}")


@router.delete("/api/schedules/{programacion_id}/robot/{robot_id}", tags=["Programaciones"], status_code=204)
def delete_schedule(programacion_id: int, robot_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.delete_schedule(db, programacion_id, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la programación: {e}")


@router.post("/api/schedules", tags=["Programaciones"])
def create_schedule(data: ScheduleData, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.create_schedule(db, data)
        return {"message": "Programación creada con éxito."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la programación: {e}")


@router.put("/api/schedules/{schedule_id}", tags=["Programaciones"])
def update_schedule(schedule_id: int, data: ScheduleData, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.update_schedule(db, schedule_id, data)
        return {"message": "Programación actualizada con éxito"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la programación: {e}")


# --- Rutas para Equipos ---
@router.get("/api/equipos/disponibles/{robot_id}", tags=["Equipos"])
def get_available_devices(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    """
    Endpoint para obtener equipos disponibles. El robot_id se mantiene por
    compatibilidad con la ruta, pero la lógica de negocio (BR-05, BR-06)
    ya no lo requiere.
    """
    try:
        # La llamada al servicio ya no necesita el robot_id.
        return db_service.get_available_teams_for_robot(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener equipos disponibles: {e}")


# --- Rutas para Asignaciones ---
@router.get("/api/robots/{robot_id}/asignaciones", tags=["Asignaciones"])
def get_robot_assignments(robot_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_asignaciones_by_robot(db, robot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener asignaciones: {e}")


@router.post("/api/robots/{robot_id}/asignaciones", tags=["Asignaciones"])
def update_robot_assignments(
    robot_id: int, update_data: AssignmentUpdateRequest, db: DatabaseConnector = Depends(get_db)
):
    try:
        # RFR-34: Se usan los nombres de campo correctos del modelo Pydantic.
        result = db_service.update_asignaciones_robot(
            db, robot_id, update_data.asignar_equipo_ids, update_data.desasignar_equipo_ids
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar asignaciones: {e}")


# --- Rutas para Pools ---
@router.get("/api/pools", tags=["Pools"])
def get_all_pools(db: DatabaseConnector = Depends(get_db)):
    logger.info("Solicitud para obtener todos los pools recibida.")
    try:
        pools = db_service.get_pools(db)
        logger.info(f"Se encontraron y devolvieron {len(pools)} pools.")
        return pools
    except Exception as e:
        logger.error(f"Error al obtener los pools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener los pools: {str(e)}")


@router.post("/api/pools", tags=["Pools"], status_code=201)
def create_new_pool(pool_data: PoolCreate, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.create_pool(db, pool_data.Nombre, pool_data.Descripcion)
    except Exception as e:
        logger.error(f"Error al crear el pool: {e}", exc_info=True)
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/api/pools/{pool_id}", tags=["Pools"])
def update_existing_pool(pool_id: int, pool_data: PoolUpdate, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.update_pool(db, pool_id, pool_data.Nombre, pool_data.Descripcion)
        return {"message": f"Pool {pool_id} actualizado con éxito."}
    except Exception as e:
        error_message = str(e)
        if "No se encontró un pool" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        elif "ya está en uso" in error_message:
            raise HTTPException(status_code=409, detail=error_message)
        else:
            logger.error(f"Error al actualizar el pool {pool_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=error_message)


@router.delete("/api/pools/{pool_id}", tags=["Pools"], status_code=204)
def delete_single_pool(pool_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        db_service.delete_pool(db, pool_id)
    except Exception as e:
        logger.error(f"Error al eliminar el pool {pool_id}: {e}", exc_info=True)
        error_message = str(e)
        if "No se encontró un pool" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Error al eliminar el pool: {error_message}")


@router.get("/api/pools/{pool_id}/asignaciones", tags=["Pools"])
def get_pool_assignments(pool_id: int, db: DatabaseConnector = Depends(get_db)):
    try:
        return db_service.get_pool_assignments_and_available_resources(db, pool_id)
    except Exception as e:
        logger.error(f"Error al obtener asignaciones para el pool {pool_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al obtener asignaciones: {str(e)}")


@router.put("/api/pools/{pool_id}/asignaciones", tags=["Pools"])
def set_pool_assignments(pool_id: int, data: PoolAssignmentsRequest, db: DatabaseConnector = Depends(get_db)):
    try:
        # RFR-34: Se usa el nombre de campo corregido 'equipo_ids'.
        db_service.assign_resources_to_pool(db, pool_id, data.robot_ids, data.equipo_ids)
        return {"message": f"Asignaciones para el Pool {pool_id} actualizadas correctamente."}
    except Exception as e:
        logger.error(f"Error al actualizar asignaciones para el pool {pool_id}: {e}", exc_info=True)
        error_message = str(e)
        if "No se encontró un pool" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=500, detail=f"Error al actualizar asignaciones: {error_message}")
