"""ORM model registry.

Importing this package registers every model on ``Base.metadata`` so that Alembic's
``env.py`` (and any ``create_all``) can discover the full schema.
"""

from app.db.models.allocation import Allocation
from app.db.models.audit_log import AuditLog
from app.db.models.bed_count import BedCount
from app.db.models.decision_log import DecisionLog
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.facility_request import FacilityRequest
from app.db.models.notification import Notification
from app.db.models.permission import Permission
from app.db.models.reservation import Reservation
from app.db.models.role import Role
from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession
from app.db.models.user_account import UserAccount

__all__ = [
    "Allocation",
    "AuditLog",
    "BedCount",
    "DecisionLog",
    "EmergencyRequest",
    "Facility",
    "FacilityRequest",
    "Notification",
    "Permission",
    "Reservation",
    "Role",
    "SimulationAllocationEvent",
    "SimulationBedState",
    "SimulationSession",
    "UserAccount",
]
