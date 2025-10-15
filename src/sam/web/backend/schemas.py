from typing import List, Optional, TypedDict

from pydantic import BaseModel


class RobotCreateRequest(BaseModel):
    RobotId: int
    Robot: str
    Descripcion: Optional[str] = None
    Activo: bool
    EsOnline: bool
    MinEquipos: int = -1
    MaxEquipos: int = 1
    PrioridadBalanceo: int = 100
    TicketsPorEquipoAdicional: Optional[int] = None


class RobotUpdateRequest(BaseModel):
    Robot: str
    Descripcion: Optional[str] = None
    MinEquipos: int
    MaxEquipos: int
    PrioridadBalanceo: int
    TicketsPorEquipoAdicional: Optional[int] = None


class ScheduleData(BaseModel):
    RobotId: int
    TipoProgramacion: str
    HoraInicio: str
    Tolerancia: int
    Equipos: List[int]  # Lista de EquipoId
    DiasSemana: Optional[str] = None
    DiaDelMes: Optional[int] = None
    FechaEspecifica: Optional[str] = None


class AssignmentUpdateRequest(BaseModel):
    asignar_equipo_ids: List[int]
    desasignar_equipo_ids: List[int]


# Define la estructura de un objeto Robot
# Basado en lo que devuelve tu endpoint /api/robots
class Robot(TypedDict):
    RobotId: int
    Robot: str
    Descripcion: Optional[str]
    Activo: bool
    EsOnline: bool
    MinEquipos: int
    MaxEquipos: int
    PrioridadBalanceo: int
    TicketsPorEquipoAdicional: Optional[int]
    CantidadEquiposAsignados: int


# Define la estructura de los filtros que usaremos en la API y el frontend
class RobotFilters(TypedDict, total=False):
    name: Optional[str]
    active: Optional[bool]
    online: Optional[bool]
    page: Optional[int]
    size: Optional[int]


class PoolCreate(BaseModel):
    Nombre: str
    Descripcion: Optional[str] = None


class PoolUpdate(BaseModel):
    Nombre: str
    Descripcion: Optional[str] = None


class PoolAssignmentsRequest(BaseModel):
    robot_ids: List[int]
    # RFR-34: Se estandariza el nombre del campo para que sea consistente.
    equipo_ids: List[int]
