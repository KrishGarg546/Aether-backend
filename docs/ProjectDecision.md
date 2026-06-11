# Aether CRM — Project Decisions Log

This document records important architectural, technical, and product decisions made during the development of Aether CRM.

The goal is to preserve reasoning behind decisions, maintain consistency as the project evolves, and provide supporting material for evaluations and interviews.

---

# Executive Summary

Aether is a goal-driven AI marketing execution platform designed for the Xeno internship challenge.

Its purpose is to translate marketer objectives into measurable campaign outcomes through a deterministic, explainable, and production-inspired architecture.

Current locked execution pipeline:

Goal Parser
→ Audience Selector
→ Campaign Planner
→ Communication Manager
→ Channel Service
→ Receipt API
→ Insights Engine

Core philosophy:
- Deterministic over stochastic.
- Explainability over complexity.
- Product thinking over isolated ML models.
- Free-tier deployability over infrastructure dependence.
- End-to-end ownership over disconnected components.

---

## Project Vision

The objective is to demonstrate a goal-driven marketing agent that translates marketer intent into measurable campaign outcomes. Rather than showcasing isolated ML models or dashboards, Aether emphasizes autonomous decision-making, execution orchestration, explainability, and product-oriented engineering.

---

# Core Principles

## 1. End-to-End Ownership

Aether should demonstrate the complete workflow:

Synthetic Data Generation
→ Feature Engineering
→ Machine Learning Intelligence
→ Campaign Recommendations
→ Dashboard & User Experience
→ Deployment

The project should feel like a complete product rather than disconnected notebooks.

---

## 2. Free-Tier Deployability

Aether must be deployable without requiring paid infrastructure.

Target deployment stack:

Frontend:
- Next.js
- Vercel Free Tier

Backend:
- Python services
- Serverless-friendly design

Data Storage:
- CSV-based datasets during evaluation
- Lightweight alternatives if persistence becomes necessary

No decision should assume access to paid cloud resources.

---

## 3. Avoid Paid AI Dependencies

The evaluation environment should not require API keys or recurring costs.

Preference order:

1. Classical Machine Learning
2. Rule-based intelligence
3. Local models
4. External AI APIs (only if optional)

All core functionality must work without paid APIs.

---

## 4. AI Should Drive Decisions

AI is not limited to message generation.

Intelligence should support:

- customer segmentation,
- churn prediction,
- customer lifetime value estimation,
- campaign targeting,
- next-best-action recommendations,
- discount sensitivity estimation,
- channel preference prediction.

The system should help marketers decide what to do next.

---

## 5. Explainability Over Complexity

Preference should be given to models that can be explained clearly during evaluation.

Preferred models:

- Random Forest
- Gradient Boosting
- Logistic Regression
- Clustering techniques

Avoid unnecessarily complex approaches that reduce interpretability.

---

## 6. Deterministic Pipelines

Synthetic data generation must remain reproducible.

Standard:

RANDOM_SEED = 42

All generated datasets should be identical across repeated executions.

---

## 7. Story Customers Are Strategic Assets

Story customers exist to improve demonstrations and evaluator understanding.

They should:

- remain identifiable,
- exhibit realistic behaviour,
- produce interpretable analytics patterns.

Story customers should never be removed for convenience.

---

## 8. Production Mindset

Even though this is an evaluation project, code quality should reflect production standards.

Requirements:

- modular design,
- type hints,
- validation layers,
- comprehensive documentation,
- deterministic behaviour,
- clear separation of responsibilities.

---

## 9. Step-by-Step Development

Large changes should be avoided.

Development process:

Implement one improvement
→ validate
→ regenerate outputs
→ confirm correctness
→ proceed

Small validated iterations reduce defects.

---

## 10. Machine Learning Before Generative AI

Predictive intelligence has higher value than text generation.

Priority order:

1. Customer intelligence models
2. Recommendation systems
3. Decision support
4. Campaign generation

Generated text should enhance recommendations rather than replace them.

---

# Current Development Status

## Backend Progress

Completed:

✓ Django Backend Integration
✓ REST API Layer
✓ Campaign Execution Persistence
✓ Campaign History Endpoints
✓ Campaign Detail Endpoints
✓ Django Admin Visibility
✓ Automated Backend Testing
✓ Repository Documentation

Planned:

