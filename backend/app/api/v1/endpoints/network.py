"""Network analysis endpoints (§4)."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.enums import Role
from app.models.user import User
from app.services.analytics.network_analysis import NetworkAnalysisService

router = APIRouter()


@router.get("/ego/{person_id}", response_model=Dict[str, Any])
async def get_ego_network(
    person_id: str,
    depth: int = Query(2, ge=1, le=4),
    current_user: User = Depends(require_roles(Role.INVESTIGATOR, Role.ANALYST, Role.ADMIN)),
):
    """Force-directed graph data for a person's ego network."""
    svc = NetworkAnalysisService()
    return await svc.get_ego_network(person_id, depth)


@router.get("/co-offending", response_model=Dict[str, Any])
async def get_cooffending_network(
    district_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(Role.INVESTIGATOR, Role.ANALYST, Role.ADMIN)),
):
    """Bipartite accused↔incident projection — person-person co-offending graph."""
    svc = NetworkAnalysisService()
    return await svc.get_cooffending_network(district_id, date_from, date_to)


@router.get("/communities", response_model=List[Dict[str, Any]])
async def detect_communities(
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Run Louvain community detection — surfaces criminal cells/sub-groups."""
    svc = NetworkAnalysisService()
    return await svc.detect_communities()


@router.get("/predicted-links/{person_id}", response_model=List[Dict[str, Any]])
async def get_predicted_links(
    person_id: str,
    top_k: int = Query(10, le=50),
    current_user: User = Depends(require_roles(Role.INVESTIGATOR, Role.ANALYST, Role.ADMIN)),
):
    """
    Plausible-but-unconfirmed connections (GCN link prediction).
    Always labeled PREDICTED — never rendered identically to confirmed edges.
    """
    svc = NetworkAnalysisService()
    return await svc.get_link_predictions(person_id, top_k)


@router.get("/multi-jurisdiction", response_model=List[Dict[str, Any]])
async def get_multi_jurisdiction_offenders(
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Persons whose cases span multiple police station jurisdictions (organized-crime signal)."""
    svc = NetworkAnalysisService()
    return await svc.get_multi_jurisdiction_offenders()
