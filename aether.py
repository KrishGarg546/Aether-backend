"""
aether.py
=========
Aether: End-to-End Goal-Driven Marketing Execution Pipeline.

Overview
--------
Aether is an AI-native CRM execution engine that transforms a marketer's plain-language
goal into a fully traceable marketing campaign — from audience selection through channel
delivery and measurable insights — without requiring paid infrastructure or external APIs.

Why Aether Exists
-----------------
Modern CRM platforms require marketers to operate disconnected tools: one system for
segmentation, another for campaign planning, a third for delivery, and yet another for
analytics. Aether collapses this fragmentation into a single autonomous pipeline.

A marketer states a business goal (e.g. "Reduce churn among inactive premium customers").
Aether handles everything else:

    Goal Parser          → interprets the goal into a structured campaign intent
    Audience Selector    → identifies which customers to target based on intelligence signals
    Campaign Planner     → constructs a campaign blueprint grounded in audience behaviour
    Communication Manager → generates one deterministic communication record per customer
    Channel Service      → simulates deterministic message delivery across channels
    Receipt API          → persists an immutable append-only event ledger
    Insights Engine      → derives actionable performance recommendations from receipts

Orchestration Philosophy
------------------------
This module is the ONLY place in Aether where all pipeline stages are wired together.
It intentionally contains NO business logic of its own.

The orchestrator's responsibilities are:
  1. Import each pipeline module.
  2. Invoke each stage in the locked sequence.
  3. Pass the output of one stage as input to the next.
  4. Isolate failures so a broken stage does not crash the entire run.
  5. Collect and return a structured result dictionary for every caller.

Why the orchestrator contains no business logic:
  - Business logic belongs inside the module that owns it.
  - The orchestrator must remain stable as individual modules evolve.
  - Keeping aether.py free of domain rules means it never needs to change
    when a campaign strategy or insight threshold is updated.
  - Testability: each module can be tested in isolation; the orchestrator's
    only test is whether it wires modules together correctly.

Determinism
-----------
The orchestrator introduces no randomness. All deterministic guarantees
established by downstream modules (SHA-256-derived IDs, fixed seeds,
reproducible delivery outcomes) are preserved. aether.py calls modules in
a fixed sequence with no conditional branching driven by external state.

Architecture Reference
----------------------
See ProjectDecision.md — "Aether Architecture Decision" (2026-06-10):
    "Aether will be implemented as a goal-driven marketing execution pipeline
     rather than a collection of independent ML components."

Pipeline Order (LOCKED — ProjectDecision.md, 2026-06-10)
---------------------------------------------------------
Goal Parser
  ↓
Audience Selector
  ↓
Campaign Planner
  ↓
Communication Manager
  ↓
Channel Service
  ↓
Receipt API          (owned by Channel Service via receive_callback)
  ↓
Insights Engine
"""

from __future__ import annotations

import sys
import traceback
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Pipeline module imports
#
# Each import is wrapped individually. If a module is unavailable (e.g. its
# dependency CSV does not exist yet, or the package is not on sys.path), the
# import fails silently and the corresponding stage is recorded as None.
# Downstream stages that depend on the missing output are skipped gracefully.
#
# This design means `python aether.py` remains executable at any point during
# development, even before all modules are complete — matching the Step-by-Step
# Development principle documented in ProjectDecision.md §9.
# ---------------------------------------------------------------------------

# Stage 1 — Goal Parser
try:
    from campaign_brain.goal_parser import parse_goal  # type: ignore[import]
    _GOAL_PARSER_AVAILABLE = True
except ImportError:
    try:
        from goal_parser import parse_goal  # type: ignore[import]
        _GOAL_PARSER_AVAILABLE = True
    except ImportError:
        _GOAL_PARSER_AVAILABLE = False
        parse_goal = None  # type: ignore[assignment]

# Stage 2 — Audience Selector
try:
    from campaign_brain.audience_selector import select_audience  # type: ignore[import]
    _AUDIENCE_SELECTOR_AVAILABLE = True
