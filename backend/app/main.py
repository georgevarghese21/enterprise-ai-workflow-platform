from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import employees, health, policy, requests, resources, tools
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.web import routes as web_routes

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
app.include_router(tools.router)

# Phase 8: server-rendered HTML frontend (Jinja2 + htmx), mounted alongside
# the JSON API above rather than replacing it.
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "web" / "static")),
    name="static",
)
app.include_router(web_routes.router)
