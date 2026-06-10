# Aether — Goal-Driven AI Marketing Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11.4-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white"/>
  <img src="https://img.shields.io/badge/DRF-3.17-ff1709?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Backend_V1-COMPLETE-22c55e?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/license-MIT-64748b?style=for-the-badge"/>
</p>

---

> **Aether is not a CRM dashboard or a recommendation widget.**
>
> It is a goal-driven marketing execution pipeline. A marketer states an objective in plain English. Aether autonomously parses the intent, selects the audience, plans the campaign, generates communications, simulates dispatch, processes receipts, derives insights, persists the execution, and exposes results through a REST API — with no human intervention at any intermediate step.

## One-Sentence Summary

Aether is a deterministic AI marketing agent that converts marketer goals into fully executed campaigns through an explainable end-to-end pipeline.

---

## Live Demo

### Campaign Execution API
> Demonstrates the complete goal-to-execution pipeline through the REST API.

![Run Campaign API](./docs/screenshots/run-campaign.png)

### Campaign History
> Shows persisted campaign executions available for retrieval.

![Campaign History](./docs/screenshots/campaign-history.png)

### Campaign Detail Analytics
> Displays execution metrics, recommendations, and campaign insights.

![Campaign Detail](./docs/screenshots/campaign-detail.png)

## Table of Contents

