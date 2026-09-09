# Enterprise AI Workflow Automation Platform

[![CI](https://github.com/georgevarghese21/enterprise-ai-workflow-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/georgevarghese21/enterprise-ai-workflow-platform/actions/workflows/ci.yml)

An internal AI assistant for **NovaTech**, a fictional technology company, built to
demonstrate production-style AI/backend engineering: structured LLM outputs, RAG over
company policy documents, agentic workflows with tool calling, deterministic risk rules,
human-in-the-loop approval, audit logging, and an evaluation harness — not a chatbot demo.

> **NovaTech, its employees, policies, and internal APIs are entirely fictional.**
> They exist only to give this project a realistic enterprise setting.

This README grows with each implementation phase. It currently reflects **Phase 10**,
the last one in the original plan — see "Beyond the phase plan" at the bottom for
honest, evaluation-harness-backed ideas for what would come next.

## Status: Phase 10 — Docker polish, CI/CD, documentation (project complete)

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
- Human-in-the-loop approval (Phase 6): `GET /api/requests/pending-approval` lists every
  request sitting at `AWAITING_APPROVAL` (the approval queue); `POST
  /api/requests/{request_id}/approve` and `.../reject` resume a request's workflow with
  a human's decision.
  - Implemented as a second, smaller LangGraph graph (`build_resume_graph` in
    `app/workflows/graph.py`: `apply_decision -> [execute -> verify] -> respond`) that
    rehydrates its starting state from what the first graph run already persisted onto
    the `Request` row - the row itself is the "checkpoint," rather than a separate
    durable LangGraph checkpointer. That's a deliberate simplification: the graph always
    runs synchronously start-to-finish within one request, so there's no long-running
    process to checkpoint mid-node, and it avoids the correctness trade-offs of LangGraph's
    native `interrupt()` mechanism (node code re-executing from the top on resume, so any
    side effects before the interrupt point must be idempotent). A distributed or
    long-running deployment would likely want the native checkpointer instead.
  - Two situations resolve differently, both handled by the same `apply_decision` node:
    a request escalated by `risk_check` *before* any tool ran (approving now runs the
    tool for the first time; rejecting ends the request with no tool ever called), and a
    request whose tool itself already returned `PENDING_APPROVAL` under its own approval
    tier (approving/rejecting overrides that `tool_executions` row's status directly).
  - Authorization is deliberately minimal for this phase: any *active* employee other
    than the requester themselves can approve or reject (self-approval and approval by
    an inactive employee are both rejected with 400). There's no real RBAC yet (e.g.
    "must be the requester's manager," or "must be Security for a HIGH-sensitivity
    resource") - a later phase could add that.
  - Approving a request whose plan was incomplete when it escalated (e.g. no resource
    name could be matched) fails cleanly with `422` rather than crashing - approval
    doesn't fabricate missing data, so that case still needs a resubmission or a manual
    tool call.
- Audit logging and a workflow timeline (Phase 7): every request now has a complete,
  append-only history at `GET /api/requests/{request_id}/timeline`, ordered oldest
  first.
  - Nothing had to change inside `app/agents/nodes.py` to get this: both graphs now run
    via `graph.stream(..., stream_mode="updates")` instead of `.invoke()`
    (`_run_graph_with_events` in `app/workflows/graph.py`), which yields one
    `{node_name: partial_state}` update per node as it completes. That's folded into a
    running state dict (equivalent to what `.invoke()` would have returned, since every
    field is last-write-wins) *and* written as a `workflow_events` row - so the timeline
    comes from the graph's own execution trace, not from instrumenting each node.
  - Two more events are logged directly by the API layer for things that happen outside
    the graph: `request_created` (when a request is first submitted) and
    `approval_decision` (who approved/rejected and their notes - distinct from the
    `apply_decision` node event, which only captures the resulting state change).
  - If a node raises (e.g. `execute` refusing an incomplete plan - see Phase 6), the
    failure itself is logged as a `workflow_error` event before the exception
    propagates, so a failed attempt still shows up in the audit trail even though that
    run never reached `respond`.
  - `workflow_events` is append-only and FK's to `requests` with `ON DELETE CASCADE`; it
    exists specifically so a request's full history survives even when the `Request` row
    itself gets overwritten by a later run (e.g. a second approval cycle after a tool
    call comes back `PENDING_APPROVAL` a second time).
- A server-rendered frontend (Phase 8): FastAPI + Jinja2 + [htmx](https://htmx.org),
  mounted alongside the JSON API in the same app/container (no separate frontend
  toolchain, no build step, no npm). Pages: a dashboard, a request list (with a status
  filter), a new-request form, a request detail page, an approval queue, and read-only
  employees/resources reference pages.
  - This was a deliberate substitute for the originally-planned React + TypeScript
    frontend, chosen to avoid a from-scratch TypeScript/React learning curve. The web
    routes (`app/web/routes.py`) call the same DB session and workflow-graph functions
    the JSON API under `app/api/requests.py` uses directly, rather than making HTTP
    calls to the JSON API from the server.
  - The request detail page and approval queue use htmx to submit actions (run the
    workflow, approve, reject) and swap in just the returned HTML fragment - no full
    page reload, no client-side JavaScript logic of any kind.
  - Fixed along the way: `request.plan_arguments`/`retrieved_policy`/`risk_flags` were
    being collapsed from an empty container (`{}`/`[]`) to `NULL` via an `X or None`
    idiom in both `app/api/requests.py` and the new web routes, which crashed the detail
    template's `plan_arguments.items()` the first time a plan genuinely extracted zero
    arguments (e.g. a data-access request naming a resource that doesn't exist). Fixed at
    the source in both places - see the comments there - since it's a real distinction
    ("this step ran and found nothing" vs. "this step never ran"), not just a template
    workaround.
- An evaluation harness (Phase 9): `app/evaluation/` runs a hand-written 22-case test set
  through the real workflow against a real database and reports intent classification,
  tool selection, risk classification, and approval routing accuracy; RAG recall@1/3/5;
  workflow completion rate; a supported-answer rate (is the final response backed by a
  meaningfully relevant retrieved chunk, not just any chunk); and a safe-routing rate (did
  anything that should have required human review get auto-completed instead). See the
  "Evaluation" section below for real, generated numbers from an actual run - not
  aspirational placeholders - plus what they reveal about the mock classifier and mock
  embedding provider's real limitations.
- Along the way, a shared `apply_run_result` helper (`app/workflows/graph.py`) replaced
  three near-identical copies of "write a graph run's final state back onto its Request
  row" that had accumulated across `app/api/requests.py`, `app/web/routes.py`, and now the
  evaluation runner - and while unifying them, fixed a real bug where the resume/approval
  path never carried `classification_reasoning` forward, silently wiping it to `NULL` on
  every approval.
- Docker polish, CI/CD, and a documentation pass (Phase 10):
  - The 5 `mypy` errors carried since Phase 5 (an untyped `dict` in `create_it_ticket`,
    an ORM object passed where a Pydantic model was expected in `/api/policy/search`,
    and the Anthropic SDK's `.parsed_output` being typed `T | None`) are fixed for real -
    `mypy app` is clean with zero errors, not "clean except a known list."
  - `backend/Dockerfile`: dependencies now install in their own cached layer (a minimal
    placeholder package structure stands in until the real source is copied in after),
    so editing application code no longer busts the slow `pip install` layer - verified
    locally, a real code change now rebuilds in under a second instead of ~50s. Also adds
    a `HEALTHCHECK` against `/health` and drops `--reload` from the image's own default
    `CMD` (docker-compose.yml's dev `command:` still enables it, unchanged for local dev).
  - `.github/workflows/ci.yml`: runs on every push/PR to `main` - `ruff check`, `mypy`,
    `alembic upgrade head` against a fresh Postgres service container (independent of the
    pytest suite's own `Base.metadata.create_all()`-based schema setup, so it actually
    verifies the migration chain applies cleanly and hasn't drifted from the models), and
    the full pytest suite. Verified locally end to end in a bare virtualenv (not the
    Docker image) against the same Postgres before being trusted here, since a bare-venv
    CI runner is a meaningfully different environment from what every other phase was
    tested in.
  - Removed the empty `frontend/` placeholder's `node_modules/`/`frontend/dist/`
    `.gitignore` entries (dead since Phase 8 replaced that plan) and cleaned up a couple
    of stale "(later)" repository-structure lines left over from Phase 1's original
    scaffold description.
- pytest suite: **98 tests**, all passing - API endpoints; RAG chunking, embedding, and
  retrieval; classification (including a network-free Ollama-provider test); the mock
  tools' business rules and API wiring; the LangGraph workflow's branches (auto-approval,
  pending-approval, denial, policy-only response, risk-based escalation); the
  approve/reject resume flow; the audit timeline; the web routes; and the evaluation
  harness's pure metric functions and test-case loader.

All 10 planned phases are complete. See "Beyond the phase plan" below for what a next
phase would realistically tackle, grounded in what Phase 9's evaluation run actually
found rather than a generic wishlist.

## Architecture (target — will fill in as phases land)

```mermaid
flowchart LR
    subgraph Frontend
        UI[Jinja2 + htmx]
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
- **AI:** LangGraph (workflow orchestration), an Anthropic/Ollama/mock provider
  abstraction with structured outputs via Pydantic, RAG over `pgvector`
- **Frontend:** Server-rendered with FastAPI + Jinja2 + htmx (no separate build/toolchain)
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
    services/      LLM provider abstraction, tool-execution persistence, audit logging
    tools/          mock enterprise tools (data access, IT tickets, travel, expenses)
    rag/            embeddings, chunking, ingestion, retrieval
    agents/         LangGraph node implementations and shared workflow state
    evaluation/     evaluation harness: test-case loader, metrics, runner, report
    workflows/      LangGraph graph definition (classify -> ... -> respond)
    web/            server-rendered frontend: routes.py, Jinja2 templates, static CSS
    main.py
  alembic/         migrations
  tests/           pytest suite
data/
  policies/        fictional NovaTech policy documents (markdown, source for RAG)
  evaluation/      evaluation test set (test_cases.json) and generated results.json
docker-compose.yml
```

## Running locally

```bash
cp .env.example .env   # optional; Compose sets its own env for the backend
docker compose up --build
```

This starts Postgres, applies Alembic migrations, seeds NovaTech's fictional
employees/resources, ingests the policy documents under `data/policies/` for RAG,
and starts the API at http://localhost:8000 (docs at http://localhost:8000/docs). The
web UI (Phase 8) is served from the same app at http://localhost:8000/ - submit a
request at `/requests/new`, run its workflow, and review/approve anything that lands in
the `/approvals` queue.

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
database's tables; the `LLM_MODE` override is required too if you have a local
`docker-compose.override.yml` switching it to `ollama`/`anthropic` for manual testing —
`docker compose run` picks that up same as `up` does, and the test suite is written
assuming the deterministic `mock` provider, not a real model's non-deterministic output):

```bash
docker compose run --rm \
  -e DATABASE_URL=postgresql+psycopg://novatech:novatech@postgres:5432/novatech_test \
  -e LLM_MODE=mock \
  backend pytest
```

## Environment variables

See [`.env.example`](.env.example). `LLM_MODE=mock` (the default) runs the system with
no external LLM calls — used for local dev and CI. `LLM_MODE=anthropic` and
`LLM_MODE=ollama` switch on the real provider integrations added in Phase 3;
`LLM_MODE=groq` (a free hosted API) and `LLM_MODE=cascade` (mock first, Groq only when
unsure) were added later — see "Using Groq" below and "Evaluation" for real numbers on
all four.

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

## Using Groq (a free hosted API)

[Groq](https://console.groq.com) hosts open-weight models and its free tier needs no
credit card and doesn't expire - a practical alternative to Ollama when the local
machine can't run a model large enough to be reliable (see "Evaluation" below for why
that matters: a 3-7B local model scored *worse than random guessing* at this project's
classification task, while Groq's hosted ~120B model scored 100%). Sign up, create an
API key under **API Keys**, then set:

```bash
LLM_MODE=groq
GROQ_API_KEY=gsk_...
```

as a `.env` entry or Compose environment override, and re-run `docker compose up --build`.
Groq's model lineup changes over time; `GROQ_MODEL` in `app/services/llm_provider.py`
pins a specific one, so check Groq's `/v1/models` endpoint if it ever 404s.

**`LLM_MODE=cascade`** is a variant worth using over plain `groq`: it classifies every
request with the free mock provider first, and only calls Groq when the mock's own
confidence comes back below 0.8 (`CascadeLLMProvider.CONFIDENCE_THRESHOLD` in
`app/services/llm_provider.py`). On this project's 22-case test set that cut real API
calls by roughly two-thirds (13 calls instead of ~40) while matching or beating plain
Groq's accuracy - see "Evaluation" for the actual numbers. Needs `GROQ_API_KEY` set the
same as `groq` mode; the mock handles the rest for free.

## Phase plan

1. ✅ Backend foundations: FastAPI, PostgreSQL, Docker Compose, SQLAlchemy, Alembic, seed data
2. ✅ RAG ingestion + retrieval over NovaTech policy documents (pgvector)
3. ✅ LLM provider abstraction, structured request classification, mock LLM mode
4. ✅ Mock enterprise tools (database/repo access, IT tickets, travel, expenses)
5. ✅ LangGraph workflow (classify → retrieve → plan → risk check → execute → respond)
6. ✅ Human-in-the-loop approvals with workflow pause/resume
7. ✅ Audit logging and workflow timeline
8. ✅ Frontend (server-rendered FastAPI + Jinja2 + htmx, in place of React + TypeScript)
9. ✅ Evaluation harness with real, generated metrics
10. ✅ Docker polish, CI/CD, documentation

## Evaluation

`backend/app/evaluation/` is a harness that runs a hand-written, 22-case test set
(`data/evaluation/test_cases.json`) through the *real* workflow
(`run_request_workflow`, against a real seeded database - nothing here is a
simulation beyond whatever `LLM_MODE=mock` already is) and reports the metrics named
in the phase plan. Run it with:

```bash
docker compose exec backend python -m app.evaluation.runner
```

against the seeded dev database (or any `DATABASE_URL` with the standard seed data
loaded). It prints a report to stdout and writes `data/evaluation/results.json`.

**Numbers below are from an actual run** (2026-09-08, `LLM_MODE=mock`) - not aspirational:

| Metric | Result |
| --- | --- |
| Intent classification accuracy | 20/22 (91%) |
| Tool selection accuracy | 20/20 (100%) |
| Risk classification accuracy | 20/20 (100%) |
| Approval routing accuracy | 20/20 (100%) |
| RAG recall@1 | 12/21 (57%) |
| RAG recall@3 | 17/21 (81%) |
| RAG recall@5 | 18/21 (86%) |
| Workflow completion rate | 22/22 (100%) |
| Supported-answer rate | 20/22 (91%) |
| Safe-routing rate | 11/11 (100%) |

Two real findings worth calling out, not just the numbers:

- **The two intent misclassifications are deliberate, not noise.** The test set
  includes two "known hard case" queries (`hard_lost_laptop_misclassified`,
  `hard_nonstandard_equipment_no_keyword`) chosen specifically to trip up the mock
  keyword-rule classifier - e.g. "I lost my laptop" hits both the IT_EQUIPMENT keyword
  `laptop` and the SECURITY_INCIDENT keyword `lost my laptop` with equal (1-hit) scores,
  and the classifier only overturns its current best guess on a *strict* improvement, so
  whichever intent it checks first (IT_EQUIPMENT, per dict order in
  `app/services/llm_provider.py`) wins the tie. Everything downstream of a
  misclassification is excluded from scoring for that case (tool/risk/approval-routing
  accuracy), since grading a decision built on the wrong premise wouldn't mean anything -
  see the applicability rules documented in `app/evaluation/metrics.py`.
- **RAG recall@1 (57%) is the weakest number here, and it's real.** Manually inspecting
  the misses shows the mock embedding provider (dependency-free feature-hashing
  bag-of-words, chosen so RAG never needs an external API call - see Phase 2) sometimes
  ranks a wrong document first with real confidence: a domestic-travel-booking query
  ranks `security-incident-and-acceptable-use-policy.md` above
  `travel-and-expense-policy.md` at a 0.398 score. Recall climbs to 86% by k=5, so the
  right document is usually *somewhere* in what the workflow retrieves (which currently
  asks for `top_k=3` - see `retrieve_policy` in `app/agents/nodes.py`) - just not
  reliably first. Swapping in a real embedding provider behind the same
  `app.rag.embeddings` interface used for `LLM_MODE=anthropic`/`ollama` would be the
  obvious next step to close this gap; the mock provider was always meant to unblock
  everything else built on top of it (Phases 3-9), not to be a good ranker.
- **`da_medium_pending` and `expense_100_1000_pending` are notable "correct but
  informationally thin" cases.** Both correctly end up `AWAITING_APPROVAL` (approval
  routing accuracy counts them right), but `risk_check` only bumps `risk_level` above
  `LOW` for HIGH-sensitivity data access or expenses over $1,000 - not for the
  MEDIUM-sensitivity / $100-$1,000 tiers that still require a human to sign off per the
  tool's own rules. So `risk_level` alone understates how many requests actually need
  review; `status == AWAITING_APPROVAL` is the reliable signal, `risk_level` is
  supplementary color. Worth tightening in a future pass over `risk_check`.

Re-running the harness adds 22 fresh `Request`/`tool_executions`/`workflow_events` rows
to whatever database it's pointed at each time (it exercises the real system, so this is
expected) - point it at a disposable database, or don't worry about the extra rows in a
dev database.

### Provider comparison: is a real AI model actually better?

The table above is `LLM_MODE=mock`, the zero-setup default. Out of curiosity (and to
answer that question honestly instead of assuming), the same 22 cases were also run
against three real providers - **also actual runs**, not estimates:

| Metric | Mock | Qwen2.5:7b (local, Ollama) | Groq / gpt-oss-120b | Groq cascade |
| --- | --- | --- | --- | --- |
| Intent accuracy | 91% | 18%\* | 100% | 100% |
| Tool selection | 100% | 30%\* | 100% | 100% |
| Risk classification | 100% | 50%\* | 95%\*\* | 100% |
| Approval routing | 100% | 55%\* | 95%\*\* | 100% |
| Real API/model calls made | 0 | 22+ | ~40 | 13 |
| Wall-clock time | seconds | ~4 min | 1m48s | 12s |

\* Qwen's collapse traces to one specific, fixable cause, not the model being
inherently bad: this project's classification prompt (`_CLASSIFICATION_SYSTEM_PROMPT`
in `app/services/llm_provider.py`) used to hand the model 9 bare category *names*
(`DATA_ACCESS`, `TIME_OFF`, ...) with no description of what any of them mean. A
frontier-scale model like Claude can apparently infer the intended meaning from the
label alone; a 7B model can't, and confidently reasoned its way to wrong answers
instead ("vacation days can be considered under expense reimbursement"). The prompt
now spells out what each of the 9 categories actually covers
(`_INTENT_DESCRIPTIONS`), which is a real fix that helps every provider, not a Qwen
workaround.

\*\* Groq's one "miss" on each of these (the same case, `it_sw_preapproved_auto` -
"a software license for Slack") isn't really wrong: its own planning prompt tells it to
omit an argument rather than guess when unsure, and it has no way to know NovaTech's
internal pre-approved-software list isn't in the retrieved policy text either - so it
correctly left the field blank and let `risk_check` escalate to a human instead of
guessing. The mock only "gets this right" because it has that specific list hardcoded.

**The cascade result is the interesting one**: classify with the free mock first, and
only call Groq when the mock's own confidence is below 0.8 (see "Using Groq" above).
It matched the mock's 0 cost on 9 of the 22 cases, escalated the rest, and landed at
**100% across the board with less than a third of Groq's own API calls** - because the
mock's hardcoded knowledge (e.g. that Slack is pre-approved) fixed the one case plain
Groq got "wrong," while genuinely ambiguous cases (the two hard-coded hard cases) still
got the smarter model. This is the config actually worth running if real accuracy
matters and free-tier rate limits or per-token cost are a concern - see the retry/backoff
handling for Groq's 429s in `GroqLLMProvider._chat_json`, needed because gpt-oss-120b is
a reasoning model that burns through the free tier's tokens-per-minute budget fast under
back-to-back load (a live one-request-at-a-time workload won't notice this).

None of this changes RAG recall@1 (57%) - retrieval is driven by `EMBEDDING_PROVIDER`,
a separate setting still on the mock embedding provider regardless of `LLM_MODE`.

## Screenshots

_Text-based; see "Using the web UI" above and the templates under
`backend/app/web/templates/` - a screenshot pass could be added later._

## Beyond the phase plan

All 10 phases from the original plan are done. These aren't a generic "future work"
wishlist - each one is a specific, real gap the project itself surfaced (mostly via the
Phase 9 evaluation run), in rough priority order:

1. **Swap in a real embedding provider for RAG.** Still open: the classification side of
   this got solved (see "Using Groq" / "Provider comparison" above - `LLM_MODE=cascade`
   gets 100% intent accuracy for a fraction of the API calls), but RAG recall@1 is still
   57% regardless of `LLM_MODE`, because retrieval runs through a *separate* setting,
   `EMBEDDING_PROVIDER`, which is still the mock feature-hashing implementation. The
   provider abstraction (`app/rag/embeddings.py`) already supports swapping this the same
   way `llm_provider.py` does for classification; this is a config change plus an API
   key, not new code.
2. **Tighten `risk_check`'s risk-level assessment.** It only bumps `risk_level` above
   `LOW` for HIGH-sensitivity data access or expenses over $1,000, understating risk for
   MEDIUM-sensitivity resources and the $100-$1,000 expense tier (both still correctly
   require approval via the tool's own rules - only the informational `risk_level` field
   undersells it). Also flagged by the Phase 9 run.
3. **Real RBAC for approvals**, replacing the current "any active employee but the
   requester" rule (see Phase 6) - e.g. requiring the requester's actual manager, or
   matching the specific department a tool's message names (Security co-approval for a
   contractor's HIGH-sensitivity access, Finance for equipment over $2,000).
4. **A durable LangGraph checkpointer** if this workflow ever needed to run as a
   genuinely long-lived, distributed process - the current `Request`-row-as-checkpoint
   approach (see Phase 6) is a deliberate, documented trade-off that fits a
   request/response backend, not a hard limitation nobody noticed.
5. **Grow the evaluation test set.** 22 hand-written cases is enough to catch real,
   specific issues (as it did), but nowhere near enough for statistically meaningful
   percentages - more cases per intent, particularly around the classifier's keyword-tie
   failure mode, would sharpen the numbers.
