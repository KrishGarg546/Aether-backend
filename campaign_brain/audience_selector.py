"""
campaign_brain/audience_selector.py
====================================
Aether CRM – Audience Selector
--------------------------------
Responsible for one thing: given a parsed marketing goal and the
customer-intelligence dataset, return a deterministic, rule-based
audience that best matches that goal.

Supports goal types:
    REACTIVATION
    RETENTION
    UPSELL
    CROSS_SELL
    LOYALTY

Unsupported goals raise ValueError.

Usage
-----
Run as a standalone script (demo mode):

    python campaign_brain/audience_selector.py

Or import and call programmatically:

    from campaign_brain.audience_selector import select_audience, load_customer_intelligence
    df = load_customer_intelligence()
    result = select_audience(parsed_goal, max_customers=500)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the customer-intelligence CSV, relative to project root.
# Override via the AETHER_CUSTOMER_INTELLIGENCE_PATH environment variable.
DEFAULT_DATA_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data_generation",
    "data",
    "customer_intelligence.csv",
)

# Ordered priority values used for sorting (lower index = higher priority).
PRIORITY_ORDER: list[str] = ["HIGH", "MEDIUM", "LOW"]

# Required columns that must exist in the CSV.
REQUIRED_COLUMNS: set[str] = {
    "customer_id",
    "segment",
    "churn_risk",
    "clv_tier",
    "recommended_offer",
    "recommended_channel",
    "campaign_priority",
    "recommended_campaign_type",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_customer_intelligence(path: str | None = None) -> pd.DataFrame:
    """Load and validate the customer-intelligence dataset.

    Parameters
    ----------
    path:
        Absolute or relative path to the CSV file.  When ``None`` the
        function first checks the ``AETHER_CUSTOMER_INTELLIGENCE_PATH``
        environment variable and then falls back to
        ``DEFAULT_DATA_PATH``.

    Returns
    -------
    pd.DataFrame
        A clean dataframe with string columns upper-cased where needed,
        duplicate customer IDs removed, and no leading/trailing
        whitespace in string fields.

    Raises
    ------
    FileNotFoundError
        If the resolved path does not exist.
    ValueError
        If required columns are missing or the dataframe is empty after
        deduplication.
    """
    resolved_path: str = (
        path
        or os.environ.get("AETHER_CUSTOMER_INTELLIGENCE_PATH", "")
        or DEFAULT_DATA_PATH
    )

    if not os.path.isfile(resolved_path):
        raise FileNotFoundError(
            f"Customer-intelligence file not found at: {resolved_path}\n"
            "Set the AETHER_CUSTOMER_INTELLIGENCE_PATH environment variable "
            "or pass an explicit path to load_customer_intelligence()."
        )

    df: pd.DataFrame = pd.read_csv(resolved_path, dtype=str)

    # Strip surrounding whitespace from every string cell.
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    # Validate required columns.
    missing_cols: set[str] = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Customer-intelligence CSV is missing required columns: {missing_cols}"
        )

    # Normalise case for categorical columns used in filtering logic.
    for col in ("churn_risk", "clv_tier", "campaign_priority"):
        df[col] = df[col].str.upper()

    # Remove duplicate customer IDs, keeping the first occurrence.
    before_dedup: int = len(df)
    df = df.drop_duplicates(subset=["customer_id"], keep="first").reset_index(drop=True)
    after_dedup: int = len(df)
    if before_dedup != after_dedup:
        print(
            f"[audience_selector] Warning: removed {before_dedup - after_dedup} "
            "duplicate customer_id rows."
        )

    if df.empty:
        raise ValueError(
            "Customer-intelligence dataset is empty after loading and deduplication."
        )

    return df


# ---------------------------------------------------------------------------
# Core selection logic
# ---------------------------------------------------------------------------


def _apply_goal_filter(df: pd.DataFrame, goal_type: str) -> tuple[pd.DataFrame, str]:
    """Apply business-rule filters that correspond to a specific goal type.

    Parameters
    ----------
    df:
        Full (or segment-pre-filtered) customer-intelligence dataframe.
    goal_type:
        Upper-cased goal type string, e.g. ``"REACTIVATION"``.

    Returns
    -------
    filtered_df:
        Subset of ``df`` that matches the goal-type rules.
    reason:
        Human-readable explanation of the filtering logic applied.

    Notes
    -----
    Unknown goal types return the full dataframe with a warning note in
    the reason string so the calling layer is aware, rather than
    silently returning an empty audience.
    """
    normalised: str = goal_type.upper().strip()

    if normalised == "REACTIVATION":
        filtered = df[df["churn_risk"] == "HIGH"].copy()
        reason = (
            "Selected customers with HIGH churn_risk for reactivation. "
            "Audience prioritised by campaign_priority (HIGH → MEDIUM → LOW)."
        )

    elif normalised == "RETENTION":
        filtered = df[
            (df["churn_risk"] == "MEDIUM") & (df["campaign_priority"] != "LOW")
        ].copy()
        reason = (
            "Selected customers with MEDIUM churn_risk for retention, "
            "excluding LOW campaign_priority customers. "
            "Audience prioritised by campaign_priority (HIGH → MEDIUM)."
        )

    elif normalised == "UPSELL":
        filtered = df[df["clv_tier"] == "HIGH"].copy()
        reason = (
            "Selected customers with HIGH clv_tier for upsell opportunities. "
            "Audience prioritised by campaign_priority (HIGH → MEDIUM → LOW)."
        )

    elif normalised == "CROSS_SELL":
        filtered = df[df["clv_tier"].isin(["MEDIUM", "HIGH"])].copy()
        reason = (
            "Selected customers with MEDIUM or HIGH clv_tier for cross-sell. "
            "Audience prioritised by campaign_priority (HIGH → MEDIUM → LOW)."
        )

    elif normalised == "LOYALTY":
        filtered = df[
            (df["churn_risk"] == "LOW") & (df["clv_tier"] == "HIGH")
        ].copy()
        reason = (
            "Selected customers with LOW churn_risk AND HIGH clv_tier for "
            "loyalty reward campaigns. "
            "Audience prioritised by campaign_priority (HIGH → MEDIUM → LOW)."
        )

    else:
        raise ValueError(
    f"Unsupported goal_type '{goal_type}'. "
    "Expected one of: "
    "REACTIVATION, RETENTION, "
    "UPSELL, CROSS_SELL, LOYALTY."
)

    return filtered, reason


def _sort_by_priority(df: pd.DataFrame) -> pd.DataFrame:
    """Sort a dataframe by campaign_priority in HIGH → MEDIUM → LOW order.

    Parameters
    ----------
    df:
        Dataframe containing a ``campaign_priority`` column.

    Returns
    -------
    pd.DataFrame
        Sorted copy of the input dataframe with the index reset.
    """
    priority_cat = pd.Categorical(
        df["campaign_priority"], categories=PRIORITY_ORDER, ordered=True
    )
    df = df.copy()
    df["_priority_sort"] = priority_cat
    df = df.sort_values("_priority_sort").drop(columns=["_priority_sort"])
    return df.reset_index(drop=True)


def _validate_output(
    result: dict[str, Any],
    intelligence_df: pd.DataFrame,
    max_customers: int,
) -> None:
    """Assert all output-contract invariants.

    Parameters
    ----------
    result:
        The dictionary that ``select_audience`` is about to return.
    intelligence_df:
        The source dataset used for selection (used to verify customer
        existence).
    max_customers:
        The cap that was in effect during selection.

    Raises
    ------
    AssertionError
        If any invariant is violated.  Each message identifies which
        contract was broken.
    """
    selected = result["selected_customers"]

    customer_ids = [
        customer["customer_id"]
        for customer in selected
    ]
    audience_size: int = result["audience_size"]

    assert audience_size == len(customer_ids), (
        f"Contract violation: audience_size ({audience_size}) != "
        f"len(selected_customers) ({len(customer_ids)})."
    )

    assert audience_size <= max_customers, (
        f"Contract violation: audience_size ({audience_size}) exceeds "
        f"max_customers ({max_customers})."
    )

    assert len(customer_ids) == len(set(customer_ids)), (
        "Contract violation: selected_customers contains duplicate customer IDs."
    )

    known_ids: set[str] = set(intelligence_df["customer_id"].tolist())
    unknown: set[str] = set(customer_ids) - known_ids
    assert not unknown, (
        f"Contract violation: {len(unknown)} selected customer(s) not found "
        f"in the intelligence dataset: {list(unknown)[:5]}{'...' if len(unknown) > 5 else ''}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_audience(
    parsed_goal: dict[str, Any],
    max_customers: int = 500,
    data_path: str | None = None,
) -> dict[str, Any]:
    """Select the best-fit audience for a parsed marketing goal.

    This is the primary public function of the module.  It is
    deterministic, rule-based, and free of any statistical or ML
    components.

    Parameters
    ----------
    parsed_goal:
        Output dictionary from the Goal Parser.  Expected keys:

        * ``goal_type`` – e.g. ``"REACTIVATION"``, ``"RETENTION"``, etc.
        * ``campaign_objective`` – free-text objective string.
        * ``target_segment`` – segment name or ``"ALL_CUSTOMERS"``.

        Additional keys (``original_goal``, ``success_metric``,
        ``parser_reason``) are accepted and ignored.
    max_customers:
        Upper bound on the number of customers to include in the
        audience.  Defaults to 500.
    data_path:
        Optional override for the CSV file path; passed through to
        :func:`load_customer_intelligence`.

    Returns
    -------
    dict with keys:
        * ``goal_type`` (str) – echoed from the parsed goal.
        * ``campaign_objective`` (str) – echoed from the parsed goal.
        * ``audience_size`` (int) – number of selected customers.
        * ``selected_customers (list[dict]) – ordered list of
          customer IDs (highest priority first).
        * ``segment_distribution`` (dict[str, int]) – count per
          segment value present in the selected audience.
        * ``priority_distribution`` (dict[str, int]) – count per
          campaign_priority value in the selected audience.
        * ``selection_reason`` (str) – plain-English explanation of
          how the audience was built.

    Raises
    ------
    FileNotFoundError
        If the customer-intelligence CSV cannot be found.
    ValueError
        If required CSV columns are absent, or the dataset is empty.
    AssertionError
        If internal output-contract invariants are violated (indicates a
        logic bug).
    """
    if max_customers < 1:
        raise ValueError(f"max_customers must be ≥ 1, got {max_customers}.")

    goal_type: str = parsed_goal.get("goal_type", "UNKNOWN")
    campaign_objective: str = parsed_goal.get("campaign_objective", "")
    target_segment: str = parsed_goal.get("target_segment", "ALL_CUSTOMERS")

    # 1. Load the intelligence dataset.
    intelligence_df: pd.DataFrame = load_customer_intelligence(path=data_path)

    # 2. Optionally restrict to a specific segment.
    if target_segment and target_segment.upper() != "ALL_CUSTOMERS":
        segment_filtered: pd.DataFrame = intelligence_df[
            intelligence_df["segment"] == target_segment
        ]
        if segment_filtered.empty:
            # Fall back to full dataset and note in the reason.
            segment_note: str = (
                f" NOTE: target_segment '{target_segment}' matched no customers; "
                "segment filter was not applied."
            )
            working_df: pd.DataFrame = intelligence_df.copy()
        else:
            segment_note = (
                f" Audience restricted to segment '{target_segment}' "
                f"({len(segment_filtered)} customers before goal filter)."
            )
            working_df = segment_filtered.copy()
    else:
        segment_note = " No segment restriction applied (ALL_CUSTOMERS)."
        working_df = intelligence_df.copy()

    # 3. Apply goal-type business rules.
    goal_filtered: pd.DataFrame
    base_reason: str
    goal_filtered, base_reason = _apply_goal_filter(working_df, goal_type)

    # 4. Sort by campaign priority.
    sorted_df: pd.DataFrame = _sort_by_priority(goal_filtered)

    # 5. Truncate to max_customers.
    final_df: pd.DataFrame = sorted_df.head(max_customers).copy()

    # 6. Build output structures.
    
    priority_score = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    final_df["selection_score"] = (
        final_df["campaign_priority"]
        .map(priority_score)
        .astype(int)
    )
    save_audience(
    final_df[
        [
            "customer_id",
            "selection_score",
            "campaign_priority",
        ]
    ],
    goal_type,
)
    selected_customers = final_df[
    ["customer_id", "selection_score"]
].to_dict(orient="records")
    audience_size: int = len(selected_customers)

    segment_distribution: dict[str, int] = (
        final_df["segment"]
        .value_counts()
        .to_dict()
    )
    priority_distribution: dict[str, int] = (
        final_df["campaign_priority"]
        .value_counts()
        .reindex(PRIORITY_ORDER)
        .dropna()
        .astype(int)
        .to_dict()
    )

    selection_reason: str = (
        f"{base_reason}{segment_note} "
        f"Final audience capped at {max_customers}; "
        f"{audience_size} customers selected."
    )

    result: dict[str, Any] = {
        "goal_type": goal_type,
        "campaign_objective": campaign_objective,
        "audience_size": audience_size,
        "selected_customers": selected_customers,
        "segment_distribution": segment_distribution,
        "priority_distribution": priority_distribution,
        "selection_reason": selection_reason,
    }

    # 7. Validate output contracts.
    _validate_output(result, intelligence_df, max_customers)

    return result

def save_audience(
    audience_df: pd.DataFrame,
    goal_type: str,
) -> None:
    """
    Export audience selection output for downstream modules.
    """

    output_dir = os.path.join(
        os.path.dirname(DEFAULT_DATA_PATH),
        "selected_audiences",
    )

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(
        output_dir,
        f"audience_{goal_type.lower()}.csv",
    )

    audience_df.to_csv(output_path, index=False)

    print(
        f"[audience_selector] Saved audience to: "
        f"{output_path}"
    )
# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(result: dict[str, Any]) -> None:
    """Print a human-readable summary of an audience-selection result.

    Parameters
    ----------
    result:
        Dictionary returned by :func:`select_audience`.
    """
    separator: str = "─" * 60
    print(separator)
    print("  AETHER CRM – Audience Selection Summary")
    print(separator)
    print(f"  Goal Type          : {result['goal_type']}")
    print(f"  Campaign Objective : {result['campaign_objective']}")
    print(f"  Audience Size      : {result['audience_size']:,}")
    print()

    print("  Segment Distribution")
    print("  " + "─" * 40)
    seg_dist: dict[str, int] = result["segment_distribution"]
    if seg_dist:
        max_label_len: int = max(len(k) for k in seg_dist)
        for segment, count in sorted(seg_dist.items(), key=lambda x: -x[1]):
            bar: str = "█" * min(count // max(1, result["audience_size"] // 20), 20)
            print(f"  {segment:<{max_label_len}}  {count:>5,}  {bar}")
    else:
        print("  (no segments)")
    print()

    print("  Priority Distribution")
    print("  " + "─" * 40)
    pri_dist: dict[str, int] = result["priority_distribution"]
    for priority in PRIORITY_ORDER:
        count = pri_dist.get(priority, 0)
        if count:
            print(f"  {priority:<8}  {count:>5,}")
    print()

    print("  Selection Reason")
    print("  " + "─" * 40)
    # Word-wrap the reason at ~56 chars for readability.
    words: list[str] = result["selection_reason"].split()
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
    """Run a demonstration of the audience selector against several goal types.

    Exercises REACTIVATION, RETENTION, UPSELL, CROSS_SELL, and LOYALTY
    scenarios so the module can be validated end-to-end from the command
    line without external dependencies.
    """
    demo_goals: list[dict[str, Any]] = [
        {
            "original_goal": "Win back customers who haven't purchased recently",
            "goal_type": "REACTIVATION",
            "campaign_objective": "Re-engage lapsed customers with a win-back offer",
            "success_metric": "Reactivation rate > 10%",
            "target_segment": "ALL_CUSTOMERS",
            "parser_reason": "Customer inactivity signals high churn risk.",
        },
        {
            "original_goal": "Keep our at-risk customers engaged",
            "goal_type": "RETENTION",
            "campaign_objective": "Reduce churn among medium-risk customers",
            "success_metric": "Churn rate reduction by 15%",
            "target_segment": "ALL_CUSTOMERS",
            "parser_reason": "Medium churn risk cohort needs targeted retention.",
        },
        {
            "original_goal": "Sell premium bundles to high-value buyers",
            "goal_type": "UPSELL",
            "campaign_objective": "Increase average order value among top CLV customers",
            "success_metric": "AOV increase of 20%",
            "target_segment": "ALL_CUSTOMERS",
            "parser_reason": "High CLV customers are most receptive to upsell.",
        },
        {
            "original_goal": "Promote complementary wellness products",
            "goal_type": "CROSS_SELL",
            "campaign_objective": "Introduce mid- and high-value customers to related products",
            "success_metric": "Cross-category purchase rate > 8%",
            "target_segment": "Wellness Advocates",
            "parser_reason": "Wellness segment shows cross-category purchase intent.",
        },
        {
            "original_goal": "Reward our most loyal customers",
            "goal_type": "LOYALTY",
            "campaign_objective": "Drive repeat purchases through exclusive loyalty rewards",
            "success_metric": "Loyalty programme enrolment uplift of 25%",
            "target_segment": "ALL_CUSTOMERS",
            "parser_reason": "Low-churn, high-CLV customers are prime loyalty candidates.",
        },
    ]

    for goal in demo_goals:
        print(f"\n{'=' * 60}")
        print(f"  Running: {goal['goal_type']} | segment: {goal['target_segment']}")
        print("=" * 60)
        try:
            result: dict[str, Any] = select_audience(
                parsed_goal=goal,
                max_customers=500,
            )
            print_summary(result)
            print(
    f"Saved audience with "
    f"{result['audience_size']} customers."
)
        except (FileNotFoundError, ValueError, AssertionError) as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()