# Enterprise AI Workflow Automation Platform

An internal AI assistant for **NovaTech**, a fictional technology company, built to
demonstrate production-style AI/backend engineering: structured LLM outputs, RAG over
company policy documents, agentic workflows with tool calling, deterministic risk rules,
human-in-the-loop approval, audit logging, and an evaluation harness — not a chatbot demo.

> **NovaTech, its employees, policies, and internal APIs are entirely fictional.**
> They exist only to give this project a realistic enterprise setting.

This README grows with each implementation phase. It currently reflects **Phase 5**.

## Status: Phase 5 — LangGraph workflow

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
  switches to a real Claude call using structured outputs (`RequestClassification`). A
  third mode, `LLM_MODE=ollama`, uses a locally-running [Ollama](https://ollama.com)
  server (`ollama pull llama3.2`, no API key, genuinely free) via the same structured
  interface. `docker-compose.yml` maps `host.docker.internal` into the backend
  container so it can reach an Ollama server running on the host — see "Using a local
  Ollama model" below.
- `POST /api/requests/{request_id}/classify` — classifies a submitted request into one
  of 9 intents (data access, IT equipment/software, travel, expenses, time off, remote
  work, security incident, other), stores the result, and advances the request's status
  to `CLASSIFIED`.
- Four mock enterprise tools (`app/tools/`), each encoding the actual approval rules
  from the Phase 2 policy documents as deterministic Python logic: `grant_data_access`
  (sensitivity-tiered approval, contractor HIGH-sensitivity restrictions),
  `create_it_ticket` (standard vs. non-standard equipment, pre-approved vs. new
  software), `book_travel` (domestic/international, cost threshold), and
  `submit_expense` (auto-approve / manager / manager+Finance tiers). Each tool is a
  pure function (no DB access) returning an `APPROVED` / `PENDING_APPROVAL` / `DENIED`
  outcome, so the business rules are unit-testable without a database.
- Every tool call is logged to a shared `tool_executions` table (input, result,
  outcome, and an optional link to the `Request` it was made for) via
  `POST /api/tools/{data-access,it-ticket,travel-booking,expense-reimbursement}` and
  listed via `GET /api/tools/executions` — this is what the Phase 5 LangGraph workflow
  will call into, and what Phase 7's audit log will build on.
- A LangGraph workflow (`app/workflows/graph.py`, nodes in `app/agents/nodes.py`) that
  wires everything above into one agentic pipeline:
  `classify -> retrieve_policy -> plan -> risk_check -> execute -> verify -> respond`.
  `POST /api/requests/{request_id}/run` runs a request through it end to end and
  persists every artifact (classification, retrieved policy chunks, planned tool call,
  risk assessment, resulting `tool_executions` row, and a final response) onto the
  `Request` row in one commit.
  - Intents with no matching mock tool (time off, remote work, security incidents, other)
    skip straight from policy retrieval to a policy-only response - there's no tool to plan
    or execute for those yet.
  - `plan` extends the LLM provider abstraction with a `plan()` method (mock: regex/keyword
    heuristics against the request text and the DB's known resource names; real providers:
    structured-output extraction) that turns free text into arguments for the matching tool.
  - `risk_check` is a deterministic rules layer independent of any single tool's own
    approval tiers - it force-escalates a request to human review (`AWAITING_APPROVAL`)
    for cross-cutting concerns no tool would catch on its own, such as an inactive
    employee, a low-confidence classification, or a tool plan missing a required argument
    (e.g. no resource name could be matched in the request text).
  - `execute` calls the same Phase 4 tool functions and logs to `tool_executions` via a
    shared `persist_tool_execution` helper, so a workflow-triggered tool call is
    indistinguishable in the audit trail from one triggered directly via `/api/tools/*`.
- pytest suite (63 tests) covering the API endpoints, RAG chunking/embedding/retrieval,
  classification (including a network-free Ollama-provider test), the mock tools'
  business rules and API wiring, and the LangGraph workflow's branches (auto-approval,
  pending-approval, denial, policy-only response, and risk-based escalation).

Not yet implemented (later phases): pause/resume for human-in-the-loop approval (the
workflow currently reaches `AWAITING_APPROVAL` as a terminal state but nothing can yet
resume it), audit logging, the React frontend, the evaluation harness, and CI/CD. See
the phase plan below.

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
    tools/          mock enterprise tools (data access, IT tickets, travel, expenses)
    rag/            embeddings, chunking, ingestion, retrieval
    agents/         LangGraph node implementations and shared workflow state
    evaluation/     (later) evaluation harness
    workflows/      LangGraph graph definition (classify -> ... -> respond)
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
no external LLM calls — used for local dev and CI. `LLM_MODE=anthropic` and
`LLM_MODE=ollama` switch on the real provider integrations added in Phase 3.

## Using a local Ollama model

[Ollama](https://ollama.com) runs an LLM on your own machine for free — no API key,
no billing. To use it for classification instead of the mock or Anthropic providers:

```bash
sudo pacman -S ollama          # or the install method for your OS
sudo systemctl enable --now ollama
ollama pull llama3.2
```

By default Ollama only listens on `127.0.0.1`, which the backend's Docker container
can't reach. Make it listen on all interfaces, and if you run a firewall, restrict
that to Docker's bridge network rather than opening it to your whole LAN:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\n' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama

# find the Compose project's bridge subnet and allow only that:
docker network inspect enterprise-ai-workflow-platform_default --format '{{json .IPAM.Config}}'
sudo ufw allow from <subnet-from-above> to any port 11434
```

Then set `LLM_MODE=ollama` (and optionally `OLLAMA_MODEL=<other model>`) in `.env` or
as a Compose environment override, and re-run `docker compose up --build`.

## Phase plan

1. ✅ Backend foundations: FastAPI, PostgreSQL, Docker Compose, SQLAlchemy, Alembic, seed data
2. ✅ RAG ingestion + retrieval over NovaTech policy documents (pgvector)
3. ✅ LLM provider abstraction, structured request classification, mock LLM mode
4. ✅ Mock enterprise tools (database/repo access, IT tickets, travel, expenses)
5. ✅ LangGraph workflow (classify → retrieve → plan → risk check → execute → respond)
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