• React / Next.js Frontend
• Dashboard Experience
• Deployment Pipeline
• Authentication and Authorization
• Final Evaluation Preparation

---

# Feature Engineering Decisions

Implemented improvements:

✓ Zero-order customer recency handling

✓ Empty orders reference-date safety

✓ Story customer flags exported as 0/1

✓ Explicit category tie-breaking logic

Planned improvements:

• orders_per_month feature

---

# Success Criteria

The project succeeds if evaluators can clearly see that Aether:

- understands customers,
- makes intelligent recommendations,
- operates without paid infrastructure,
- is deployable,
- and demonstrates strong engineering discipline.

The objective is not to build the largest system.

The objective is to build the smartest system that can realistically be delivered by one engineer.

## Intelligence Layer Pathing Decision

Date: 2026-06-10

The intelligence layer lives outside the data_generation package.

Reason:
- data_generation is responsible only for synthetic dataset creation.
- intelligence is responsible for customer analysis and decision making.
- This separation mirrors a production architecture:
    Data → Features → Intelligence → Campaign Planning → Channel Execution.

All intelligence scripts should resolve paths relative to PROJECT_ROOT:

PROJECT_ROOT/
    data_generation/data/
    intelligence/

using:

PROJECT_ROOT = Path(__file__).resolve().parent.parent

## Intelligence Layer Decisions (Locked)

Date: June 2026

### Decision 1
Aether will use deterministic business intelligence rules rather than external LLM APIs for customer intelligence generation.

Reason:
Free deployment requirements and evaluator reproducibility.

---

### Decision 2
Customer intelligence outputs must be explainable.

Every major recommendation produced by Aether should include a business reason explaining why the decision was made.

Reason:
Marketing teams require trust and transparency.

---

### Decision 3
Campaign recommendations should balance retention and growth objectives.

Aether must not focus solely on churn prevention. Intelligence should proactively recommend loyalty, cross-sell, upsell, and awareness campaigns.

Reason:
Xeno operates as a shopper engagement platform rather than a reactive CRM.

---

### Decision 4
Story customers represent strategic showcase cohorts.

Story customers receive elevated campaign priority and may receive dedicated campaign strategies.

Reason:
These customers demonstrate Aether's ability to model realistic shopper journeys.

---

### Decision 5
Historical customer communication preferences should influence channel recommendations.

Decision hierarchy:

Engagement Signals
→ Historical Preferred Channel
→ Payment Behaviour
→ Persona Behaviour
→ Default Channel

Reason:
Respecting existing customer behaviour improves campaign effectiveness.

---

Status:
Intelligence Layer Version 1 nearing freeze.
Next phase begins with Goal Interpreter and Campaign Planner development.

### Intelligence Decision — CLV v1

Customer Lifetime Value (CLV) in Aether is determined using a weighted business score based on:

- Monetary value
- Purchase frequency
- Average order value
- Orders per month
- Customer tenure

Long-term customers receive an additional loyalty bonus in CLV scoring.

Reason:
Customers who sustain purchasing behaviour over extended periods represent more reliable lifetime value than recently acquired customers with similar spending patterns.

### Decision: CLV Tiering v1

Status: LOCKED

CLV scoring combines:

- Lifetime monetary value
- Purchase frequency
- Average order value
- Orders per month
- Customer tenure

Long-term customers (365+ days tenure) receive an additional loyalty bonus.

Reason:
Sustained purchasing behaviour is a stronger indicator of customer lifetime value than short-term spending spikes.

Observed distribution:

HIGH   ≈ 33%
MEDIUM ≈ 50%
LOW    ≈ 17%

The distribution was deemed realistic for an FMCG shopper engagement platform.

### Decision: Intelligence Explainability

Status: LOCKED

Every recommendation produced by Aether must include a business explanation.

Aether outputs not only WHAT action should be taken but also WHY that action was selected.

Reason:
Marketing teams require transparency and trust in AI-assisted decision making.

Outcome:
customer_intelligence.csv now contains a decision_reason field for every customer.

### Decision: Explainability Alignment

Status: LOCKED

Decision explanations in Aether must be derived from the same business rules that generated the recommendation itself.

Reason:
Explanations should faithfully represent the underlying intelligence logic to maintain marketer trust and transparency.

Outcome:
Every recommendation produced by Aether is accompanied by a rule-aligned explanation describing why the action was selected.

