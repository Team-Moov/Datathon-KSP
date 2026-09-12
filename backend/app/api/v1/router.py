"""Top-level v1 API router — aggregates all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    alerts,
    auth,
    cases,
    chat,
    documents,
    financial,
    internal_tasks,
    models,
    network,
    persons,
    reports,
    risk,
    socio,
    trends,
    workspace,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(cases.router, prefix="/cases", tags=["Cases"])
api_router.include_router(persons.router, prefix="/persons", tags=["Persons"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents & Ingestion"])
api_router.include_router(network.router, prefix="/network", tags=["Network Analysis"])
api_router.include_router(trends.router, prefix="/trends", tags=["Crime Patterns & Trends"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Early-Warning Alerts"])
api_router.include_router(models.router, prefix="/models", tags=["Model Transparency"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Profiling"])
api_router.include_router(financial.router, prefix="/financial", tags=["Financial Crime"])
api_router.include_router(socio.router, prefix="/socio", tags=["Sociological Insights"])
api_router.include_router(chat.router, prefix="/chat", tags=["Conversational AI"])
api_router.include_router(reports.router, prefix="/reports", tags=["Secure Report Sharing"])
api_router.include_router(workspace.router, prefix="/workspace", tags=["Investigator Workspace"])
api_router.include_router(admin.router, prefix="/admin", tags=["Administration"])
api_router.include_router(internal_tasks.router, prefix="/internal/tasks", tags=["Internal Task Triggers"])
