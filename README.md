# Enterprise AI Workflow Automation Platform

An internal AI assistant for **NovaTech**, a fictional technology company, built to
demonstrate production-style AI/backend engineering: structured LLM outputs, RAG over
company policy documents, agentic workflows with tool calling, deterministic risk rules,
human-in-the-loop approval, audit logging, and an evaluation harness — not a chatbot demo.

> **NovaTech, its employees, policies, and internal APIs are entirely fictional.**
> They exist only to give this project a realistic enterprise setting.

This README grows with each implementation phase. It currently reflects **Phase 1**.

## Status: Phase 1 — Foundations

What exists so far:

- FastAPI backend with a health check, employees, resources, and requests endpoints.
- PostgreSQL (via the `pgvector/pgvector` image, so pgvector is ready for Phase 2) with
  SQLAlchemy models and an Alembic migration for `employees`, `resources`, `requests`.
- Seed data: ~30 fictional NovaTech employees across 7 departments with a manager
  hierarchy, and 9 mock enterprise resources (databases, repos, cloud accounts, tools).
- Docker Compose setup running Postgres + the backend together.
- pytest suite covering the API endpoints built so far.

Not yet implemented (later phases): RAG ingestion/retrieval, LLM classification,
LangGraph workflow, tool execution, human-in-the-loop approvals, audit logging, the
React frontend, the evaluation harness, and CI/CD. See the phase plan below.

## Architecture (target — will fill in as phases land)

```mermaid
flowchart LR
    subgraph Frontend
        UI[React + TypeScript]
    end
    subgraph Backend
        API[FastAPI]
        LG[LangGraph Workflow]
        RAG[RAG Retrieval]
        Tools[Mock Enterprise Tools]
    end
    DB[(PostgreSQL + pgvector)]

    UI --> API
    API --> LG
    LG --> RAG
    LG --> Tools
    RAG --> DB
    Tools --> DB
    API --> DB
```

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **Database:** PostgreSQL 16 with the `pgvector` extension
- **AI (upcoming phases):** LangGraph, Anthropic/OpenAI-compatible provider abstraction,
  structured outputs via Pydantic, embeddings + RAG
- **Frontend (upcoming):** React, TypeScript, Vite
- **Infra:** Docker, Docker Compose, pytest, GitHub Actions

## Repository structure

```
backend/
  app/
    api/          FastAPI routers
    core/         settings, logging
    db/           session, declarative base, seed data
    models/       SQLAlchemy models
    schemas/      Pydantic request/response models
    services/      (later) business logic
    agents/        (later) LangGraph nodes
    tools/          (later) mock enterprise tools
    rag/            (later) embeddings/retrieval
    evaluation/     (later) evaluation harness
    workflows/      (later) LangGraph graph definition
    main.py
  alembic/         migrations
  tests/           pytest suite
data/
  policies/        (later) fictional NovaTech policy documents
  evaluation/      (later) evaluation test cases
frontend/          (later) React + TypeScript app
docker-compose.yml
```

## Running locally

```bash
cp .env.example .env   # optional; Compose sets its own env for the backend
docker compose up --build
```

This starts Postgres, applies Alembic migrations, seeds NovaTech's fictional
employees/resources, and starts the API at http://localhost:8000 (docs at
http://localhost:8000/docs).

## Running tests

Tests require a reachable Postgres (they create a separate `novatech_test`
database automatically). With the Compose Postgres running:

```bash
cd backend
pip install -e ".[dev]"
DATABASE_URL=postgresql+psycopg://novatech:novatech@localhost:5432/novatech_test pytest
```

or inside Docker:

```bash
docker compose run --rm backend pytest
```

## Environment variables

See [`.env.example`](.env.example). `LLM_MODE=mock` (the default) runs the system with
no external LLM calls — used for local dev and CI until Phase 3 introduces the real
provider integrations.

## Phase plan

1. ✅ Backend foundations: FastAPI, PostgreSQL, Docker Compose, SQLAlchemy, Alembic, seed data
2. RAG ingestion + retrieval over NovaTech policy documents (pgvector)
3. LLM provider abstraction, structured request classification, mock LLM mode
4. Mock enterprise tools (database/repo access, IT tickets, travel, expenses)
5. LangGraph workflow (classify → retrieve → plan → risk check → execute → respond)
6. Human-in-the-loop approvals with workflow pause/resume
7. Audit logging and workflow timeline
8. React + TypeScript frontend
9. Evaluation harness with real, generated metrics
10. Docker polish, CI/CD, documentation

## Evaluation

A real evaluation harness (Phase 9) will measure intent classification accuracy, tool
selection accuracy, risk classification accuracy, approval routing accuracy, RAG
recall@1/3/5, workflow completion rate, unsupported-answer rate, and unsafe-action rate
against a hand-written test set. No metrics are reported until they can be generated
from an actual run — none are published yet.

## Screenshots

_To be added once the frontend (Phase 8) exists._