## Intelligence Layer V1 Finalized

Date: 2026-06-10

Decision:
Aether's customer intelligence engine will remain deterministic and explainable.

Rationale:
The Xeno assignment emphasises decision quality and marketer trust rather than ML sophistication. Rule-based systems provide transparent reasoning, deterministic outputs, and easier debugging.

Implemented Outputs:
- Segment assignment
- Churn risk scoring
- CLV tier estimation
- Recommended offer generation
- Recommended communication channel
- Campaign priority scoring
- Recommended campaign type
- Natural language decision explanations

Architectural Principles:
- One intelligence row per customer
- Fully reproducible outputs
- Human-readable reasoning attached to every recommendation
- Designed to evolve into a goal-driven marketing agent

Status:
LOCKED (V1)

## Intelligence Layer V1 Locked

Date: 2026-06-10

Decision:
Aether will use a deterministic and explainable customer intelligence engine.

Rationale:
The Xeno assignment prioritizes marketer trust and decision quality.
Every recommendation produced by Aether must be explainable.

Principles:
- One intelligence record per customer.
- No black-box ML models in V1.
- Explanations must derive from the same logic used to generate decisions.
- Customer intelligence should support autonomous campaign planning.

Outputs:
- Segment
- Churn Risk
- CLV Tier
- Recommended Offer
- Recommended Channel
- Campaign Priority
- Recommended Campaign Type
- Decision Reason

Status:
LOCKED (V1 COMPLETE)

## Campaign Brain V1 – Goal Parser

Date: 2026-06-10

Decision:
Goals provided by marketers will be transformed into structured campaign intents.

Rationale:
Marketers think in business outcomes, not ML outputs.
Aether should understand goals such as reducing churn or increasing repeat purchases and translate them into actionable campaign plans.

Implementation:
- Rule-based parser.
- Deterministic outputs.
- Supports common marketing objectives.
- Designed to evolve into LLM-assisted parsing in future versions.

Status:
IN PROGRESS


## Goal Parser V1 Locked

Date: 2026-06-10

Decision:
Marketing goals will initially be parsed using deterministic phrase matching.

Rationale:
Marketing objectives are finite and high-impact.
Deterministic parsing maximizes predictability and explainability.

Design Principles:
- No external APIs.
- No LLM dependency.
- Graceful handling of unsupported goals.
- Every parsed goal must include an explanation.

Future Evolution:
Goal Parser V2 may use lightweight ML intent classification.

Status:
LOCKED

## Audience Selection Strategy

Date: 2026-06-10

Decision:
Audience selection will initially use deterministic business rules
derived from customer intelligence outputs.

Rationale:
The intelligence layer already encodes churn risk, CLV,
campaign priority, and segmentation.
Rule-based audience selection maximizes explainability while
demonstrating autonomous decision-making.

Design Principles:
- Goal-driven.
- Explainable.
- Fully deterministic.
- No external APIs.
- No paid services.

Future Evolution:
Audience selection may later incorporate uplift modelling
or propensity scoring.

Status:
LOCKED

## Folder Structure Locked

Date: 2026-06-10

Decision:
The Aether folder structure is now frozen.

Rationale:
Frequent restructuring creates confusion, breaks imports,
and slows development.

Structure Principles:
- data_generation → synthetic data pipelines
- intelligence → customer enrichment pipelines
- campaign_brain → autonomous marketing decision-making
- channel_services → execution stubs
- simulation → campaign outcome estimation
- dashboard → marketer-facing UI
- tests → automated validation
- docs → project documentation

Status:
LOCKED

Audience Selector will not attempt to recover from invalid goals.

Responsibility for unsupported goals lies with Goal Parser.

Status: LOCKED


## Audience Selector V1 Locked

Date: 2026-06-10

Decision:
Audience selection will use deterministic business rules
derived from customer intelligence outputs.

Responsibilities:
- Filter eligible customers.
- Prioritize customers.
- Export audience datasets.
- Provide explainable selection reasons.

Non-responsibilities:
- Goal interpretation.
- Campaign planning.
- Message generation.

Design Principles:
- Deterministic.
- Explainable.
- Goal-driven.
- CSV-first architecture.

Status:
LOCKED


## Decision: Channel Services Separated from Campaign Brain

Date: 2026-06-10

Reason:
Aether distinguishes between decision-making and execution.

