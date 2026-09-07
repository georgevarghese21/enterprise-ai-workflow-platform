from fastapi import FastAPI

from app.api import employees, health, policy, requests, resources
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Internal AI assistant for NovaTech (a fictional company) that "
        "classifies employee requests, retrieves company policy via RAG, "
        "and executes approved workflows with human-in-the-loop approval."
    ),
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(employees.router)
app.include_router(resources.router)
app.include_router(requests.router)
app.include_router(policy.router)
