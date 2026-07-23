"""
ORM Models — re-exported from submodules for convenience.
Import this package to register all models with SQLAlchemy's metadata.
"""

from app.models.alert import Alert
from app.models.audit import AuditLog, RecordChangeHistory
from app.models.case import (
    Act,
    ActSectionAssociation,
    CaseMaster,
    CaseStageEvent,
    CaseStatusMaster,
    ChargesheetDetails,
    CrimeHead,
    CrimeSubHead,
    GravityOffence,
    Section,
)
from app.models.document import Document
from app.models.financial import FinancialTransaction
from app.models.location import Location
from app.models.offender import CriminalHistory, MOLinkageCluster, RiskScore
from app.models.person import CasteMaster, OccupationMaster, Person, PersonCaseRole, ReligionMaster
from app.models.reports import ReportShareLink
from app.models.security import OtpChallenge, RefreshTokenRecord
from app.models.socio import CrimeStatAggregate, DistrictCompositeIndex, SocioEconomicIndicator
from app.models.unit import Court, District, State, Unit, UnitType
from app.models.user import User
from app.models.vector import VectorChunk
from app.models.workspace import CaseNote

__all__ = [
    "Alert",
    "AuditLog",
    "RecordChangeHistory",
    "Act",
    "ActSectionAssociation",
    "CaseMaster",
    "CaseStageEvent",
    "CaseStatusMaster",
    "ChargesheetDetails",
    "CrimeHead",
    "CrimeSubHead",
    "GravityOffence",
    "Section",
    "Document",
    "FinancialTransaction",
    "Location",
    "CriminalHistory",
    "MOLinkageCluster",
    "RiskScore",
    "CasteMaster",
    "OccupationMaster",
    "Person",
    "PersonCaseRole",
    "ReligionMaster",
    "OtpChallenge",
    "RefreshTokenRecord",
    "ReportShareLink",
    "CrimeStatAggregate",
    "DistrictCompositeIndex",
    "SocioEconomicIndicator",
    "Court",
    "District",
    "State",
    "Unit",
    "UnitType",
    "User",
    "VectorChunk",
    "CaseNote",
]