The Campaign Brain decides:
- what goal is being pursued,
- which customers should be targeted,
- what campaign strategy should be used.

Channel Services are responsible only for simulating message delivery through different communication channels.

This separation follows the Single Responsibility Principle and makes future integration with real providers easier.

Architecture:

Goal Parser
↓
Audience Selector
↓
Campaign Planner
↓
Channel Router
↓
Email / WhatsApp / SMS / RCS Services
↓
Campaign Executor
↓
Insights

Decision: Model channel delivery as a separate callback-driven service rather than direct delivery methods.

## Campaign Planner V1 Locked

Date: 2026-06-10

Decision:
Campaign planning will transform selected audiences and parsed goals into structured campaign manifests.

Responsibilities:
- Determine campaign type.
- Recommend channel strategy.
- Select offers and messaging themes.
- Generate campaign metadata for downstream execution.

Non-responsibilities:
- Audience selection.
- Communication generation.
- Channel execution.

Design Principles:
- Goal-driven.
- Deterministic.
- Explainable.
- Marketer-centric.

Status:
LOCKED

## Communication Manager V1 Locked

Date: 2026-06-10

Decision:
The Communication Manager is responsible for converting campaign plans into executable communication manifests.

Responsibilities:
- Generate one communication record per customer.
- Produce deterministic communication identifiers.
- Export communications for execution services.
- Preserve campaign traceability.

Non-responsibilities:
- Message delivery.
- Receipt generation.
- Campaign analytics.

Status:
LOCKED

## Channel Service V1 Locked

Date: 2026-06-10

Decision:
Channel execution in Aether will be simulated through a deterministic callback-driven Channel Service.

Rationale:
Real providers are asynchronous and probabilistic. Deterministic simulation preserves reproducibility while demonstrating production-inspired architecture.

Design Principles:
- Append-only event generation.
- Receipt API as the single source of truth.
- Deterministic delivery outcomes derived from communication identifiers.
- Channel-specific engagement behaviour.
- Reproducible smoke tests.

Supported Channels:
- EMAIL
- SMS
- PUSH
- WHATSAPP

Status:
LOCKED

## Receipt API V1 Locked

Date: 2026-06-10

Decision:
The Receipt API serves as Aether's immutable communication event ledger.

Responsibilities:
- Persist lifecycle events.
- Validate event schemas.
- Maintain append-only storage semantics.
- Provide historical execution records.

Non-responsibilities:
- Event generation.
- Campaign analytics.
- Delivery simulation.

Design Principles:
- Append-only architecture.
- Deterministic behaviour.
- CSV-first persistence.
- Framework independence.

Status:
LOCKED

## Insights Engine V1 Locked

Date: 2026-06-10

Decision:
Campaign insights will be generated exclusively from immutable receipt data.

Rationale:
Execution systems and analytics systems should remain separated. Insights must never mutate execution history.

Metric Definitions:
- delivery_rate = DELIVERED / DISPATCHED × 100
- open_rate = (OPENED + READ) / DELIVERED × 100
- click_rate = CLICKED / DELIVERED × 100
- failure_rate = FAILED / DISPATCHED × 100

Design Principles:
- Read-only consumption of receipt logs.
- Deterministic calculations.
- Explainable recommendations.
- Graceful handling of missing data.
- Channel-level and campaign-level reporting.

Status:
LOCKED

## Aether Architecture Decision

Date: 2026-06-10

Decision:
Aether will be implemented as a goal-driven marketing execution pipeline rather than a collection of independent ML components.

Pipeline:
Goal Parser
→ Audience Selector
→ Campaign Planner
→ Communication Manager
→ Channel Service
→ Receipt API
→ Insights Engine

Rationale:
The Xeno assignment evaluates product thinking and engineering execution. Demonstrating autonomous progression from marketer goal to measurable outcomes better reflects Forward Deployed Engineering responsibilities than isolated predictive models.

Status:
LOCKED
# System Freeze Summary (V1)

The following modules are considered architecturally locked:

✓ Intelligence Engine
✓ Goal Parser
✓ Audience Selector
✓ Campaign Planner
✓ Communication Manager
✓ Channel Service
✓ Receipt API
✓ Insights Engine
✓ End-to-End Aether Orchestrator

Future development should prioritize integration rather than redesign.

Next milestone sequence:

