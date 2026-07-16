"""ORM model registry.

Importing this package registers every model on ``Base.metadata`` so that Alembic's
``env.py`` (and any ``create_all``) can discover the full schema. Add new models here as
later phases introduce them (emergency_request, simulation_* in Phases 3-4).
"""

from app.db.models.bed_count import BedCount
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession

__all__ = [
    "BedCount",
    "EmergencyRequest",
    "Facility",
    "SimulationAllocationEvent",
    "SimulationBedState",
    "SimulationSession",
]