except ImportError:
    try:
        from audience_selector import select_audience  # type: ignore[import]
        _AUDIENCE_SELECTOR_AVAILABLE = True
    except ImportError:
        _AUDIENCE_SELECTOR_AVAILABLE = False
        select_audience = None  # type: ignore[assignment]

# Stage 3 — Campaign Planner
try:
    from campaign_brain.campaign_planner import build_campaign_plan  # type: ignore[import]
    _CAMPAIGN_PLANNER_AVAILABLE = True
except ImportError:
    try:
        from campaign_planner import build_campaign_plan  # type: ignore[import]
        _CAMPAIGN_PLANNER_AVAILABLE = True
    except ImportError:
        _CAMPAIGN_PLANNER_AVAILABLE = False
        build_campaign_plan = None  # type: ignore[assignment]

# Stage 4 — Communication Manager
try:
    from crm.communication_manager import (  # type: ignore[import]
        generate_communications,
        save_communications,
    )
    _COMMUNICATION_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from communication_manager.communication_manager import (  # type: ignore[import]
            generate_communications,
            save_communications,
        )
        _COMMUNICATION_MANAGER_AVAILABLE = True
    except ImportError:
        _COMMUNICATION_MANAGER_AVAILABLE = False
        generate_communications = None  # type: ignore[assignment]
        save_communications = None  # type: ignore[assignment]

# Stage 5 — Channel Service
# The Channel Service also drives Receipt API writes via receive_callback.
# No direct Receipt API import is required at the orchestrator level:
# the Channel Service calls it internally, preserving the separation of
# responsibilities documented in ProjectDecision.md §"Channel Services Separated
# from Campaign Brain".
try:
    from channel_service.channel_service import process_campaign  # type: ignore[import]
    _CHANNEL_SERVICE_AVAILABLE = True
except ImportError:
    try:
        from channel_service import process_campaign  # type: ignore[import]
        _CHANNEL_SERVICE_AVAILABLE = True
    except ImportError:
        _CHANNEL_SERVICE_AVAILABLE = False
        process_campaign = None  # type: ignore[assignment]

# Stage 7 — Insights Engine
# (Stage 6 — Receipt API — is an internal concern of the Channel Service.)
try:
    from insight_engine.insight_engine import (  # type: ignore[import]
        calculate_campaign_metrics,
        calculate_channel_metrics,
        generate_recommendations,
    )
    _INSIGHT_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from insight_engine import (  # type: ignore[import]
            calculate_campaign_metrics,
            calculate_channel_metrics,
            generate_recommendations,
        )
        _INSIGHT_ENGINE_AVAILABLE = True
    except ImportError:
        _INSIGHT_ENGINE_AVAILABLE = False
        calculate_campaign_metrics = None  # type: ignore[assignment]
        calculate_channel_metrics = None  # type: ignore[assignment]
        generate_recommendations = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pipeline stage labels (used in checklist and error reporting)
# ---------------------------------------------------------------------------

