import os

_DEFAULT_TEST_DB_URL = "postgresql+psycopg://novatech:novatech@localhost:5432/novatech_test"
os.environ.setdefault("DATABASE_URL", _DEFAULT_TEST_DB_URL)

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.enums import Department, EmploymentType, ResourceType, Sensitivity
from app.models.resource import Resource

settings = get_settings()

if "test" not in make_url(settings.database_url).database:
    raise RuntimeError(
        f"Refusing to run tests against DATABASE_URL={settings.database_url!r}: its "
        "database name doesn't contain 'test'. This test suite drops and recreates "
        "every table, so pointing it at a non-test database (e.g. the dev database) "
        "would destroy real data. Point DATABASE_URL at a *_test database instead."
    )


def _ensure_database_exists(database_url: str) -> None:
    """Create the target database if it doesn't exist yet.

    The Compose Postgres container only provisions the `novatech` database
    on first boot, so the separate `novatech_test` database used by the
    test suite needs to be created on demand via the `postgres` maintenance
    database.
    """
    url = make_url(database_url)
    db_name = url.database
    admin_url = url.set(database="postgres")

    conn = psycopg.connect(
        host=admin_url.host,
        port=admin_url.port,
        user=admin_url.username,
        password=admin_url.password,
        dbname="postgres",
        autocommit=True,
    )
    try:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()


_ensure_database_exists(settings.database_url)
engine = create_engine(settings.database_url, future=True)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE requests, employees, resources, policy_chunks, "
                "tool_executions RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_employee(db_session) -> Employee:
    employee = Employee(
        name="Jordan Lee",
        email="jordan.lee@novatech.io",
        department=Department.ENGINEERING,
        role="Senior Software Engineer",
        employment_type=EmploymentType.FULL_TIME,
        location="San Francisco",
        active=True,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return employee


@pytest.fixture
def sample_resource(db_session) -> Resource:
    resource = Resource(
        name="analytics-db",
        resource_type=ResourceType.DATABASE,
        sensitivity=Sensitivity.LOW,
        description="Read-mostly analytics warehouse.",
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource
