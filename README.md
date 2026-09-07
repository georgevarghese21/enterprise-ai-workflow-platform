# Enterprise AI Workflow Automation Platform

An internal AI assistant for **NovaTech**, a fictional technology company, built to
demonstrate production-style AI/backend engineering: structured LLM outputs, RAG over
company policy documents, agentic workflows with tool calling, deterministic risk rules,
human-in-the-loop approval, audit logging, and an evaluation harness — not a chatbot demo.

> **NovaTech, its employees, policies, and internal APIs are entirely fictional.**
> They exist only to give this project a realistic enterprise setting.

This README grows with each implementation phase. It currently reflects **Phase 3**.

## Status: Phase 3 — LLM classification

What exists so far:

- FastAPI backend with a health check, employees, resources, requests, and policy
  search endpoints.
- PostgreSQL with the `pgvector` extension, SQLAlchemy models, and Alembic migrations
  for `employees`, `resources`, `requests`, and `policy_chunks`.
- Seed data: ~30 fictional NovaTech employees across 7 departments with a manager
  hierarchy, and 9 mock enterprise resources (databases, repos, cloud accounts, tools).
- 5 fictional NovaTech policy documents (`data/policies/`) covering data access,
  IT equipment/software, travel & expenses, remote work & time off, and security
  incidents — split into ~35 chunks, embedded, and stored in `policy_chunks`.
- A deterministic, dependency-free "mock" embedding provider (feature-hashing
  bag-of-words) so ingestion, retrieval, and tests never need an external API call;
  a real provider can be swapped in behind the same interface in a later phase.
- `POST /api/policy/search` — cosine-similarity search over policy chunks.
  `GET /api/policy/documents` — lists ingested documents and their chunk counts.
- Docker Compose setup running Postgres + the backend together, applying migrations,
  seeding, and ingesting policy documents on startup.
- An LLM provider abstraction (`app/services/llm_provider.py`) mirroring the embedding
  provider pattern: the default `mock` mode is a deterministic keyword-rule classifier
  with no external calls, and `LLM_MODE=anthropic` (with `ANTHROPIC_API_KEY` set)
  switches to a real Claude call using structured outputs (`RequestClassification`).
- `POST /api/requests/{request_id}/classify` — classifies a submitted request into one
  of 9 intents (data access, IT equipment/software, travel, expenses, time off, remote
  work, security incident, other), stores the result, and advances the request's status
  to `CLASSIFIED`.
- pytest suite (24 tests) covering the API endpoints, RAG chunking/embedding/retrieval,
  and classification built so far.

Not yet implemented (later phases): LangGraph workflow, tool execution,
human-in-the-loop approvals, audit logging, the React frontend, the evaluation
harness, and CI/CD. See the phase plan below.

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
    rag/            embeddings, chunking, ingestion, retrieval
    evaluation/     (later) evaluation harness
    workflows/      (later) LangGraph graph definition
    main.py
  alembic/         migrations
  tests/           pytest suite
data/
  policies/        fictional NovaTech policy documents (markdown, source for RAG)
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
employees/resources, ingests the policy documents under `data/policies/` for RAG,
and starts the API at http://localhost:8000 (docs at http://localhost:8000/docs).

## Running tests

Tests require a reachable Postgres (they create a separate `novatech_test`
database automatically). With the Compose Postgres running:

```bash
cd backend
pip install -e ".[dev]"
DATABASE_URL=postgresql+psycopg://novatech:novatech@localhost:5432/novatech_test pytest
```

or inside Docker (the `DATABASE_URL` override is required — without it, `pytest` inherits
Compose's `novatech` dev-database URL, and the test suite's teardown will wipe the dev
database's tables):

```bash
docker compose run --rm -e DATABASE_URL=postgresql+psycopg://novatech:novatech@postgres:5432/novatech_test backend pytest
```

## Environment variables

See [`.env.example`](.env.example). `LLM_MODE=mock` (the default) runs the system with
no external LLM calls — used for local dev and CI until Phase 3 introduces the real
provider integrations.

## Phase plan

1. ✅ Backend foundations: FastAPI, PostgreSQL, Docker Compose, SQLAlchemy, Alembic, seed data
2. ✅ RAG ingestion + retrieval over NovaTech policy documents (pgvector)
3. ✅ LLM provider abstraction, structured request classification, mock LLM mode
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