_STAGE_LABELS: list[str] = [
    "Goal Parser",
    "Audience Selector",
    "Campaign Planner",
    "Communication Manager",
    "Channel Service",
    "Receipt API",
    "Insights Engine",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_pipeline(goal: str | None = None) -> dict[str, Any]:
    """
    Orchestrate the complete Aether execution pipeline for a marketer goal.

    Accepts a natural-language marketing goal, routes it through each pipeline
    stage in the locked sequence, and returns a structured dictionary containing
    the output of every stage.

    The function is deliberately fault-tolerant: if any stage raises an
    exception, the failure is caught, logged to stderr, and the corresponding
    output key is set to None. Downstream stages that require the missing output
    are skipped, but the pipeline continues to completion for all independent or
    partially dependent stages. This behaviour matches the "Step-by-Step
    Development" principle (ProjectDecision.md §9) and ensures the orchestrator
    remains usable during incremental development.

    Parameters
    ----------
    goal:
        A plain-language marketing objective as a marketer would state it,
        e.g. "Reduce churn among inactive premium customers".

    Returns
    -------
    dict with keys:
        ``goal`` (str)
            The original goal string, echoed verbatim.
        ``parsed_goal`` (dict | None)
            Structured campaign intent produced by the Goal Parser, or None
            if the Goal Parser failed or is unavailable.
        ``audience`` (dict | None)
            Selected audience and selection metadata produced by the Audience
            Selector, or None if the stage failed or was skipped.
        ``campaign`` (dict | None)
            Campaign blueprint produced by the Campaign Planner, or None if
            the stage failed or was skipped.
        ``communications`` (list[dict] | None)
            Ordered list of communication records produced by the Communication
            Manager, or None if the stage failed or was skipped.
        ``receipts`` (pd.DataFrame | None)
            Append-only receipt event log produced by the Channel Service
            (which internally writes through the Receipt API), or None if the
            stage failed or was skipped.
        ``insights`` (dict | None)
            Campaign metrics, channel metrics, and business recommendations
            produced by the Insights Engine, or None if the stage failed or
            was skipped.
        ``stage_status`` (dict[str, str])
            A record of every stage's execution outcome: one of
            "OK", "SKIPPED", "UNAVAILABLE", or "ERROR: <message>".
            Useful for diagnostics and the progress checklist.

    Notes
    -----
    - The orchestrator introduces no randomness. All determinism guarantees
      established by downstream modules are preserved end-to-end.
    - The ``stage_status`` key is not part of the external API contract but is
      included as a first-class output to support dashboard rendering and CI
      validation without requiring callers to re-run the pipeline.
    """
    # Normalize the incoming goal so both the CLI and DRF layer can
    # support reviewer-friendly defaults.
    default_goal: str = "Reduce churn among inactive premium customers"

    normalized_goal: str = (
        goal.strip()
        if isinstance(goal, str) and goal.strip()
        else default_goal
    )
    # Initialise output slots and stage tracking.
    parsed_goal: dict[str, Any] | None = None
    audience: dict[str, Any] | None = None
    campaign: dict[str, Any] | None = None
    communications: list[dict[str, Any]] | None = None
    receipts: pd.DataFrame | None = None
    insights: dict[str, Any] | None = None

    # stage_status maps each stage label to a short outcome string.
    # Populated incrementally as each stage runs.
    stage_status: dict[str, str] = {label: "PENDING" for label in _STAGE_LABELS}

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 1 — Goal Parser
    #
    # Converts the marketer's free-text goal into a structured intent dictionary
    # (goal_type, campaign_objective, success_metric, target_segment).
    # All downstream stages depend on parsed_goal, so a failure here will
    # cascade — but each downstream stage handles None inputs independently.
    # ──────────────────────────────────────────────────────────────────────────
    if not _GOAL_PARSER_AVAILABLE:
        stage_status["Goal Parser"] = "UNAVAILABLE"
        print("[aether] WARNING – Goal Parser module is unavailable.", file=sys.stderr)
    else:
        try:
            parsed_goal = parse_goal(normalized_goal)

            # Temporary compatibility bridge:
            # Goal Parser emits business-oriented goal types (e.g. reduce_churn)
            # while the Audience Selector currently expects execution-oriented
            # campaign categories. Normalize the values here until the contracts
            # are unified across modules.
            if isinstance(parsed_goal, dict):
                goal_type = str(parsed_goal.get("goal_type", "")).lower()

                goal_type_mapping = {
                    "reduce_churn": "REACTIVATION",
                    "increase_retention": "RETENTION",
                    "upsell": "UPSELL",
                    "cross_sell": "CROSS_SELL",
                    "loyalty": "LOYALTY",
                }

                if goal_type in goal_type_mapping:
                    parsed_goal["goal_type"] = goal_type_mapping[goal_type]

            stage_status["Goal Parser"] = "OK"
        except Exception as exc:
            stage_status["Goal Parser"] = f"ERROR: {exc}"
            print(
                f"[aether] ERROR – Goal Parser failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 2 — Audience Selector
    #
    # Uses parsed_goal (goal_type, target_segment) to filter and rank customers
    # from customer_intelligence.csv. Produces a list of selected customers with
    # priority scores, segment distribution, and a plain-English selection reason.
    #
    # Skipped if parsed_goal is unavailable (Goal Parser failed or unknown goal).
    # ──────────────────────────────────────────────────────────────────────────
    if parsed_goal is None:
        stage_status["Audience Selector"] = "SKIPPED"
        print(
            "[aether] SKIPPED – Audience Selector requires parsed_goal.",
            file=sys.stderr,
        )
    elif not _AUDIENCE_SELECTOR_AVAILABLE:
        stage_status["Audience Selector"] = "UNAVAILABLE"
        print("[aether] WARNING – Audience Selector module is unavailable.", file=sys.stderr)
    else:
        try:
            audience = select_audience(parsed_goal)
            stage_status["Audience Selector"] = "OK"
        except Exception as exc:
            stage_status["Audience Selector"] = f"ERROR: {exc}"
            print(
                f"[aether] ERROR – Audience Selector failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 3 — Campaign Planner
    #
    # Combines parsed_goal and the selected audience to build a campaign blueprint:
    # campaign_type, recommended_channel, recommended_offer, message_theme, and
    # a plain-English execution_reason explaining all decisions made.
    #
    # Skipped if either parsed_goal or audience is unavailable.
    # ──────────────────────────────────────────────────────────────────────────
    if parsed_goal is None or audience is None:
        stage_status["Campaign Planner"] = "SKIPPED"
        print(
            "[aether] SKIPPED – Campaign Planner requires parsed_goal and audience.",
            file=sys.stderr,
        )
    elif not _CAMPAIGN_PLANNER_AVAILABLE:
        stage_status["Campaign Planner"] = "UNAVAILABLE"
        print("[aether] WARNING – Campaign Planner module is unavailable.", file=sys.stderr)
    else:
        try:
            campaign = build_campaign_plan(parsed_goal, audience)
            stage_status["Campaign Planner"] = "OK"
        except Exception as exc:
            stage_status["Campaign Planner"] = f"ERROR: {exc}"
            print(
                f"[aether] ERROR – Campaign Planner failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 4 — Communication Manager
    #
    # Generates one deterministic communication record per selected customer.
    # Each record carries a SHA-256-derived communication_id, campaign_id,
    # channel, campaign_type, message theme, and initial status (CREATED).
    # Records are saved to a per-campaign CSV for the Channel Service to consume.
    #
    # Skipped if campaign or audience is unavailable.
    # ──────────────────────────────────────────────────────────────────────────
    if campaign is None or audience is None:
        stage_status["Communication Manager"] = "SKIPPED"
        print(
            "[aether] SKIPPED – Communication Manager requires campaign and audience.",
            file=sys.stderr,
        )
    elif not _COMMUNICATION_MANAGER_AVAILABLE:
        stage_status["Communication Manager"] = "UNAVAILABLE"
        print(
            "[aether] WARNING – Communication Manager module is unavailable.",
            file=sys.stderr,
        )
    else:
        try:
            communications = generate_communications(campaign, audience)
            save_communications(communications, campaign)
            stage_status["Communication Manager"] = "OK"
        except Exception as exc:
            stage_status["Communication Manager"] = f"ERROR: {exc}"
            print(
                f"[aether] ERROR – Communication Manager failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 5 — Channel Service  (also drives Stage 6 — Receipt API internally)
    #
    # Accepts the communication manifest as a DataFrame and simulates deterministic
    # message delivery for each record. For every communication, it:
    #   - emits a DISPATCHED event,
    #   - derives delivery outcome from SHA-256(communication_id),
    #   - emits DELIVERED or FAILED accordingly,
    #   - conditionally emits OPENED/READ and CLICKED engagement events.
    # All events are forwarded to receive_callback() in the Receipt API, which
    # maintains the immutable append-only event ledger.
    #
    # The Receipt API is not called directly from the orchestrator (ProjectDecision.md
    # §"Channel Services Separated from Campaign Brain"). The receipts DataFrame
    # returned by process_campaign() is the observable output of both stages 5 and 6.
    #
    # Skipped if communications is unavailable.
    # ──────────────────────────────────────────────────────────────────────────
    if communications is None:
        stage_status["Channel Service"] = "SKIPPED"
        stage_status["Receipt API"] = "SKIPPED"
        print(
            "[aether] SKIPPED – Channel Service requires communications.",
            file=sys.stderr,
        )
    elif not _CHANNEL_SERVICE_AVAILABLE:
        stage_status["Channel Service"] = "UNAVAILABLE"
        stage_status["Receipt API"] = "UNAVAILABLE"
        print(
            "[aether] WARNING – Channel Service module is unavailable.",
            file=sys.stderr,
        )
    else:
        try:
            # process_campaign() expects a DataFrame, not a list of dicts.
            # The Communication Manager returns list[dict]; convert here so the
            # orchestrator absorbs the transformation without touching either module.
            communications_df: pd.DataFrame = pd.DataFrame(communications)
            receipts = process_campaign(communications_df)
            stage_status["Channel Service"] = "OK"
            # The Receipt API is an internal concern of the Channel Service; its
            # status is reported as OK when Channel Service completes successfully.
            stage_status["Receipt API"] = "OK"
        except Exception as exc:
            stage_status["Channel Service"] = f"ERROR: {exc}"
            stage_status["Receipt API"] = "SKIPPED"
            print(
                f"[aether] ERROR – Channel Service failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 7 — Insights Engine
    #
    # Consumes the immutable receipt log (produced in stages 5–6) to compute:
    #   - campaign-level metrics: delivery_rate, open_rate, click_rate, failure_rate
    #   - channel-level metrics: per-channel breakdown of the same metrics
    #   - recommendations: rule-based business recommendations derived from metrics
    # The Insights Engine is read-only; it never mutates receipts.
    #
    # The communications_df is passed to calculate_channel_metrics() so that
    # channel inference uses the explicit communication_id → channel mapping
    # rather than the COMM-CH-* prefix convention (which applies only to
    # smoke-test IDs). This is the correct path for full-pipeline receipts.
    #
    # Skipped if receipts is None or empty.
    # ──────────────────────────────────────────────────────────────────────────
    if receipts is None or (isinstance(receipts, pd.DataFrame) and receipts.empty):
        stage_status["Insights Engine"] = "SKIPPED"
        print(
            "[aether] SKIPPED – Insights Engine requires a non-empty receipts log.",
            file=sys.stderr,
        )
    elif not _INSIGHT_ENGINE_AVAILABLE:
        stage_status["Insights Engine"] = "UNAVAILABLE"
        print(
            "[aether] WARNING – Insights Engine module is unavailable.",
            file=sys.stderr,
        )
    else:
        try:
            # Build the optional communications lookup DataFrame for channel inference.
            # Only possible if the Communication Manager produced valid output.
            comms_lookup: pd.DataFrame | None = None
            if communications is not None:
                comms_lookup = pd.DataFrame(communications)[
                    ["communication_id", "channel"]
                ]

            campaign_metrics: dict[str, Any] = calculate_campaign_metrics(receipts)

            # Support both Insights Engine signatures during development:
            #   calculate_channel_metrics(receipts)
            #   calculate_channel_metrics(receipts, communications=...)
            try:
                channel_metrics: pd.DataFrame = calculate_channel_metrics(
                    receipts,
                    communications=comms_lookup,
                )
            except TypeError:
                channel_metrics = calculate_channel_metrics(receipts)

            recommendations: list[str] = generate_recommendations(campaign_metrics)

            insights = {
                "campaign_metrics": campaign_metrics,
                "channel_metrics": channel_metrics,
                "recommendations": recommendations,
            }
            stage_status["Insights Engine"] = "OK"
        except Exception as exc:
            stage_status["Insights Engine"] = f"ERROR: {exc}"
            print(
                f"[aether] ERROR – Insights Engine failed: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    # ──────────────────────────────────────────────────────────────────────────
    # Return the fully structured pipeline result.
    #
    # Every key is always present in the returned dictionary regardless of which
    # stages succeeded. Callers can safely access result["insights"] without
    # first checking whether earlier stages completed — a None value signals that
    # the stage did not produce output, not that the key is absent.
    # ──────────────────────────────────────────────────────────────────────────
    return {
        "goal":           normalized_goal,
        "parsed_goal":    parsed_goal,
        "audience":       audience,
        "campaign":       campaign,
        "communications": communications,
        "receipts":       receipts,
        "insights":       insights,
        "stage_status":   stage_status,
    }


# ---------------------------------------------------------------------------
# API response builder for Django/DRF integration
# ---------------------------------------------------------------------------

def build_api_response(results: dict[str, Any]) -> dict[str, Any]:
    """Convert pipeline results into a JSON-serialisable API payload.

    This helper is intended for Django/DRF integration. It extracts the
    high-level outputs marketers care about while avoiding direct exposure
    of pandas DataFrames through the API layer.
    """
    parsed_goal = results.get("parsed_goal") or {}
    audience = results.get("audience") or {}
    campaign = results.get("campaign") or {}
    communications = results.get("communications") or []
    receipts = results.get("receipts")
    insights = results.get("insights") or {}

    receipt_count = 0
    if isinstance(receipts, pd.DataFrame):
        receipt_count = len(receipts)

    recommendations: list[str] = insights.get("recommendations", [])

    return {
        "goal": results.get("goal"),
        "objective": parsed_goal.get("campaign_objective"),
        "audience_size": audience.get("audience_size"),
        "campaign_name": campaign.get("campaign_name"),
        "communications_generated": len(communications),
        "receipt_events_processed": receipt_count,
        "recommendations": recommendations,
        "stage_status": results.get("stage_status", {}),
    }


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_pipeline_summary(results: dict[str, Any]) -> None:
    """
    Print a human-readable summary of a completed pipeline run.

    Extracts and displays the most important figures from each stage output,
    providing a quick at-a-glance view of what the pipeline achieved for the
    given goal.

    Displayed fields:
    - Original goal
    - Parsed campaign objective (from Goal Parser)
    - Audience size (from Audience Selector)
    - Campaign name (from Campaign Planner)
    - Number of communication records generated (from Communication Manager)
    - Number of receipt events processed (from Channel Service / Receipt API)
    - Number of recommendations generated (from Insights Engine)

    All values are extracted defensively: a missing or None stage output
    is reported as "N/A" rather than raising a KeyError or AttributeError.

    Parameters
    ----------
    results:
        Dictionary as returned by ``run_pipeline()``.

    Returns
    -------
    None
        All output is written to stdout.
    """
    bar: str = "─" * 60

    parsed_goal    = results.get("parsed_goal")
    audience       = results.get("audience")
    campaign       = results.get("campaign")
    communications = results.get("communications")
    receipts       = results.get("receipts")
    insights       = results.get("insights")

    # Safely extract values, falling back to "N/A" for any missing stage.
    goal_str: str = results.get("goal", "N/A")

    objective_str: str = (
        parsed_goal.get("campaign_objective", "N/A")
        if isinstance(parsed_goal, dict) else "N/A"
    )

    audience_size_str: str = (
        f"{audience.get('audience_size', 'N/A'):,}"
        if isinstance(audience, dict) else "N/A"
    )

    campaign_name_str: str = (
        campaign.get("campaign_name", "N/A")
        if isinstance(campaign, dict) else "N/A"
    )

    comms_count_str: str = (
        f"{len(communications):,}"
        if isinstance(communications, list) else "N/A"
    )

    receipts_count_str: str = "N/A"
    if isinstance(receipts, pd.DataFrame):
        receipts_count_str = f"{len(receipts):,}"

    rec_count_str: str = "N/A"
    if isinstance(insights, dict):
        recs = insights.get("recommendations")
        if isinstance(recs, list):
            rec_count_str = str(len(recs))

    print(f"\n{'=' * 60}")
    print("  AETHER – Pipeline Execution Summary")
    print(f"{'=' * 60}")
    print(f"\n{bar}")
    print(f"  {'Goal':<34}  {goal_str}")
    print(f"  {'Parsed Objective':<34}  {objective_str}")
    print(f"{bar}")
    print(f"  {'Audience Size':<34}  {audience_size_str} customers")
    print(f"  {'Campaign':<34}  {campaign_name_str}")
    print(f"  {'Communications Generated':<34}  {comms_count_str}")
    print(f"  {'Receipt Events Processed':<34}  {receipts_count_str}")
    print(f"  {'Recommendations Generated':<34}  {rec_count_str}")
    print(f"{bar}")

    # Print recommendations if available, for full insight visibility.
    if isinstance(insights, dict):
        recs = insights.get("recommendations", [])
        if recs:
            print("\n  Recommendations:")
            for i, rec in enumerate(recs, start=1):
                # Wrap long lines at 56 characters for clean terminal output.
                words = rec.split()
                line: list[str] = []
                current_len = 0
                lines_out: list[str] = []
                for word in words:
                    if current_len + len(word) + 1 > 56 and line:
                        lines_out.append(" ".join(line))
                        line = [word]
                        current_len = len(word)
                    else:
                        line.append(word)
                        current_len += len(word) + 1
                if line:
                    lines_out.append(" ".join(line))
                indent = f"  {i}. "
                continuation = "     "
                for j, text_line in enumerate(lines_out):
                    if j == 0:
                        print(f"{indent}{text_line}")
                    else:
                        print(f"{continuation}{text_line}")

    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Execute the Aether pipeline end-to-end and print the results.

    Prints the Aether banner, runs the full pipeline with the demo goal,
    displays a per-stage progress checklist, and then prints the final
    pipeline summary.

    This function is the canonical demonstration entry point. It is
    not part of the public API contract; callers should use run_pipeline()
    directly when integrating Aether into a larger system.
    """
    # ── Banner ────────────────────────────────────────────────────────────────
    banner = r"""
     ___        _   _               _
    / _ \ _   _| |_| |__   ___   __| |___
   | | | | | | | __| '_ \ / _ \ / _` / __|
   | |_| | |_| | |_| | | | (_) | (_| \__ \
    \__\_\\__,_|\__|_| |_|\___/ \__,_|___/
    """
    print(banner)
    print("AETHER: End-to-End Goal-Driven Marketing Execution Pipeline")
    print("=" * 60)

    # Allow reviewers to provide their own marketing goal while preserving
    # a deterministic fallback scenario for demonstrations.
    default_goal: str = "Reduce churn among inactive premium customers"

    print("\nEnter a marketing goal (press Enter to use the demo goal).")
    user_goal: str = input(
        f"Goal [{default_goal}]: "
    ).strip()

    demo_goal: str = user_goal or default_goal

    print(f"\nGoal: {demo_goal}\n")

    # ── Execute ───────────────────────────────────────────────────────────────
    results: dict[str, Any] = run_pipeline(demo_goal)

    # ── Progress checklist ────────────────────────────────────────────────────
    # Displays each stage with its execution outcome, making it easy to see
    # at a glance which stages completed, which were skipped, and which failed.
    print("\nPipeline Progress Checklist:")
    print("─" * 40)

    stage_status: dict[str, str] = results.get("stage_status", {})

    for label in _STAGE_LABELS:
        status: str = stage_status.get(label, "UNKNOWN")

        if status == "OK":
            marker = "✓  OK      "
        elif status == "SKIPPED":
            marker = "–  SKIPPED "
        elif status == "UNAVAILABLE":
            marker = "?  UNAVAIL "
        elif status.startswith("ERROR"):
            marker = "✗  FAILED  "
        else:
            marker = "…  PENDING "

        print(f"  [{marker}] {label}")
        if status.startswith("ERROR"):
            # Print the error message indented, for immediate visibility.
            print(f"             {status}")

    # ── Final summary ─────────────────────────────────────────────────────────
    print_pipeline_summary(results)


if __name__ == "__main__":
    main()