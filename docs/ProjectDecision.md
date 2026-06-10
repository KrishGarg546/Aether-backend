# Aether CRM — Project Decisions Log

This document records important architectural, technical, and product decisions made during the development of Aether CRM.

The goal is to preserve reasoning behind decisions, maintain consistency as the project evolves, and provide supporting material for evaluations and interviews.

---

## Project Vision

Aether CRM is an AI-native CRM platform designed for the Xeno internship challenge.

The objective is not simply to build a dashboard, but to demonstrate how AI can be integrated throughout the CRM lifecycle:

- customer understanding,
- segmentation,
- campaign intelligence,
- next-best-action recommendations,
- and marketing decision support.

The project prioritizes practicality, explainability, and deployability.

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

# Current Pipeline Status

Completed:

✓ generate_products.py

✓ generate_customers.py

✓ generate_story_customers.py

✓ generate_orders.py

✓ generate_customer_features.py

In Progress:

• Customer Intelligence Layer

Planned:

• Churn Prediction

• CLV Estimation

• Next Best Action Engine

• Campaign Recommendation Engine

• Dashboard Integration

• Vercel Deployment

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

## Audience Selector V1 Locked

Date: 2026-06-10

Decision:
Audience selection in Aether will be deterministic and rule-based.

Input:
- Goal Parser output
- customer_intelligence.csv

Output:
- selected_customers
- selection_score
- campaign_priority
- audience CSV exports

Rationale:
Audience selection represents business reasoning rather than prediction.
Deterministic logic improves explainability and aligns with the Xeno challenge.

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