1. Django backend completion.
2. Backend repository publication.
3. Comprehensive README creation.
4. React/Next.js frontend implementation.
5. Full-stack deployment.
6. Interview preparation and demonstration polishing.

Status: BACKEND V1 COMPLETE

## Django Integration Strategy (V1)

Date: 2026-06-10

Decision:
Aether will expose its deterministic marketing execution pipeline through a Django REST API.

Rationale:
The Xeno FDA role values product ownership and production-minded engineering. Providing API access demonstrates how Aether could integrate into real-world systems.

Design Principles:
- Existing pipeline modules remain framework-agnostic.
- Django acts as an orchestration and delivery layer.
- aether.py remains executable as a standalone demonstration entrypoint.
- Business logic should never migrate into Django views.
- Views call service functions rather than implementing marketing logic directly.

Initial API Endpoints:
- POST /api/run-campaign/
- GET /api/insights/
- GET /api/campaigns/

Status:
LOCKED

## Aether Public API Boundary (2026-06-10)

Decision:
The orchestrator (aether.py) exposes two public functions:

- run_pipeline(goal)
- build_api_response(results)

Rationale:
Django should consume Aether through a stable interface rather than depending directly on internal pipeline outputs.

Consequences:
- pandas DataFrames remain internal implementation details.
- DRF views remain thin.
- Business logic stays outside Django.
- Future interfaces (CLI, frontend, Celery workers) can reuse the same entrypoints.

Status:
ACCEPTED

## Decision: Goal Parser Strategy (V2)

### Problem

Marketers express identical business objectives using different language patterns. A rigid phrase-to-objective mapping results in poor usability and frequent manual intervention.

Examples:

- "Reduce churn among premium users"
- "Win back inactive customers"
- "Bring back dormant users"

All represent the same business intent.

---

### Alternatives Considered

#### Option 1: Exact Phrase Matching

Pros:
- Simple implementation
- Fully deterministic

Cons:
- Extremely brittle
- Poor marketer experience
- Low real-world applicability

Decision: Rejected.

---

#### Option 2: Embedding-Based Semantic Matching

Pros:
- High flexibility
- Better understanding of natural language

Cons:
- Additional infrastructure complexity
- Increased dependencies
- Reduced explainability
- Harder to evaluate under assignment constraints

Decision: Deferred for future versions.

---

#### Option 3: Rule-Based NLP with Synonym Expansion

Pros:
- Deterministic and explainable
- Handles varied marketer phrasing
- Easy to test and extend
- Appropriate complexity for assignment scope

Cons:
- Requires ongoing synonym maintenance

Decision: Accepted.

---

### Final Architecture

User Goal
→ Text Normalization
→ Phrase/Synonym Matching
→ Structured Objective Mapping
→ Audience Selection
→ Campaign Planning

---

### Future Evolution

Aether may evolve this component into an embedding-based intent classification system once production-scale requirements justify additional complexity.

Current implementation prioritizes transparency, robustness, and interview explainability.

Decision #008 – Goal Parser V2

* Replaced exact phrase matching with rule-based semantic matching.
* Added support for multiple marketer phrasings per objective.
* Introduced text normalization before intent detection.
* Introduced MANUAL_REVIEW fallback instead of pipeline failure.
* Deferred embedding/LLM-based intent classification to future versions.
* Rationale:
    * Deterministic.
    * Explainable.
    * Easy to test.
    * Suitable for assignment scope.
    * Architecturally compatible with future LLM replacement.

## Goal Parser V2 Validation

Date: 2026-06-10

Validation Status: PASSED

Validated Objectives:
- REACTIVATION
- UPSELL
- CROSS_SELL
- LOYALTY

Validation Method:
Standalone parser execution against representative marketer goals.

Observed Outcome:
The parser successfully translated varied marketer language into structured campaign objectives while preserving deterministic behaviour and explainable reasoning.

Decision:
Goal Parser V2 is considered production-ready for assignment scope.

Future Work:
Expand persona vocabulary coverage before introducing ML-based intent classification.

Status:
LOCKED

## Decision: Interactive Goal Input with Deterministic Fallback

Date: 2026-06-10

### Context
Aether originally relied on hardcoded demonstration goals inside
`aether.py`.

While useful during development, this prevented evaluators from
testing arbitrary marketer objectives without modifying source code.

### Decision
Aether will prompt users for a natural-language marketing goal during
CLI execution.