- [What Makes Aether Different](#what-makes-aether-different)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Intelligence Layer](#intelligence-layer)
- [Project Structure](#project-structure)
- [Example Workflow](#example-workflow)
- [API Reference](#api-reference)
- [Database and Persistence](#database-and-persistence)
- [Technical Decisions](#technical-decisions)
- [Testing](#testing)
- [Installation and Setup](#installation-and-setup)
- [Roadmap](#roadmap)
- [What This Project Demonstrates](#what-this-project-demonstrates)

---

## Quick Demo

```text
Input:
"Bring back inactive customers"

↓

Goal Parser → REACTIVATION

↓

Audience Selector → Target customers selected

↓

Campaign Planner → Reactivation campaign generated

↓

Communication Manager → Personalized communications created

↓

Channel Service → Delivery events simulated

↓

Insights Engine → Metrics and recommendations generated

↓

Campaign persisted and retrievable through REST APIs
```

## What Makes Aether Different

Most marketing tools require a marketer to manually define segments, author messages, pick channels, dispatch, and interpret results. That workflow is fragmented and slow.

Aether collapses the entire workflow into a single intent statement:

```
"Bring back inactive customers"
"Reward loyal customers"
"Increase average order value"
"Recommend complementary products"
```

From that input alone, Aether executes every downstream step:

```
Parse intent → Select audience → Plan campaign → Generate communications
→ Simulate dispatch → Process receipts → Derive insights → Persist and expose via API
```

The project demonstrates **orchestration and autonomous decision-making** — not model training. Intelligence is applied at every pipeline stage, not isolated to a single predictive component.

**Core philosophy:**

| Principle | Choice |
|---|---|
| Predictability | Deterministic over stochastic |
| Trustworthiness | Explainability over complexity |
| Scope | End-to-end ownership over disconnected notebooks |
| Cost | Free-tier deployable — no paid APIs required |
| Engineering | Production mindset even at evaluation scale |

---

## Key Features

- **Natural-language goal input** — Marketers submit objectives as plain English strings
- **Goal Parser V2** — Rule-based NLP with synonym expansion; handles varied phrasing for the same intent; graceful `MANUAL_REVIEW` fallback on unknown goals
- **Customer Intelligence Engine** — Deterministic segment assignment, churn risk scoring, CLV tier estimation, recommended offer, channel preference, campaign priority, and natural-language decision explanations — one record per customer
- **Audience Selector** — Filters and prioritizes customers using intelligence outputs; selection is goal-driven and fully explainable
- **Campaign Planner** — Produces structured campaign manifests including name, channel strategy, offer, and messaging tone
- **Communication Manager** — Generates one per-customer communication record per execution; identifiers are deterministic within an instance and unique across runs
- **Channel Service** — Simulates dispatch across EMAIL, SMS, PUSH, and WHATSAPP; callback-driven delivery event generation
- **Receipt API** — Append-only immutable event ledger; never mutated after write
- **Insights Engine** — Derives delivery rate, open rate, click rate, and failure rate from receipts; produces explainable next-best-action recommendations
- **Execution Persistence** — Full campaign metadata stored in Django ORM; append-only
- **Django REST API** — Three production-style endpoints with serialized JSON responses
- **Django Admin** — Campaign executions browsable and inspectable out of the box
- **Standalone CLI** — `aether.py` executable independently of Django; interactive goal input with deterministic default fallback

---

## System Architecture

Aether is a sequential, single-responsibility pipeline. Each module owns one concern and passes a typed output to the next stage. Business logic never lives inside Django views.

```
╔══════════════════════════════════════════════════════════════════╗
║                    MARKETER GOAL (plain English)                 ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           │
                    ┌──────▼──────┐
                    │ Goal Parser │  Normalize → Synonym match → Structured objective
                    └──────┬──────┘  Fallback: MANUAL_REVIEW (never raises)
                           │
               ┌───────────▼───────────┐
               │   Audience Selector   │  Filter + prioritize via intelligence outputs
               └───────────┬───────────┘  Outputs: customer cohort + selection reasons
                           │
              ┌────────────▼────────────┐
              │    Campaign Planner     │  Campaign name, channel strategy, offer, tone
              └────────────┬────────────┘
                           │
          ┌────────────────▼────────────────┐
          │     Communication Manager       │  One message record per customer
          └────────────────┬────────────────┘  Deterministic IDs, unique per run
                           │
               ┌───────────▼───────────┐
               │    Channel Service    │  Simulated dispatch: EMAIL/SMS/PUSH/WHATSAPP
               └───────────┬───────────┘  Callback-driven delivery events
                           │
                  ┌────────▼────────┐
                  │   Receipt API   │  Append-only event ledger (never mutated)
                  └────────┬────────┘
                           │
              ┌────────────▼────────────┐
              │    Insights Engine      │  delivery_rate, open_rate, click_rate,
              └────────────┬────────────┘  failure_rate + explainable recommendations
                           │
        ┌──────────────────▼──────────────────┐
        │       Execution Persistence          │  Django ORM — append-only record
        └──────────────────┬──────────────────┘
                           │
              ┌────────────▼────────────┐
              │        REST APIs        │  POST run-campaign / GET campaigns / GET detail
              └─────────────────────────┘
```

### Module Responsibilities

**`goal_parser.py`** — Accepts a raw marketer goal string. Normalizes text (lowercase, whitespace strip), then matches against a phrase/synonym dictionary. Supported objectives: `REACTIVATION`, `LOYALTY`, `UPSELL`, `CROSS_SELL`. Unknown input resolves to `MANUAL_REVIEW` — the pipeline never hard-fails on an unrecognized goal.

**`audience_selector.py`** — Consumes the structured objective and queries the customer intelligence dataset. Selects a cohort using churn risk, CLV tier, campaign priority, and segment signals. Provides a human-readable reason for each customer's inclusion.

**`campaign_planner.py`** — Produces a named campaign specification: campaign type, channel strategy, offer recommendation, and messaging tone. Inputs are the objective and the selected audience.

**`communication_manager.py`** — Generates one communication manifest per customer. Communication identifiers are deterministic within a campaign instance but unique across pipeline runs, allowing repeated demonstrations without duplicate collision.

**`channel_service.py`** — Simulates delivery across EMAIL, SMS, PUSH, and WHATSAPP using a callback-driven event model. Delivery outcomes are deterministic given the communication identifier. Appends lifecycle events (`DISPATCHED`, `DELIVERED`, `OPENED`, `READ`, `CLICKED`, `FAILED`) to the receipt ledger.

**`receipt_api.py`** — Append-only event store. Validates event schemas, persists receipt records, and provides execution-scoped read access to the insights engine. Never mutated after write.

**`insight_engine.py`** — Reads the receipt ledger for a campaign execution and computes four core metrics. Produces explainable next-best-action recommendations aligned to the business rules that generated them.

**`generate_customer_intelligence.py`** — Enriches each synthetic customer with segment, churn risk, CLV tier, recommended offer, preferred channel, campaign priority, recommended campaign type, and a natural-language `decision_reason`. All outputs are deterministic (`RANDOM_SEED = 42`).

**`aether.py`** — Top-level orchestrator. Exposes `run_pipeline(goal: str)` and `build_api_response(results)` as the only public surface Django consumes. Pandas DataFrames remain internal implementation details; Django views never touch raw pipeline data.

---

## Intelligence Layer

The customer intelligence engine runs before any campaign. It enriches every customer with:

| Output | Description |
|---|---|
| `segment` | Behavioral cohort (e.g., High-Value Active, At-Risk, Dormant) |
| `churn_risk` | Scored likelihood of customer disengagement |
| `clv_tier` | HIGH / MEDIUM / LOW — weighted by monetary value, frequency, AOV, orders/month, and tenure |
| `recommended_offer` | Best offer type for this customer |
| `recommended_channel` | Preferred channel derived from engagement signals and payment behaviour |
| `campaign_priority` | Numeric priority score for audience ranking |
| `recommended_campaign_type` | Goal-aligned campaign category |
| `decision_reason` | Natural-language explanation of why these recommendations were made |

**CLV scoring** accounts for lifetime monetary value, purchase frequency, average order value, orders per month, and tenure. Customers with 365+ days tenure receive a loyalty bonus — sustained behaviour is weighted more heavily than short-term spending spikes.

**Channel recommendation hierarchy:** Engagement signals → Historical preferred channel → Payment behaviour → Persona behaviour → Default channel. This respects existing customer behaviour rather than imposing a one-size-fits-all channel.

**Explainability is not optional.** Every recommendation includes a `decision_reason` derived from the same business rules that produced it — not a post-hoc label. This aligns with the principle that marketing teams require transparency and trust in AI-assisted decisions.

---

## Project Structure

```
aether/
├── aether-backend/
│   ├── backend/
│   │   └── api/                        # Django app — models, views, serializers, URLs, tests
│   │       ├── models.py               # CampaignExecution ORM model
│   │       ├── views.py                # Thin DRF views — no business logic
│   │       ├── serializers.py          # Response serialization
│   │       ├── services.py             # Bridge between Django and aether.py
│   │       ├── urls.py                 # URL routing for all endpoints
│   │       ├── admin.py                # Django Admin registration
│   │       └── tests/                 # Dedicated API test suite
│   └── config/                         # Django settings and root URL configuration
│
├── campaign_brain/                     # Autonomous marketing decision-making
│   ├── goal_parser.py                  # Intent extraction from natural language
│   ├── audience_selector.py            # Goal-driven customer cohort selection
│   └── campaign_planner.py             # Campaign manifest generation
│
├── channel_service/                    # Execution simulation layer
│   └── channel_service.py              # Callback-driven multi-channel dispatch
│
├── crm/                                # Communication and receipt management
│   ├── communication_manager.py        # Per-customer communication generation
│   └── receipt_api.py                  # Append-only event ledger
│
├── insight_engine/                     # Post-execution analytics
│   └── insight_engine.py               # Metric computation and recommendations
│
├── intelligence/                       # Customer enrichment pipeline
│   └── generate_customer_intelligence.py
│
├── data_generation/                    # Synthetic dataset pipeline
│   ├── data/                           # Generated CSV outputs
│   ├── generators/                     # Customer, order, and behaviour generators
│   └── utils/
│
├── docs/
│   └── ProjectDecision.md              # Full architectural decision log
│
├── tests/                              # Additional test suites
├── aether.py                           # Standalone CLI + public pipeline entrypoint
└── requirements.txt
```

**Separation of concerns:** `data_generation` creates synthetic datasets. `intelligence` enriches customers. `campaign_brain` makes autonomous decisions. `channel_service` and `crm` handle execution. `insight_engine` handles analytics. Django (`backend/api`) handles delivery only.

---

## Example Workflow

**Goal submitted:** `"Bring back inactive customers"`

**Step 1 — Goal Parser**
Input is normalized. The phrase matches the `REACTIVATION` synonym group. Structured objective: `REACTIVATION`.

**Step 2 — Audience Selector**
Customers are filtered by `segment = Dormant` and `churn_risk = HIGH`. The cohort is ranked by `campaign_priority`. Each selected customer receives a `selection_reason`.

**Step 3 — Campaign Planner**
Output: campaign name `"Reactivation – Win-Back Drive"`, primary channel `EMAIL`, offer type `discount_voucher`, tone `re-engagement`.

**Step 4 — Communication Manager**
One communication record per customer is generated. A unique execution instance ID scopes the identifiers so the pipeline can be run multiple times without duplicate collisions.

**Step 5 — Channel Service**
Each communication is dispatched through the simulated EMAIL channel. Delivery events are appended to the receipt ledger: `DISPATCHED → DELIVERED → OPENED / FAILED`.

**Step 6 — Receipt API**
Events are written to the append-only ledger. Nothing downstream can mutate this record.

**Step 7 — Insights Engine**
Metrics computed from receipts:
```
delivery_rate  = 91.1%
open_rate      = 38.7%
click_rate     = 14.5%
failure_rate   =  8.9%
```
Recommendations generated: `"61.3% of the reactivation cohort did not open. Consider a follow-up SMS for non-openers."`

**Step 8 — Persistence and API**
Execution record persisted to `CampaignExecution`. Immediately retrievable via `GET /api/campaigns/`.

---

## API Reference

All endpoints return JSON. No authentication is required in V1.

---

### `POST /api/run-campaign/`

Execute the full Aether pipeline for a given marketer goal.

**Request**
```json
{
  "goal": "Bring back inactive customers"
}
```

**Response**
```json
{
  "status": "success",
  "campaign": {
    "id": 7,
    "goal": "Bring back inactive customers",
    "objective": "REACTIVATION",
    "campaign_name": "Reactivation – Win-Back Drive",
    "audience_size": 124,
    "communications_generated": 124,
    "receipts_processed": 124,
    "delivery_rate": 91.1,
    "open_rate": 38.7,
    "click_rate": 14.5,
    "failure_rate": 8.9,
    "recommendations": [
      "61.3% of the reactivation cohort did not open. Consider a follow-up SMS for non-openers.",
      "High click rate among female customers aged 25–34. Prioritize this segment in future campaigns."
    ],
    "status": "COMPLETED",
    "started_at": "2026-06-10T18:50:58Z",
    "completed_at": "2026-06-10T18:50:58Z",
    "duration_seconds": 0.43
  }
}
```

**Key fields**

| Field | Type | Description |
|---|---|---|
| `objective` | string | Resolved campaign intent — `REACTIVATION`, `LOYALTY`, `UPSELL`, `CROSS_SELL`, or `MANUAL_REVIEW` |
| `audience_size` | integer | Customers selected for this execution |
| `delivery_rate` | float | `DELIVERED / DISPATCHED × 100` |
| `open_rate` | float | `(OPENED + READ) / DELIVERED × 100` |
| `click_rate` | float | `CLICKED / DELIVERED × 100` |
| `failure_rate` | float | `FAILED / DISPATCHED × 100` |
| `recommendations` | array | Rule-aligned, explainable next-best-action suggestions |
| `status` | string | `COMPLETED`, `FAILED`, or `MANUAL_REVIEW` |

---

### `GET /api/campaigns/`

Retrieve a list of all campaign executions with summary metadata.

**Response**
```json
[
  {
    "id": 7,
    "goal": "Bring back inactive customers",
    "objective": "REACTIVATION",
    "campaign_name": "Reactivation – Win-Back Drive",
    "audience_size": 124,
    "status": "COMPLETED",
    "started_at": "2026-06-10T18:50:58Z"
  },
  {
    "id": 6,
    "goal": "Reward loyal customers",
    "objective": "LOYALTY",
    "campaign_name": "Loyalty Appreciation Campaign",
    "audience_size": 88,
    "status": "COMPLETED",
    "started_at": "2026-06-10T18:45:10Z"
  }
]
```

---

### `GET /api/campaigns/{id}/`

Full execution detail for a single campaign, including analytics and recommendations.

**URL parameter:** `id` — integer campaign execution ID.

**Response**
```json
{
  "id": 7,
  "goal": "Bring back inactive customers",
  "objective": "REACTIVATION",
  "campaign_name": "Reactivation – Win-Back Drive",
  "audience_size": 124,
  "communications_generated": 124,
  "receipts_processed": 124,
  "delivery_rate": 91.1,
  "open_rate": 38.7,
  "click_rate": 14.5,
  "failure_rate": 8.9,
  "recommendations": ["..."],
  "status": "COMPLETED",
  "started_at": "2026-06-10T18:50:58Z",
  "completed_at": "2026-06-10T18:50:58Z",
  "duration_seconds": 0.43
}
```

Returns `404` for non-existent campaign IDs.

---

## Database and Persistence

Campaign executions are persisted in a `CampaignExecution` Django model. Records are written once at pipeline completion and never updated — an append-only audit log pattern.

| Field | Type | Description |
|---|---|---|
| `id` | AutoField | Primary key |
| `goal` | CharField | Raw marketer goal string |
| `objective` | CharField | Resolved structured objective |
| `campaign_name` | CharField | Human-readable campaign name |
| `audience_size` | IntegerField | Customers targeted |
| `communications_generated` | IntegerField | Communications created |
| `receipts_processed` | IntegerField | Receipt events appended |
| `delivery_rate` | FloatField | Delivery success percentage |
| `open_rate` | FloatField | Open/read percentage of delivered |
| `click_rate` | FloatField | Click percentage of delivered |
| `failure_rate` | FloatField | Failure percentage of dispatched |
| `recommendations` | JSONField | List of insight-engine recommendations |
| `status` | CharField | `COMPLETED` / `FAILED` / `MANUAL_REVIEW` |
| `started_at` | DateTimeField | Pipeline start timestamp |
| `completed_at` | DateTimeField | Pipeline completion timestamp |
| `duration_seconds` | FloatField | Wall-clock execution time |

---

## Technical Decisions

The complete decision log is in `docs/ProjectDecision.md`. The decisions most relevant to engineering interviewers are summarized below.

---

### Goal Parser: Rule-Based NLP over LLM APIs

Three approaches were evaluated:

| Option | Verdict | Reason |
|---|---|---|
| Exact phrase matching | ❌ Rejected | Brittle; fails on any phrasing variation |
| Embedding-based semantic matching | ⏳ Deferred | Infrastructure complexity; reduced explainability at this scope |
| Rule-based NLP with synonym expansion | ✅ Accepted | Deterministic, explainable, easy to test and extend |

The accepted approach normalizes text then matches against a phrase/synonym dictionary. A `MANUAL_REVIEW` fallback prevents hard failures on unrecognized input. The architecture is designed so the matching component can be replaced with an embedding-based classifier in a future version without changing any downstream module.

---

### Demo-Safe Campaign Instances

A deterministic communication identifier scheme caused repeated executions of the same goal to generate duplicate IDs, blocking receipt generation. The fix: each pipeline run generates a unique execution instance ID. Communication identifiers are still deterministic *within* a run, preserving reproducibility while enabling repeated demonstrations. This is an explicit tradeoff: identical goals run at different times produce distinct campaign instances.

---

### Django as Delivery Layer Only

Business logic never migrates into Django views. Views call `services.py`, which calls `aether.py`, which orchestrates the pipeline modules. This ensures:

- The pipeline is independently testable without starting Django
- The same pipeline is reusable from the CLI, API, Celery workers, or any future interface
- Framework migrations do not break marketing intelligence

---

### Modular Pipeline with Explicit Non-Responsibilities

Every module documents not only what it does but what it explicitly does not do. The Audience Selector does not interpret goals. The Communication Manager does not deliver messages. The Receipt API does not generate events. These boundaries are enforced at the design level, not just the implementation level.

---

### Immutable Receipt Ledger

The Receipt API is append-only. The Insights Engine is read-only. Execution systems and analytics systems are fully separated — insights can never mutate execution history. This mirrors the pattern used in production event-sourced systems.

---

## Testing

Tests are located in `backend/api/tests/` and cover four areas:

**Goal Parser tests** — Validates that multiple phrasing variants of the same intent map to the correct structured objective. Confirms `MANUAL_REVIEW` is returned (not an exception) for unrecognized input.

**Run Campaign API tests** — Validates successful end-to-end execution via `POST /api/run-campaign/`. Confirms the response includes all required fields and that an execution record is persisted.

**Campaign History API tests** — Validates `GET /api/campaigns/` returns all stored executions with correct field presence.

**Campaign Detail API tests** — Validates `GET /api/campaigns/{id}/` returns full detail for a valid ID. Confirms `404` for non-existent IDs.

```bash
python manage.py test api.tests
```

---

## Installation and Setup

**Requirements:** Python 3.11+

### 1. Clone the repository

```bash
git clone https://github.com/KrishGarg546/Aether-backend.git
cd Aether-backend
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
cd backend
python manage.py migrate
```

### 5. Start the development server

```bash
python manage.py runserver
```
> Run this command from the `backend/` directory.

API available at `http://127.0.0.1:8000/api/`

### 6. Run tests

```bash
python manage.py test api.tests
```

### 7. Run the standalone CLI (optional)

```bash
cd ..
python aether.py
```

You will be prompted for a marketer goal. Press Enter without input to run the default deterministic scenario: `"Reduce churn among inactive premium customers"`.

---

## Roadmap

| Item | Priority | Notes |
|---|---|---|
| React / Next.js frontend dashboard | High | Campaign submission UI, history browser, analytics visualizations |
| Authentication and authorization | High | DRF token auth; multi-user campaign isolation |
| Asynchronous execution | Medium | Celery + Redis for long-running pipelines |
| Real communication provider integrations | Medium | Replace simulation stubs with provider APIs |
| ML-assisted goal understanding | Low | Embedding-based intent classification as optional layer over the deterministic parser |
| Advanced campaign analytics | Low | Segment-level breakdowns, cohort comparisons, time-series trends |

---

## What This Project Demonstrates

Aether was built by a single engineer to production standards. It is designed to be read, run, explained, and extended.

| Capability | How Aether shows it |
|---|---|
| **Backend system design** | Clean layered architecture — intelligence, pipeline, API delivery, and persistence as distinct concerns |
| **API development** | Production-style REST endpoints with Django REST Framework; serialized responses; clean URL routing |
| **Modular software architecture** | Independent pipeline stages with single-responsibility contracts; no business logic in views |
| **Data processing pipelines** | End-to-end data flow from raw synthetic customer data through enrichment, segmentation, campaign execution, receipt processing, and insight derivation |
| **Product-oriented thinking** | Designed around a marketer's workflow rather than a data scientist's notebook |
| **Translating business goals into executable workflows** | The core capability — turning a natural-language intent into a measurable campaign outcome |
| **Engineering discipline** | Type hints, validation layers, documented decision log, deterministic behaviour, append-only persistence |

## Results

- Backend validation completed successfully.
- 11/11 API and pipeline tests passing.
- End-to-end campaign execution verified.
- Campaign persistence and retrieval confirmed.
- Goal parser fallback behavior validated.
- Campaign detail and history endpoints validated.

---

<p align="center">
  <sub>Built by Krish Garg • Backend V1 • Developed for the Xeno Software Engineering Challenge</sub>
</p>
