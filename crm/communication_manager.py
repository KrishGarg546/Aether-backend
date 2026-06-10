"""
crm/communication_manager.py
==============================
Aether CRM – Communication Manager
------------------------------------
Responsible for one thing: given a campaign plan (from campaign_planner.py)
and an audience result (from audience_selector.py), generate one deterministic
communication record per selected customer and export them to CSV for
downstream consumption by the Channel Service.

This module sits at the boundary between campaign decision-making and channel
execution.  It does NOT deliver messages — that is the Channel Service's
responsibility.  It produces a communication manifest that the Channel Service
reads and acts upon.

Pipeline position
-----------------
Goal Parser
  ↓
Audience Selector
  ↓
Campaign Planner
  ↓
Communication Manager  ← THIS MODULE
  ↓
Channel Service
  ↓
Receipt API
  ↓
Insights

Communication lifecycle
-----------------------
Every communication record begins in CREATED status with retry_count = 0.
The Channel Service is responsible for transitioning records through:

    CREATED → DISPATCHED → DELIVERED | FAILED → (RETRY → DELIVERED | FAILED)

Callback events emitted by the Channel Service extend the lifecycle further:

    DISPATCHED → OPENED   (recipient opened the message)
    DISPATCHED → READ     (recipient read the full message)
    DISPATCHED → CLICKED  (recipient clicked a call-to-action link)

These states are owned and written exclusively by the Channel Service and
Receipt API.  This module owns only the CREATED state.

Output naming
-------------
Each campaign produces its own CSV file named after the campaign ID:

    communications_<campaign_id>.csv

This prevents campaigns from overwriting each other and allows the
Channel Service to load the exact manifest for a given campaign_id.

Determinism guarantee
---------------------
communication_id and campaign_id are both derived from inputs via SHA-256
hashing, meaning identical inputs always produce identical IDs regardless
of when or where the module is executed.

Usage
-----
Run as a standalone script (demo / smoke-test mode):

    python crm/communication_manager.py

Or import and call programmatically:

    from crm.communication_manager import generate_communications, save_communications

    records = generate_communications(campaign_plan, audience_result)
    save_communications(records, campaign_plan)
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Output directory for communications CSVs, relative to project root.
# Override via the AETHER_COMMUNICATIONS_DIR environment variable.
DEFAULT_OUTPUT_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data_generation",
    "data",
)

# Output filename template.  The campaign_id is interpolated at save time so
# each campaign writes its own file instead of overwriting a shared one.
# Example: communications_CAMP-3A9F12E0B4C71D58.csv
COMMUNICATIONS_FILENAME_TEMPLATE: str = "communications_{campaign_id}.csv"

# Communication status at creation time.
INITIAL_STATUS: str = "CREATED"

# Retry count at creation time.
INITIAL_RETRY_COUNT: int = 0

# Canonical column order for the output CSV.
# ``message`` is included so the Channel Service send API receives
# recipient, message, and channel from a single row with no additional
# lookups required.
COMMUNICATION_COLUMNS: list[str] = [
    "communication_id",
    "campaign_id",
    "customer_id",
    "channel",
    "campaign_type",
    "message",
    "status",
    "retry_count",
    "created_at",
]

# Required keys that must be present in the campaign_plan dict.
REQUIRED_PLAN_KEYS: set[str] = {
    "goal_type",
    "campaign_type",
    "recommended_channel",
    "recommended_offer",
    "message_theme",
    "audience_size",
}

# Required keys that must be present in the audience_result dict.
REQUIRED_AUDIENCE_KEYS: set[str] = {
    "goal_type",
    "audience_size",
    "selected_customers",
}


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def generate_campaign_id(campaign_plan: dict[str, Any]) -> str:
    """Generate a deterministic campaign ID from the campaign plan.

    The ID is derived by hashing a stable composite key built from
    goal_type and campaign_type.  This guarantees that the same plan
    always produces the same campaign_id, regardless of execution time
    or environment.

    Parameters
    ----------
    campaign_plan:
        Output dictionary from ``campaign_planner.build_campaign_plan()``.
        Must contain at minimum ``goal_type`` and ``campaign_type`` keys.

    Returns
    -------
    str
        A 16-character uppercase hexadecimal string prefixed with ``CAMP-``.
        Example: ``CAMP-3A9F12E0B4C71D58``

    Notes
    -----
    The hash incorporates goal_type and campaign_type only — fields that
    are structurally stable across a campaign's lifetime.  Time-varying
    fields such as audience_size are intentionally excluded to keep the
    ID stable across partial re-runs or audience adjustments.
    """
    goal_type: str = campaign_plan.get("goal_type", "UNKNOWN").upper().strip()
    campaign_type: str = campaign_plan.get("campaign_type", "UNKNOWN").upper().strip()

    composite_key: str = f"AETHER|CAMPAIGN|{goal_type}|{campaign_type}"
    digest: str = hashlib.sha256(composite_key.encode("utf-8")).hexdigest()

    # Take the first 16 hex characters for a compact but collision-resistant ID.
    return f"CAMP-{digest[:16].upper()}"


def _generate_communication_id(
    campaign_id: str,
    customer_id: str,
) -> str:
    """Generate a deterministic communication ID for a single customer.

    The ID is derived by hashing the campaign_id and customer_id together.
    This ensures that the same campaign–customer pair always produces the
    same communication_id, which is critical for idempotent re-runs and
    deduplication at the Channel Service layer.

    Parameters
    ----------
    campaign_id:
        The campaign ID as returned by :func:`generate_campaign_id`.
    customer_id:
        The unique customer identifier string.

    Returns
    -------
    str
        A 20-character uppercase hexadecimal string prefixed with ``COMM-``.
        Example: ``COMM-7B2E4F91A03CD856E120``
    """
    composite_key: str = f"AETHER|COMMUNICATION|{campaign_id}|{customer_id}"
    digest: str = hashlib.sha256(composite_key.encode("utf-8")).hexdigest()

    return f"COMM-{digest[:20].upper()}"


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------


def _extract_customer_ids(audience_result: dict[str, Any]) -> list[str]:
    """Extract a flat list of customer IDs from an audience result.

    The audience_selector module emits ``selected_customers`` in two
    possible shapes depending on the call path:

    * ``list[str]`` — plain customer IDs (older API).
    * ``list[dict]`` — each dict containing at least ``"customer_id"``
      (the enriched format produced by current audience_selector versions).

    This function normalises both shapes into a flat ``list[str]``.

    Parameters
    ----------
    audience_result:
        Output dictionary from ``audience_selector.select_audience()``.

    Returns
    -------
    list[str]
        Ordered list of customer ID strings.

    Raises
    ------
    ValueError
        If ``selected_customers`` is missing, empty, or contains an
        unrecognised element type.
    """
    raw: Any = audience_result.get("selected_customers")

    if not raw:
        raise ValueError(
            "audience_result['selected_customers'] is missing or empty. "
            "Ensure audience_selector has been run successfully before "
            "calling generate_communications()."
        )

    customer_ids: list[str] = []

    for item in raw:
        if isinstance(item, str):
            customer_ids.append(item.strip())
        elif isinstance(item, dict):
            cid: str | None = item.get("customer_id")
            if not cid:
                raise ValueError(
                    f"A customer entry in selected_customers is missing "
                    f"'customer_id': {item}"
                )
            customer_ids.append(str(cid).strip())
        else:
            raise ValueError(
                f"Unexpected element type in selected_customers: "
                f"{type(item).__name__}.  Expected str or dict."
            )

    return customer_ids


def generate_communications(
    campaign_plan: dict[str, Any],
    audience_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate one communication record per selected customer.

    Produces a deterministic list of communication dictionaries ready for
    export to CSV and subsequent consumption by the Channel Service.

    All records are initialised with status=CREATED and retry_count=0.
    The created_at timestamp is captured once at call-time and shared
    across all records in the batch, so every communication in the same
    run carries an identical timestamp.  This is intentional: the
    timestamp reflects when the batch was created, not individual
    processing latency.

    Parameters
    ----------
    campaign_plan:
        Output dictionary from ``campaign_planner.build_campaign_plan()``.
        Must contain: goal_type, campaign_type, recommended_channel,
        audience_size.

    audience_result:
        Output dictionary from ``audience_selector.select_audience()``.
        Must contain: goal_type, audience_size, selected_customers.

    Returns
    -------
    list[dict[str, Any]]
        Ordered list of communication record dicts, one per customer.
        Each dict contains all fields defined in ``COMMUNICATION_COLUMNS``.

    Raises
    ------
    ValueError
        If required keys are missing from either input, if the audience
        is empty, or if goal_type values disagree between plan and audience.
    """
    # ------------------------------------------------------------------
    # 1. Validate inputs.
    # ------------------------------------------------------------------

    missing_plan_keys: set[str] = REQUIRED_PLAN_KEYS - set(campaign_plan.keys())
    if missing_plan_keys:
        raise ValueError(
            f"campaign_plan is missing required keys: {missing_plan_keys}"
        )

    missing_audience_keys: set[str] = REQUIRED_AUDIENCE_KEYS - set(audience_result.keys())
    if missing_audience_keys:
        raise ValueError(
            f"audience_result is missing required keys: {missing_audience_keys}"
        )

    plan_goal: str = str(campaign_plan.get("goal_type", "")).upper().strip()
    audience_goal: str = str(audience_result.get("goal_type", "")).upper().strip()
    if plan_goal != audience_goal:
        raise ValueError(
            f"goal_type mismatch: campaign_plan has '{plan_goal}' but "
            f"audience_result has '{audience_goal}'.  "
            "Both inputs must originate from the same goal."
        )

    # ------------------------------------------------------------------
    # 2. Extract fields from inputs.
    # ------------------------------------------------------------------

    campaign_type: str = str(campaign_plan.get("campaign_type", "UNKNOWN")).upper().strip()

    # Channel: use per-customer recommended_channel if available from the
    # plan's customer-level breakdown; fall back to the plan-level channel.
    # In V1 we use a single channel per campaign (plan-level).
    channel: str = str(campaign_plan.get("recommended_channel", "EMAIL")).upper().strip()

    customer_ids: list[str] = _extract_customer_ids(audience_result)

    if not customer_ids:
        raise ValueError(
            "No customers found in audience_result['selected_customers']. "
            "Cannot generate communications for an empty audience."
        )

    # ------------------------------------------------------------------
    # 3. Generate stable identifiers.
    # ------------------------------------------------------------------

    campaign_id: str = generate_campaign_id(campaign_plan)

    # Capture batch creation time once — all records share this timestamp.
    created_at: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    message: str = (
    f"{campaign_plan['message_theme']} "
    f"Offer: {campaign_plan['recommended_offer']}"
)

    # ------------------------------------------------------------------
    # 4. Build one record per customer.
    # ------------------------------------------------------------------

    records: list[dict[str, Any]] = []

    for customer_id in customer_ids:
        communication_id: str = _generate_communication_id(campaign_id, customer_id)

        record: dict[str, Any] = {
            "communication_id": communication_id,
            "campaign_id":      campaign_id,
            "customer_id":      customer_id,
            "channel":          channel,
            "campaign_type":    campaign_type,
            "message":          message,
            "status":           INITIAL_STATUS,
            "retry_count":      INITIAL_RETRY_COUNT,
            "created_at":       created_at,
        }

        records.append(record)

    return records


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_output(
    records: list[dict[str, Any]],
    audience_result: dict[str, Any],
) -> None:
    """Validate the generated communication records against contract rules.

    Verifies the following invariants:

    1. Communication count equals the audience size reported by audience_result.
    2. Every record contains exactly the expected columns.
    3. No duplicate communication_ids exist.
    4. All statuses are CREATED.
    5. All retry_counts are 0.
    6. No customer_id appears more than once (one communication per customer).

    Parameters
    ----------
    records:
        List of communication dicts as returned by
        :func:`generate_communications`.
    audience_result:
        The original audience result dict used to generate the records.
        Used to cross-check the expected audience size.

    Raises
    ------
    AssertionError
        If any validation invariant is violated.  The error message
        identifies which rule failed and provides diagnostic details.
    """
    expected_count: int = int(audience_result.get("audience_size", -1))
    actual_count: int = len(records)

    # Rule 1: communication count must match audience_size.
    assert actual_count == expected_count, (
        f"[validate_output] Communication count mismatch: "
        f"expected {expected_count} (audience_size) "
        f"but generated {actual_count} records."
    )

    df: pd.DataFrame = pd.DataFrame(records)

    # Rule 2: all expected columns must be present.
    missing_cols: set[str] = set(COMMUNICATION_COLUMNS) - set(df.columns)
    assert not missing_cols, (
        f"[validate_output] Generated records are missing columns: {missing_cols}"
    )

    # Rule 3: no duplicate communication_ids.
    duplicate_comm_ids: pd.Series = df["communication_id"][df["communication_id"].duplicated()]
    assert duplicate_comm_ids.empty, (
        f"[validate_output] Duplicate communication_ids detected: "
        f"{duplicate_comm_ids.tolist()}"
    )

    # Rule 4: all statuses must be CREATED.
    non_created: pd.Series = df.loc[df["status"] != INITIAL_STATUS, "status"]
    assert non_created.empty, (
        f"[validate_output] Expected all statuses to be '{INITIAL_STATUS}' "
        f"but found: {non_created.unique().tolist()}"
    )

    # Rule 5: all retry_counts must be 0.
    non_zero_retries: pd.Series = df.loc[df["retry_count"] != INITIAL_RETRY_COUNT, "retry_count"]
    assert non_zero_retries.empty, (
        f"[validate_output] Expected all retry_count values to be "
        f"{INITIAL_RETRY_COUNT} but found non-zero values."
    )

    # Rule 6: one communication per customer (no duplicate customer_ids).
    duplicate_customers: pd.Series = df["customer_id"][df["customer_id"].duplicated()]
    assert duplicate_customers.empty, (
        f"[validate_output] Duplicate customer_ids detected — "
        f"each customer must appear exactly once: "
        f"{duplicate_customers.tolist()}"
    )

    print(
        f"[communication_manager] ✓ Validation passed — "
        f"{actual_count:,} records, all invariants satisfied."
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_communications(
    records: list[dict[str, Any]],
    campaign_plan: dict[str, Any],
    output_dir: str | None = None,
) -> str:
    """Export communication records to a CSV file.

    Writes all records to ``data_generation/data/communications.csv``.
    If the file already exists it is overwritten (last campaign run wins).
    Downstream modules (Channel Service, Insights) should treat this file
    as the authoritative communication manifest for the most recent run.

    Parameters
    ----------
    records:
        List of communication dicts as returned by
        :func:`generate_communications`.
    campaign_plan:
        The campaign plan that generated these records.  Used for
        contextual logging only — no plan fields are written to the CSV.
    output_dir:
        Absolute path to the output directory.  When ``None`` the function
        checks the ``AETHER_COMMUNICATIONS_DIR`` environment variable and
        falls back to ``DEFAULT_OUTPUT_DIR``.

    Returns
    -------
    str
        Absolute path to the written CSV file.

    Raises
    ------
    ValueError
        If ``records`` is empty.
    OSError
        If the output directory cannot be created or the file cannot be
        written.
    """
    if not records:
        raise ValueError(
            "Cannot save an empty communications list.  "
            "Run generate_communications() first."
        )

    resolved_dir: str = (
        output_dir
        or os.environ.get("AETHER_COMMUNICATIONS_DIR", "")
        or DEFAULT_OUTPUT_DIR
    )

    os.makedirs(resolved_dir, exist_ok=True)

    campaign_id: str = generate_campaign_id(campaign_plan)

    filename: str = COMMUNICATIONS_FILENAME_TEMPLATE.format(
        campaign_id=campaign_id
    )

    output_path: str = os.path.join(
        resolved_dir,
        filename,
    )

    df: pd.DataFrame = pd.DataFrame(records, columns=COMMUNICATION_COLUMNS)
    df.to_csv(output_path, index=False)

    campaign_type: str = campaign_plan.get("campaign_type", "UNKNOWN")
    print(
        f"[communication_manager] Saved {len(records):,} communications "
        f"(campaign_type={campaign_type}) → {output_path}"
    )

    return output_path


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(
    records: list[dict[str, Any]],
    campaign_plan: dict[str, Any],
    audience_result: dict[str, Any],
) -> None:
    """Print a human-readable summary of the generated communications.

    Parameters
    ----------
    records:
        List of communication dicts as returned by
        :func:`generate_communications`.
    campaign_plan:
        The campaign plan dict used to generate the communications.
    audience_result:
        The audience result dict used to generate the communications.
    """
    separator: str = "─" * 60

    if not records:
        print(f"{separator}")
        print("  AETHER CRM – Communication Manager Summary")
        print(f"{separator}")
        print("  (no records to summarise)")
        print(separator)
        return

    df: pd.DataFrame = pd.DataFrame(records)

    campaign_id: str  = records[0]["campaign_id"]
    channel: str      = records[0]["channel"]
    campaign_type: str = records[0]["campaign_type"]
    created_at: str   = records[0]["created_at"]

    channel_dist: dict[str, int] = (
        df["channel"].value_counts().to_dict()
    )
    status_dist: dict[str, int] = (
        df["status"].value_counts().to_dict()
    )

    print(separator)
    print("  AETHER CRM – Communication Manager Summary")
    print(separator)
    print(f"  Campaign ID        : {campaign_id}")
    print(f"  Goal Type          : {campaign_plan.get('goal_type', '')}")
    print(f"  Campaign Type      : {campaign_type}")
    print(f"  Channel            : {channel}")
    print(f"  Total Records      : {len(records):,}")
    print(f"  Batch Created At   : {created_at}")
    print()

    print("  Channel Distribution")
    print("  " + "─" * 40)
    if channel_dist:
        max_label_len: int = max(len(k) for k in channel_dist)
        for ch, count in sorted(channel_dist.items(), key=lambda x: -x[1]):
            print(f"  {ch:<{max_label_len}}  {count:>6,}")
    else:
        print("  (none)")
    print()

    print("  Status Distribution")
    print("  " + "─" * 40)
    if status_dist:
        max_label_len = max(len(k) for k in status_dist)
        for status, count in sorted(status_dist.items(), key=lambda x: -x[1]):
            print(f"  {status:<{max_label_len}}  {count:>6,}")
    else:
        print("  (none)")
    print()

    print("  Selection Reason (from Audience Selector)")
    print("  " + "─" * 40)
    reason: str = audience_result.get("selection_reason", "(not provided)")
    words: list[str] = reason.split()
    line: str = "  "
    for word in words:
        if len(line) + len(word) + 1 > 58:
            print(line)
            line = "  " + word
        else:
            line += (" " if line.strip() else "") + word
    if line.strip():
        print(line)

    print(separator)


# ---------------------------------------------------------------------------
# Entry point (demo / smoke-test)
# ---------------------------------------------------------------------------


def main() -> None:
    """Smoke-test all five goal types end-to-end.

    Constructs minimal ``campaign_plan`` and ``audience_result`` inputs
    that mirror what the real Goal Parser → Audience Selector →
    Campaign Planner pipeline would produce, then calls
    :func:`generate_communications`, :func:`validate_output`,
    :func:`save_communications`, and :func:`print_summary` for each.

    The function is entirely self-contained and does not import
    audience_selector or campaign_planner at runtime, keeping the
    module independently runnable during development.

    Note: Because each scenario overwrites the same communications.csv,
    only the final scenario's records will persist after the smoke test.
    In production, campaigns are processed one at a time.
    """

    # ------------------------------------------------------------------
    # Define five representative scenario seeds.
    # ------------------------------------------------------------------

    # Synthetic customer IDs for testing.
    def _fake_customers(prefix: str, n: int) -> list[dict[str, str]]:
        return [{"customer_id": f"{prefix}-{i:04d}"} for i in range(1, n + 1)]

    scenarios: list[dict[str, Any]] = [
        {
            "label": "REACTIVATION",
            "campaign_plan": {
                "goal_type":           "REACTIVATION",
                "campaign_type":       "WIN_BACK",
                "recommended_channel": "EMAIL",
                "recommended_offer":   "15% discount",
                "audience_size":       30,
                "message_theme":       "Reconnect and rediscover value.",
                "execution_reason":    "HIGH churn risk cohort selected for win-back.",
                "success_metric":      "Reactivation rate > 10%",
            },
            "audience_result": {
                "goal_type":           "REACTIVATION",
                "campaign_objective":  "Re-engage lapsed customers",
                "audience_size":       30,
                "selected_customers":  _fake_customers("CUST-REACT", 30),
                "segment_distribution": {"Lapsed Buyers": 30},
                "priority_distribution": {"HIGH": 20, "MEDIUM": 10},
                "selection_reason": (
                    "Selected customers with HIGH churn_risk for reactivation. "
                    "Final audience capped at 500; 30 customers selected."
                ),
            },
        },
        {
            "label": "RETENTION",
            "campaign_plan": {
                "goal_type":           "RETENTION",
                "campaign_type":       "NURTURE",
                "recommended_channel": "WHATSAPP",
                "recommended_offer":   "Exclusive member discount",
                "audience_size":       40,
                "message_theme":       "Continue building long-term relationships.",
                "execution_reason":    "MEDIUM churn risk cohort targeted for retention.",
                "success_metric":      "Churn rate reduction by 15%",
            },
            "audience_result": {
                "goal_type":           "RETENTION",
                "campaign_objective":  "Reduce churn among at-risk customers",
                "audience_size":       40,
                "selected_customers":  _fake_customers("CUST-RETAIN", 40),
                "segment_distribution": {"At-Risk Regulars": 40},
                "priority_distribution": {"HIGH": 15, "MEDIUM": 25},
                "selection_reason": (
                    "Selected MEDIUM churn_risk customers, excluding LOW priority. "
                    "Final audience capped at 500; 40 customers selected."
                ),
            },
        },
        {
            "label": "UPSELL",
            "campaign_plan": {
                "goal_type":           "UPSELL",
                "campaign_type":       "PREMIUM_PROMOTION",
                "recommended_channel": "EMAIL",
                "recommended_offer":   "Premium bundle access",
                "audience_size":       25,
                "message_theme":       "Unlock premium experiences.",
                "execution_reason":    "HIGH CLV customers targeted for upsell.",
                "success_metric":      "AOV increase of 20%",
            },
            "audience_result": {
                "goal_type":           "UPSELL",
                "campaign_objective":  "Increase average order value",
                "audience_size":       25,
                "selected_customers":  _fake_customers("CUST-UPSELL", 25),
                "segment_distribution": {"Power Shoppers": 25},
                "priority_distribution": {"HIGH": 25},
                "selection_reason": (
                    "Selected HIGH clv_tier customers for upsell. "
                    "Final audience capped at 500; 25 customers selected."
                ),
            },
        },
        {
            "label": "CROSS_SELL",
            "campaign_plan": {
                "goal_type":           "CROSS_SELL",
                "campaign_type":       "RECOMMENDATION",
                "recommended_channel": "SMS",
                "recommended_offer":   "Personalised product recommendation",
                "audience_size":       35,
                "message_theme":       "Discover products tailored to your interests.",
                "execution_reason":    "MEDIUM/HIGH CLV customers selected for cross-sell.",
                "success_metric":      "Cross-category purchase rate > 8%",
            },
            "audience_result": {
                "goal_type":           "CROSS_SELL",
                "campaign_objective":  "Drive cross-category discovery",
                "audience_size":       35,
                "selected_customers":  _fake_customers("CUST-XSELL", 35),
                "segment_distribution": {"Wellness Advocates": 20, "Frequent Buyers": 15},
                "priority_distribution": {"HIGH": 20, "MEDIUM": 15},
                "selection_reason": (
                    "Selected MEDIUM or HIGH clv_tier customers for cross-sell. "
                    "Final audience capped at 500; 35 customers selected."
                ),
            },
        },
        {
            "label": "LOYALTY",
            "campaign_plan": {
                "goal_type":           "LOYALTY",
                "campaign_type":       "REWARDS",
                "recommended_channel": "EMAIL",
                "recommended_offer":   "Loyalty reward voucher",
                "audience_size":       20,
                "message_theme":       "Celebrate loyalty with exclusive benefits.",
                "execution_reason":    "LOW churn + HIGH CLV customers rewarded.",
                "success_metric":      "Loyalty programme enrolment uplift of 25%",
            },
            "audience_result": {
                "goal_type":           "LOYALTY",
                "campaign_objective":  "Drive loyalty programme enrolment",
                "audience_size":       20,
                "selected_customers":  _fake_customers("CUST-LOYAL", 20),
                "segment_distribution": {"Brand Champions": 20},
                "priority_distribution": {"HIGH": 20},
                "selection_reason": (
                    "Selected LOW churn_risk AND HIGH clv_tier customers. "
                    "Final audience capped at 500; 20 customers selected."
                ),
            },
        },
    ]

    print("\n" + "=" * 60)
    print("  AETHER CRM – Communication Manager Smoke Test")
    print("=" * 60)

    for scenario in scenarios:
        label: str = scenario["label"]
        campaign_plan: dict[str, Any] = scenario["campaign_plan"]
        audience_result: dict[str, Any] = scenario["audience_result"]

        print(f"\n{'=' * 60}")
        print(f"  Scenario: {label}")
        print("=" * 60)

        try:
            records: list[dict[str, Any]] = generate_communications(
                campaign_plan=campaign_plan,
                audience_result=audience_result,
            )

            validate_output(records=records, audience_result=audience_result)

            saved_path: str = save_communications(
                records=records,
                campaign_plan=campaign_plan,
            )

            print_summary(
                records=records,
                campaign_plan=campaign_plan,
                audience_result=audience_result,
            )

            # Verify the written CSV round-trips correctly.
            df_check: pd.DataFrame = pd.read_csv(saved_path)
            assert len(df_check) == len(records), (
                f"CSV row count {len(df_check)} does not match "
                f"generated record count {len(records)}."
            )
            print(f"  ✓ CSV round-trip verified ({len(df_check):,} rows).")

        except (ValueError, AssertionError, OSError) as exc:
            print(f"  ERROR ({label}): {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()