If no goal is supplied, the system will automatically execute a
deterministic default scenario:

    "Reduce churn among inactive premium customers"

### Rationale

Benefits:
- Enables reviewers to explore multiple use cases.
- Demonstrates the goal-driven nature of Aether.
- Preserves reproducible demo behaviour.
- Improves usability without introducing infrastructure complexity.

Tradeoffs:
- CLI execution becomes interactive.
- Automated scripts may require stdin handling.

### Status
ACCEPTED

Decision: Demo-Safe Campaign Execution

Date: 2026-06-10

Context

Aether uses deterministic communication identifiers and an append-only receipt ledger.

Repeated execution of identical campaigns caused duplicate callback detection, preventing downstream insight generation.

Decision

For evaluation environments, each pipeline execution will generate a unique campaign instance identifier.

Communication identifiers remain deterministic within a campaign instance.

Rationale

Benefits:

* Enables repeated demonstrations.
* Preserves immutable receipt history.
* Avoids evaluator confusion.
* Maintains production-inspired behaviour.

Tradeoffs:

* Identical goals executed at different times will produce different campaign instances.

Status

ACCEPTED

## Decision: Demo-Safe Campaign Instances

### Context
Deterministic campaign identifiers caused repeated executions of identical marketer goals to generate duplicate communication identifiers, preventing new receipt generation.

### Decision
Campaigns now generate a unique execution identifier for each pipeline run. Communication identifiers remain deterministic within a campaign instance.

### Rationale
- Supports repeated demonstrations.
- Enables evaluator experimentation.
- Preserves immutable receipt history.
- Maintains production-inspired architecture.

### Tradeoff
Identical goals executed at different times produce distinct campaign instances.

### Status
ACCEPTED

# Backend V1 Completion Summary

Date: 2026-06-10

Status: BACKEND V1 LOCKED

The deterministic Aether backend is considered feature complete for the Xeno evaluation scope.

Implemented Components:
- Goal Parser V2
- Audience Selector V1
- Campaign Planner V1
- Communication Manager V1
- Channel Service V1
- Receipt API V1
- Insights Engine V1
- End-to-End Pipeline Orchestrator
- Django REST Integration
- Campaign Execution Persistence
- Campaign History Endpoints
- Campaign Detail Endpoints
- Django Admin Visibility

Public API Surface:
- POST /api/run-campaign/
- GET /api/campaigns/
- GET /api/campaigns/<id>/

Architectural Principle:
Business logic remains framework-agnostic.
Django serves as an orchestration and delivery layer rather than a location for marketing intelligence.

Evaluation Outcome:
Aether demonstrates end-to-end ownership from marketer goal definition through audience selection, campaign planning, simulated execution, receipt generation, insight production, and historical reporting.

Future Scope (Post-Evaluation):
- Frontend dashboard implementation.
- Authentication and multi-user support.
- Real communication provider integrations.
- Asynchronous task execution.
- ML-assisted intent understanding.
- Advanced campaign analytics.

Status:
LOCKED

# Testing Strategy (V1)

Decision:
The Aether backend should be protected by lightweight automated tests focused on deterministic behaviour and integration stability.

Testing Priorities:
- Goal parser objective mapping.
- Audience selector output validation.
- Campaign planner consistency.
- Communication identifier uniqueness within campaign instances.
- Receipt generation validation.
- Insights engine metric correctness.
- Django API endpoint behaviour.

Rationale:
Assignment evaluation prioritizes reliability and engineering discipline over exhaustive test coverage.

Status:
ACCEPTED

# Repository Publication Checklist

Before repository publication:

- Ensure README accurately reflects final architecture.
- Remove temporary debugging output.
- Confirm requirements.txt is up to date.
- Verify migrations are committed.
- Include API usage examples.
- Include setup instructions for local execution.
- Include screenshots of Django Admin and DRF endpoints.
- Verify all major modules contain docstrings.

Status:
PENDING FINAL REVIEW

# Backend Validation Summary

Date: 2026-06-11

Status: ACCEPTED

Validated Components:
- Goal Parser tests
- Run Campaign API tests
- Campaign History API tests
- Campaign Detail API tests

Outcome:
The Backend V1 implementation passed deterministic validation across the primary marketer workflow. The system successfully demonstrated end-to-end execution from marketer goal interpretation through campaign persistence and historical retrieval.

