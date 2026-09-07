"""Idempotent seed data for the NovaTech fictional company.

Run with `python -m app.db.seed`. Safe to re-run: it upserts by unique
email (employees) / name (resources) rather than blindly inserting.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.employee import Employee
from app.models.enums import Department, EmploymentType, ResourceType, Sensitivity
from app.models.resource import Resource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmployeeSeed:
    name: str
    email: str
    department: Department
    role: str
    manager_email: str | None
    employment_type: EmploymentType
    location: str
    active: bool = True


@dataclass(frozen=True)
class ResourceSeed:
    name: str
    resource_type: ResourceType
    sensitivity: Sensitivity
    description: str


EMPLOYEES: list[EmployeeSeed] = [
    # Executives / department heads (no manager)
    EmployeeSeed("Sarah Chen", "sarah.chen@novatech.io", Department.ENGINEERING,
                 "VP of Engineering", None, EmploymentType.FULL_TIME, "San Francisco"),
    EmployeeSeed("Marcus Webb", "marcus.webb@novatech.io", Department.DATA_SCIENCE,
                 "Head of Data Science", None, EmploymentType.FULL_TIME, "New York"),
    EmployeeSeed("Priya Nair", "priya.nair@novatech.io", Department.IT,
                 "IT Director", None, EmploymentType.FULL_TIME, "Dublin"),
    EmployeeSeed("David Okafor", "david.okafor@novatech.io", Department.FINANCE,
                 "Finance Director", None, EmploymentType.FULL_TIME, "London"),
    EmployeeSeed("Helen Brooks", "helen.brooks@novatech.io", Department.HR,
                 "Head of HR", None, EmploymentType.FULL_TIME, "London"),
    EmployeeSeed("Tomasz Adamczyk", "tomasz.adamczyk@novatech.io", Department.SECURITY,
                 "CISO", None, EmploymentType.FULL_TIME, "Dublin"),
    EmployeeSeed("Renee Dupont", "renee.dupont@novatech.io", Department.SALES,
                 "Head of Sales", None, EmploymentType.FULL_TIME, "Paris"),

    # Engineering
    EmployeeSeed("Alex Kim", "alex.kim@novatech.io", Department.ENGINEERING,
                 "Engineering Manager", "sarah.chen@novatech.io", EmploymentType.FULL_TIME,
                 "San Francisco"),
    EmployeeSeed("Jordan Lee", "jordan.lee@novatech.io", Department.ENGINEERING,
                 "Senior Software Engineer", "alex.kim@novatech.io", EmploymentType.FULL_TIME,
                 "San Francisco"),
    EmployeeSeed("Maria Gonzalez", "maria.gonzalez@novatech.io", Department.ENGINEERING,
                 "Software Engineer", "alex.kim@novatech.io", EmploymentType.FULL_TIME, "Remote"),
    EmployeeSeed("Chris Bailey", "chris.bailey@novatech.io", Department.ENGINEERING,
                 "Software Engineer", "alex.kim@novatech.io", EmploymentType.FULL_TIME, "Austin"),
    EmployeeSeed("Noah Fischer", "noah.fischer@novatech.io", Department.ENGINEERING,
                 "Contract Software Engineer", "alex.kim@novatech.io", EmploymentType.CONTRACTOR,
                 "Remote"),
    EmployeeSeed("Ling Zhao", "ling.zhao@novatech.io", Department.ENGINEERING,
                 "DevOps Engineer", "sarah.chen@novatech.io", EmploymentType.FULL_TIME, "Dublin"),

    # Data Science
    EmployeeSeed("Amara Eze", "amara.eze@novatech.io", Department.DATA_SCIENCE,
                 "Senior Data Scientist", "marcus.webb@novatech.io", EmploymentType.FULL_TIME,
                 "New York"),
    EmployeeSeed("Ben Carter", "ben.carter@novatech.io", Department.DATA_SCIENCE,
                 "Data Scientist", "marcus.webb@novatech.io", EmploymentType.FULL_TIME, "Remote"),
    EmployeeSeed("Yuki Tanaka", "yuki.tanaka@novatech.io", Department.DATA_SCIENCE,
                 "Data Analyst", "marcus.webb@novatech.io", EmploymentType.FULL_TIME, "Tokyo"),
    EmployeeSeed("Owen Murphy", "owen.murphy@novatech.io", Department.DATA_SCIENCE,
                 "Contract Data Analyst", "marcus.webb@novatech.io", EmploymentType.CONTRACTOR,
                 "Remote"),

    # IT
    EmployeeSeed("Grace Kelly", "grace.kelly@novatech.io", Department.IT,
                 "IT Support Specialist", "priya.nair@novatech.io", EmploymentType.FULL_TIME,
                 "Dublin"),
    EmployeeSeed("Samuel Osei", "samuel.osei@novatech.io", Department.IT,
                 "Systems Administrator", "priya.nair@novatech.io", EmploymentType.FULL_TIME,
                 "Dublin"),
    EmployeeSeed("Fiona Walsh", "fiona.walsh@novatech.io", Department.IT,
                 "IT Support Specialist", "priya.nair@novatech.io", EmploymentType.FULL_TIME,
                 "London"),

    # Finance
    EmployeeSeed("Robert Hayes", "robert.hayes@novatech.io", Department.FINANCE,
                 "Financial Analyst", "david.okafor@novatech.io", EmploymentType.FULL_TIME,
                 "London"),
    EmployeeSeed("Emma Laurent", "emma.laurent@novatech.io", Department.FINANCE,
                 "Accounts Payable Specialist", "david.okafor@novatech.io",
                 EmploymentType.FULL_TIME, "Paris"),
    EmployeeSeed("Daniel Cohen", "daniel.cohen@novatech.io", Department.FINANCE,
                 "Financial Controller", "david.okafor@novatech.io", EmploymentType.FULL_TIME,
                 "London"),

    # HR
    EmployeeSeed("Isabel Rossi", "isabel.rossi@novatech.io", Department.HR,
                 "HR Business Partner", "helen.brooks@novatech.io", EmploymentType.FULL_TIME,
                 "London"),
    EmployeeSeed("Liam O'Connor", "liam.oconnor@novatech.io", Department.HR,
                 "Recruiter", "helen.brooks@novatech.io", EmploymentType.FULL_TIME, "Dublin"),

    # Security
    EmployeeSeed("Nina Petrov", "nina.petrov@novatech.io", Department.SECURITY,
                 "Security Engineer", "tomasz.adamczyk@novatech.io", EmploymentType.FULL_TIME,
                 "Dublin"),
    EmployeeSeed("Victor Alves", "victor.alves@novatech.io", Department.SECURITY,
                 "Security Analyst", "tomasz.adamczyk@novatech.io", EmploymentType.FULL_TIME,
                 "Remote"),

    # Sales
    EmployeeSeed("Sophie Martin", "sophie.martin@novatech.io", Department.SALES,
                 "Account Executive", "renee.dupont@novatech.io", EmploymentType.FULL_TIME,
                 "Paris"),
    EmployeeSeed("James Turner", "james.turner@novatech.io", Department.SALES,
                 "Sales Development Rep", "renee.dupont@novatech.io", EmploymentType.FULL_TIME,
                 "London"),
    EmployeeSeed("Aisha Rahman", "aisha.rahman@novatech.io", Department.SALES,
                 "Account Executive", "renee.dupont@novatech.io", EmploymentType.FULL_TIME,
                 "Remote", active=False),
]

RESOURCES: list[ResourceSeed] = [
    ResourceSeed("analytics-db", ResourceType.DATABASE, Sensitivity.LOW,
                 "Read-mostly analytics warehouse used for BI dashboards."),
    ResourceSeed("production-db", ResourceType.DATABASE, Sensitivity.HIGH,
                 "Primary production database backing customer-facing services."),
    ResourceSeed("development-db", ResourceType.DATABASE, Sensitivity.LOW,
                 "Development/staging database with synthetic data."),
    ResourceSeed("phoenix-repository", ResourceType.REPOSITORY, Sensitivity.MEDIUM,
                 "Core product monorepo (Project Phoenix)."),
    ResourceSeed("atlas-repository", ResourceType.REPOSITORY, Sensitivity.MEDIUM,
                 "Internal tooling repository (Project Atlas)."),
    ResourceSeed("jira", ResourceType.TOOL, Sensitivity.LOW,
                 "Issue tracking and project management tool."),
    ResourceSeed("github", ResourceType.TOOL, Sensitivity.LOW,
                 "Source control platform used company-wide."),
    ResourceSeed("aws-development", ResourceType.CLOUD, Sensitivity.MEDIUM,
                 "AWS development account."),
    ResourceSeed("aws-production", ResourceType.CLOUD, Sensitivity.HIGH,
                 "AWS production account hosting live infrastructure."),
]


def seed_employees(db: Session) -> dict[str, Employee]:
    by_email: dict[str, Employee] = {}

    # First pass: create/update every employee without manager_id, since
    # managers must already exist as rows before we can link to their ids.
    for seed in EMPLOYEES:
        employee = db.scalar(select(Employee).where(Employee.email == seed.email))
        if employee is None:
            employee = Employee(email=seed.email)
            db.add(employee)
        employee.name = seed.name
        employee.department = seed.department
        employee.role = seed.role
        employee.employment_type = seed.employment_type
        employee.location = seed.location
        employee.active = seed.active
        by_email[seed.email] = employee

    db.flush()

    # Second pass: wire up manager relationships now that everyone has an id.
    for seed in EMPLOYEES:
        if seed.manager_email is not None:
            by_email[seed.email].manager_id = by_email[seed.manager_email].id

    db.flush()
    return by_email


def seed_resources(db: Session) -> None:
    for seed in RESOURCES:
        resource = db.scalar(select(Resource).where(Resource.name == seed.name))
        if resource is None:
            resource = Resource(name=seed.name)
            db.add(resource)
        resource.resource_type = seed.resource_type
        resource.sensitivity = seed.sensitivity
        resource.description = seed.description


def run_seed() -> None:
    with SessionLocal() as db:
        employees = seed_employees(db)
        seed_resources(db)
        db.commit()
        logger.info("Seeded %d employees and %d resources", len(employees), len(RESOURCES))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