Decision:
Backend V1 is considered complete for the Xeno evaluation scope. Future effort should prioritize presentation quality, frontend implementation, deployment, and interview preparation rather than backend redesign.

## Product Affinity Engine

### Decision

Implemented affinity-based recommendations using historical co-purchases.

### Alternatives Considered

- Collaborative Filtering
- Matrix Factorization

### Why


Affinity analysis provides explainable recommendations with minimal computational overhead and aligns with the project's goal of delivering actionable marketing intelligence without requiring external ML infrastructure.

---

# Backend Reopening Decision (V2 Intelligence Expansion)

Date: 2026-06-11

Status: ACCEPTED

## Context

Backend V1 had previously been declared feature complete for the Xeno evaluation scope. Subsequent analysis of the generated customer and order datasets revealed an opportunity to significantly strengthen Aether's AI-native positioning without compromising its core architectural principles.

The existing datasets already contained sufficient behavioural information to support higher-order marketing intelligence capabilities.

## Decision

The backend freeze is partially lifted for a tightly scoped Intelligence Expansion Sprint.

Only intelligence-enhancing additions are permitted.

The existing execution pipeline remains architecturally locked:

Goal Parser
→ Audience Selector
→ Campaign Planner
→ Communication Manager
→ Channel Service
→ Receipt API
→ Insights Engine

## Permitted Enhancements

- Product affinity modelling using historical co-purchases.
- Churn risk refinement using behavioural purchase signals.
- Customer health scoring.
- Goal-aligned campaign recommendation improvements.
- Explainable next-best-action intelligence.

## Non-Permitted Changes

- Replacing deterministic systems with opaque models.
- Introducing mandatory paid AI APIs.
- Re-architecting the execution pipeline.
- Migrating business logic into framework layers.
- Expanding scope beyond evaluation constraints.

## Rationale

These enhancements strengthen Aether's ability to behave as an intelligent marketing agent rather than a campaign automation system.

The decision preserves:

- Free-tier deployability.
- Deterministic behaviour.
- Explainability.
- Reproducibility.
- Existing backend investments.

while increasing the system's ability to:

- predict risk,
- recommend products,
- identify opportunities,
- and proactively guide marketers toward effective actions.

## Strategic Principle

Aether should not pursue AI for appearance alone.

Intelligence should be introduced only when it improves marketer decision quality while remaining explainable, affordable, and demonstrably useful.

## Outcome

Backend V2 development focuses on increasing AI nativeness through behavioural intelligence rather than through dependence on external generative services.

This decision represents an evolution of Aether's original philosophy rather than a departure from it.

Decision:
Product intelligence was introduced as an independent intelligence generator rather than extending customer intelligence directly.

Rationale:
Product affinity represents relationships between products rather than attributes of customers. Separating these concerns preserves modularity and allows future intelligence generators to evolve independently.

Product affinity recommendations were enhanced with human-readable metadata because intelligence must be interpretable by marketers, not only machines.

### Product Affinity Explainability

Status: ACCEPTED

Affinity recommendations should include human-readable product metadata rather than exposing only identifiers.

Reason:
Marketing teams act on products, not IDs. Recommendations must remain understandable to non-technical stakeholders.

Outcome:
Product affinity exports include both product identifiers and product names for the source and recommended products.

## Customer Health Engine

Decision:
Implement heuristic customer health scoring.

Alternatives Considered:
- Survival models
- XGBoost churn prediction

Why:
Needed explainable, deployable intelligence capable of prioritizing interventions without introducing opaque ML dependencies.

Outcome:
Aether can proactively identify customers requiring retention efforts and adapt campaign aggressiveness accordingly.

## Decision: Re-open backend to improve AI nativeness

### Context
The original backend focused on audience selection and campaign execution. While functional, it lacked deeper behavioural reasoning.

### Decision
The backend was temporarily reopened to introduce:

- Product Affinity Intelligence
- Customer Health Scoring
- CRM Lifecycle Intelligence
- Story Intelligence
- Personalized Campaign Generation

### Rationale
The goal was to move Aether from a campaign automation system toward an AI-native marketing intelligence platform while remaining fully deterministic and explainable.

### Consequences
Aether can now personalize campaigns using behavioural context, lifecycle stage, engagement health, and inferred customer journeys without relying on paid LLM APIs.