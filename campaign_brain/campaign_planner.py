"""
campaign_brain/campaign_selector.py
=====================================
Aether CRM – Campaign Selector
--------------------------------
Responsible for one thing: given a parsed marketing goal (from
goal_parser.py) and a selected audience (from audience_selector.py),
produce a deterministic, rule-based campaign blueprint ready for
handoff to the Channel Service.

The module derives all variable decisions — channel, offer — from the
intelligence signals already embedded in the customer dataset, so the
plan is always grounded in real audience behaviour rather than generic
defaults.

Pipeline position
-----------------
Goal Parser
  ↓
Audience Selector
  ↓
Campaign Selector  ← THIS MODULE
  ↓
Channel Service
  ↓
Campaign Execution
  ↓
Insights

Usage
-----
Run as a standalone script (demo / smoke-test mode):

    python campaign_brain/campaign_selector.py

Or import and call programmatically:

    from campaign_brain.campaign_selector import build_campaign_plan, print_summary, save_campaign_plan

    plan = build_campaign_plan(parsed_goal, audience_result)
    print_summary(plan)
    save_campaign_plan(plan)
"""

from __future__ import annotations

import json
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

# Directory where JSON campaign plans are written.
DEFAULT_PLANS_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data_generation",
    "data",
    "campaign_plans",
)

# Maps goal_type → internal campaign_type code.
# goal_type values are expected upper-cased (e.g. "REACTIVATION").
# Adding a new goal requires only a new entry here and a matching entry
# in MESSAGE_THEMES.
CAMPAIGN_STRATEGIES: dict[str, str] = {
    "REACTIVATION": "WIN_BACK",
    "RETENTION":    "NURTURE",
    "UPSELL":       "PREMIUM_PROMOTION",
    "CROSS_SELL":   "RECOMMENDATION",
    "LOYALTY":      "REWARDS",
}

# Maps campaign_type code → rule-based message theme.
# Themes are intentionally concise: they anchor copy tone without
# prescribing exact wording — that responsibility belongs to the
# Message Generator downstream.
MESSAGE_THEMES: dict[str, str] = {
    "WIN_BACK":          "Reconnect and rediscover value.",
    "NURTURE":           "Continue building long-term relationships.",
    "PREMIUM_PROMOTION": "Unlock premium experiences.",
    "RECOMMENDATION":    "Discover products tailored to your interests.",
    "REWARDS":           "Celebrate loyalty with exclusive benefits.",
}

# Required columns that must exist in the customer-intelligence CSV.
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

    Mirrors the contract established in ``audience_selector.py`` so
    both modules always operate on identically prepared data regardless
    of entry point.

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

    # Normalise case for categorical columns used in filtering/grouping.
    for col in ("churn_risk", "clv_tier", "campaign_priority"):
        df[col] = df[col].str.upper()

    # Remove duplicate customer IDs, keeping the first occurrence.
    before_dedup: int = len(df)
    df = df.drop_duplicates(subset=["customer_id"], keep="first").reset_index(drop=True)
    after_dedup: int = len(df)
    if before_dedup != after_dedup:
        print(
            f"[campaign_selector] Warning: removed "
            f"{before_dedup - after_dedup} duplicate customer_id rows."
        )

    if df.empty:
        raise ValueError(
            "Customer-intelligence dataset is empty after loading and deduplication."
        )

    return df


# ---------------------------------------------------------------------------
# Audience enrichment
# ---------------------------------------------------------------------------


def get_audience_customers(
    audience_result: dict[str, Any],
    intelligence_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return the intelligence rows that correspond to the selected audience.

    Parameters
    ----------
    audience_result:
        Output dictionary from ``audience_selector.select_audience()``.
        Must contain a ``selected_customers`` key whose value is either:

        * a ``list[str]`` of plain customer IDs, or
        * a ``list[dict]`` each containing at least a ``"customer_id"``
          key (the richer format emitted by some audience_selector
          variants).

    intelligence_df:
        Full customer-intelligence dataframe as returned by
        :func:`load_customer_intelligence`.

    Returns
    -------
    pd.DataFrame
        Subset of ``intelligence_df`` containing only the rows whose
        ``customer_id`` appears in ``selected_customers``, preserving
        the original row order.

    Raises
    ------
    ValueError
        If ``selected_customers`` is empty or if any ID is not found in
        ``intelligence_df`` (upstream contract violation).
    """
    raw_selection: list[Any] = audience_result.get("selected_customers", [])

    if not raw_selection:
        raise ValueError(
            "audience_result['selected_customers'] is empty. "
            "The audience selector must provide at least one customer."
        )

    # Support both plain-string and dict-with-customer_id formats.
    if isinstance(raw_selection[0], dict):
        selected_ids: list[str] = [entry["customer_id"] for entry in raw_selection]
    else:
        selected_ids = [str(cid) for cid in raw_selection]

    known_ids: set[str] = set(intelligence_df["customer_id"].tolist())
    unknown_ids: set[str] = set(selected_ids) - known_ids
    if unknown_ids:
        raise ValueError(
            f"get_audience_customers: {len(unknown_ids)} selected customer(s) "
            f"not found in the intelligence dataset: "
            f"{sorted(unknown_ids)[:5]}"
            f"{'...' if len(unknown_ids) > 5 else ''}"
        )

    audience_df: pd.DataFrame = intelligence_df[
        intelligence_df["customer_id"].isin(set(selected_ids))
    ].copy()

    return audience_df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------


def select_campaign_strategy(goal_type: str) -> str:
    """Map a goal_type to its campaign_type code.

    Parameters
    ----------
    goal_type:
        Upper-cased goal type string, e.g. ``"REACTIVATION"``.  The
        value is normalised (stripped and upper-cased) before lookup so
        minor formatting inconsistencies from the Goal Parser do not
        cause failures.

    Returns
    -------
    str
        The campaign_type code, e.g. ``"WIN_BACK"``.

    Raises
    ------
    ValueError
        If the goal_type is not present in ``CAMPAIGN_STRATEGIES``.
        The planner never silently falls back on an unknown goal —
        that responsibility belongs to the Goal Parser.
    """
    normalised: str = goal_type.strip().upper()
    if normalised not in CAMPAIGN_STRATEGIES:
        supported: str = ", ".join(sorted(CAMPAIGN_STRATEGIES.keys()))
        raise ValueError(
            f"Unsupported goal_type '{goal_type}'. "
            f"Supported values: {supported}. "
            "Ensure the Goal Parser resolves unknown goals before "
            "passing them to the Campaign Selector."
        )
    return CAMPAIGN_STRATEGIES[normalised]


# ---------------------------------------------------------------------------
# Audience-derived decisions
# ---------------------------------------------------------------------------


def _derive_recommended_channel(audience_df: pd.DataFrame) -> str:
    """Return the most common ``recommended_channel`` in the audience.

    Uses ``pandas.Series.mode().iloc[0]`` for deterministic tie-breaking
    (first alphabetically among equally frequent values).

    Parameters
    ----------
    audience_df:
        Dataframe of intelligence rows for the selected audience.

    Returns
    -------
    str
        Modal channel value, e.g. ``"EMAIL"``.

    Raises
    ------
    ValueError
        If the ``recommended_channel`` column is entirely null or
        empty for this audience.
    """
    channel_series: pd.Series = audience_df["recommended_channel"].dropna()
    if channel_series.empty:
        raise ValueError(
            "Cannot derive recommended_channel: "
            "all values are null for the selected audience."
        )
    return str(channel_series.mode().iloc[0])


def _derive_recommended_offer(audience_df: pd.DataFrame) -> str:
    """Return the most common ``recommended_offer`` in the audience.

    Uses ``pandas.Series.mode().iloc[0]`` for deterministic tie-breaking
    (first alphabetically among equally frequent values).

    Parameters
    ----------
    audience_df:
        Dataframe of intelligence rows for the selected audience.

    Returns
    -------
    str
        Modal offer value, e.g. ``"Win-back Discount"``.

    Raises
    ------
    ValueError
        If the ``recommended_offer`` column is entirely null or empty
        for this audience.
    """
    offer_series: pd.Series = audience_df["recommended_offer"].dropna()
    if offer_series.empty:
        raise ValueError(
            "Cannot derive recommended_offer: "
            "all values are null for the selected audience."
        )
    return str(offer_series.mode().iloc[0])


def _derive_message_theme(campaign_type: str) -> str:
    """Return the rule-based message theme for a campaign_type code.

    Parameters
    ----------
    campaign_type:
        Campaign type code, e.g. ``"WIN_BACK"``.

    Returns
    -------
    str
        Message theme sentence.

    Raises
    ------
    ValueError
        If no theme is registered for the given campaign_type.
    """
    if campaign_type not in MESSAGE_THEMES:
        raise ValueError(
            f"No message theme registered for campaign_type '{campaign_type}'. "
            "Update MESSAGE_THEMES to include it."
        )
    return MESSAGE_THEMES[campaign_type]


def _build_execution_reason(
    campaign_type: str,
    goal_type: str,
    channel: str,
    offer: str,
    audience_size: int,
) -> str:
    """Compose a plain-English explanation of all planning decisions.

    The execution reason is mandatory in the output contract. It must
    explain WHAT was decided and WHY, so marketers can audit the plan
    without reading source code.

    Parameters
    ----------
    campaign_type:
        Campaign type code selected by the strategy rules.
    goal_type:
        Original goal type from the parsed goal.
    channel:
        Derived recommended channel.
    offer:
        Derived recommended offer.
    audience_size:
        Number of customers in the selected audience.

    Returns
    -------
    str
        Multi-sentence explanation string.
    """
    return (
        f"Campaign type {campaign_type} selected because the goal_type "
        f"'{goal_type}' maps to this strategy in the Aether campaign rules. "
        f"{channel} chosen as the recommended channel because it was the most "
        f"common preferred channel among the {audience_size:,} selected customers "
        f"in the customer intelligence dataset. "
        f"Offer '{offer}' selected because it was the most frequently "
        f"recommended offer across the target audience."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_campaign_plan(
    parsed_goal: dict[str, Any],
    audience_result: dict[str, Any],
    data_path: str | None = None,
) -> dict[str, Any]:
    """Convert a parsed goal and selected audience into a campaign blueprint.

    This is the primary public function of the module.  It is
    deterministic, rule-based, and free of any statistical or ML
    components.  Every variable field in the output is derived from
    real audience intelligence signals, not hardcoded defaults.

    Parameters
    ----------
    parsed_goal:
        Output dictionary from the Goal Parser.  Required keys:

        * ``goal_type`` – e.g. ``"REACTIVATION"``.
        * ``success_metric`` – echoed verbatim into the output.

        Optional keys (``original_goal``, ``campaign_objective``,
        ``target_segment``, ``parser_reason``) are accepted and ignored.
    audience_result:
        Output dictionary from the Audience Selector.  Required keys:

        * ``selected_customers`` – list of customer ID strings or dicts.
        * ``audience_size`` – integer count (used for reporting).

    data_path:
        Optional override for the customer-intelligence CSV path; passed
        through to :func:`load_customer_intelligence`.

    Returns
    -------
    dict with keys:
        * ``campaign_name`` (str)
        * ``goal_type`` (str)
        * ``campaign_type`` (str)
        * ``recommended_channel`` (str)
        * ``recommended_offer`` (str)
        * ``message_theme`` (str)
        * ``audience_size`` (int)
        * ``success_metric`` (str)
        * ``execution_reason`` (str)

    Raises
    ------
    FileNotFoundError
        If the customer-intelligence CSV cannot be found.
    ValueError
        If the goal_type is unsupported, the audience is empty, or
        derived fields cannot be computed.
    AssertionError
        If internal output-contract invariants are violated (indicates a
        logic bug in this module).
    """
    goal_type: str = parsed_goal.get("goal_type", "UNKNOWN")
    success_metric: str = parsed_goal.get("success_metric") or ""
    audience_size: int = audience_result.get("audience_size", 0)

    # 1. Resolve campaign_type from goal_type (raises ValueError for unknowns).
    campaign_type: str = select_campaign_strategy(goal_type)

    # 2. Load intelligence dataset and narrow to selected audience.
    intelligence_df: pd.DataFrame = load_customer_intelligence(path=data_path)
    audience_df: pd.DataFrame = get_audience_customers(audience_result, intelligence_df)
    assert audience_size == len(audience_df), (
    f"Audience contract violation: "
    f"audience_result reported {audience_size} customers "
    f"but {len(audience_df)} were found."
)

    # 3. Derive audience-grounded decisions.
    recommended_channel: str = _derive_recommended_channel(audience_df)
    recommended_offer: str   = _derive_recommended_offer(audience_df)
    message_theme: str       = _derive_message_theme(campaign_type)

    # 4. Compose execution reason.
    execution_reason: str = _build_execution_reason(
        campaign_type=campaign_type,
        goal_type=goal_type,
        channel=recommended_channel,
        offer=recommended_offer,
        audience_size=len(audience_df),
    )

    # 5. Assemble the plan.
    plan: dict[str, Any] = {
        "campaign_name":       f"Aether {campaign_type} Campaign",
        "goal_type":           goal_type,
        "campaign_type":       campaign_type,
        "recommended_channel": recommended_channel,
        "recommended_offer":   recommended_offer,
        "message_theme":       message_theme,
        "audience_size":       audience_size if audience_size else len(audience_df),
        "success_metric":      success_metric,
        "execution_reason":    execution_reason,
    }

    # 6. Validate all output contracts.
    validate_output(plan)

    return plan


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_output(plan: dict[str, Any]) -> None:
    """Assert all output-contract invariants for a campaign plan.

    Parameters
    ----------
    plan:
        Dictionary produced by :func:`build_campaign_plan`.

    Raises
    ------
    AssertionError
        If any invariant is violated.  Each message identifies which
        contract was broken, making debugging straightforward.
    """
    assert plan.get("campaign_name"), (
        "Contract violation: campaign_name is empty or missing."
    )

    assert plan.get("campaign_type"), (
        "Contract violation: campaign_type is empty or missing."
    )

    assert plan.get("recommended_channel"), (
        "Contract violation: recommended_channel is empty or missing."
    )

    assert plan.get("recommended_offer"), (
        "Contract violation: recommended_offer is empty or missing."
    )

    assert plan.get("message_theme"), (
        "Contract violation: message_theme is empty or missing."
    )

    audience_size: int = plan.get("audience_size", 0)
    assert isinstance(audience_size, int) and audience_size > 0, (
        f"Contract violation: audience_size must be a positive integer, "
        f"got {audience_size!r}."
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_campaign_plan(
    plan: dict[str, Any],
    output_dir: str | None = None,
) -> str:
    """Serialise a campaign plan to a JSON file.

    Parameters
    ----------
    plan:
        Dictionary returned by :func:`build_campaign_plan`.
    output_dir:
        Directory in which to write the file.  Defaults to
        ``DEFAULT_PLANS_DIR``.  Created automatically if absent.

    Returns
    -------
    str
        Resolved absolute path of the written file.

    Raises
    ------
    OSError
        If the output directory cannot be created or the file cannot be
        written.
    """
    resolved_dir: str = output_dir or DEFAULT_PLANS_DIR
    os.makedirs(resolved_dir, exist_ok=True)

    campaign_type: str = plan.get("campaign_type", "unknown")
    filename: str = f"campaign_{campaign_type.lower()}.json"
    output_path: str = os.path.join(resolved_dir, filename)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)

    print(f"[campaign_selector] Plan saved → {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(plan: dict[str, Any]) -> None:
    """Print a human-readable summary of a campaign plan.

    Parameters
    ----------
    plan:
        Dictionary returned by :func:`build_campaign_plan`.
    """
    separator: str = "─" * 60
    print(separator)
    print("  AETHER CRM – Campaign Plan Summary")
    print(separator)
    print(f"  Campaign Name      : {plan.get('campaign_name', '')}")
    print(f"  Goal Type          : {plan.get('goal_type', '')}")
    print(f"  Campaign Type      : {plan.get('campaign_type', '')}")
    print(f"  Recommended Channel: {plan.get('recommended_channel', '')}")
    print(f"  Recommended Offer  : {plan.get('recommended_offer', '')}")
    print(f"  Message Theme      : {plan.get('message_theme', '')}")
    print(f"  Audience Size      : {plan.get('audience_size', 0):,}")
    print(f"  Success Metric     : {plan.get('success_metric', '')}")
    print()

    print("  Execution Reason")
    print("  " + "─" * 40)
    words: list[str] = plan.get("execution_reason", "").split()
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
    """Smoke-test all five supported goal types end-to-end.

    Constructs minimal ``parsed_goal`` and ``audience_result`` inputs
    from real customer IDs in the intelligence dataset, then calls
    :func:`build_campaign_plan`, :func:`print_summary`, and
    :func:`save_campaign_plan` for each scenario.

    The function is self-contained: it does not import audience_selector
    or goal_parser at runtime, keeping the module independently runnable
    during development.
    """
    # Resolve data path so the smoke test works from any working directory.
    data_path: str = (
        os.environ.get("AETHER_CUSTOMER_INTELLIGENCE_PATH", "")
        or DEFAULT_DATA_PATH
    )

    try:
        intel_df: pd.DataFrame = load_customer_intelligence(path=data_path)
    except FileNotFoundError as exc:
        print(f"[campaign_selector] Cannot run smoke tests: {exc}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Define the five scenario seeds.  Each entry mirrors what the real  #
    # Goal Parser + Audience Selector pipeline would produce upstream.   #
    # Customer IDs are sampled from real intelligence data so that       #
    # channel and offer derivation exercises genuine modal logic.        #
    # ------------------------------------------------------------------ #

    def _sample_ids(mask: pd.Series, n: int = 50) -> list[str]:
        """Return up to n customer_ids matching a boolean mask."""
        return intel_df.loc[mask, "customer_id"].head(n).tolist()

    scenarios: list[tuple[dict[str, Any], dict[str, Any]]] = [
        (
            {
                "original_goal":      "Reduce churn among dormant customers",
                "goal_type":          "REACTIVATION",
                "campaign_objective": "reactivation",
                "success_metric": "Reactivation rate > 10%",
                "target_segment":     "ALL_CUSTOMERS",
                "parser_reason":      "Matched goal phrase 'reduce churn'.",
            },
            {
                "goal_type":           "REACTIVATION",
                "campaign_objective":  "reactivation",
                "audience_size":       50,
                "selected_customers":  _sample_ids(intel_df["churn_risk"] == "HIGH"),
                "segment_distribution": {},
                "priority_distribution": {},
                "selection_reason":    "HIGH churn_risk customers selected.",
            },
        ),
        (
            {
                "original_goal":      "Keep at-risk customers engaged",
                "goal_type":          "RETENTION",
                "campaign_objective": "retention",
                "success_metric": "Churn rate reduction by 15%",
                "target_segment":     "ALL_CUSTOMERS",
                "parser_reason":      "Matched goal phrase 'reduce churn'.",
            },
            {
                "goal_type":           "RETENTION",
                "campaign_objective":  "retention",
                "audience_size":       50,
                "selected_customers":  _sample_ids(
                    (intel_df["churn_risk"] == "MEDIUM")
                    & (intel_df["campaign_priority"] != "LOW")
                ),
                "segment_distribution": {},
                "priority_distribution": {},
                "selection_reason":    "MEDIUM churn_risk customers selected.",
            },
        ),
        (
            {
                "original_goal":      "Sell premium bundles to high-value buyers",
                "goal_type":          "UPSELL",
                "campaign_objective": "upsell",
                "success_metric": "AOV increase of 20%",
                "target_segment":     "ALL_CUSTOMERS",
                "parser_reason":      "Matched goal phrase 'increase customer lifetime value'.",
            },
            {
                "goal_type":           "UPSELL",
                "campaign_objective":  "upsell",
                "audience_size":       50,
                "selected_customers":  _sample_ids(intel_df["clv_tier"] == "HIGH"),
                "segment_distribution": {},
                "priority_distribution": {},
                "selection_reason":    "HIGH clv_tier customers selected.",
            },
        ),
        (
            {
                "original_goal":      "Promote complementary wellness products",
                "goal_type":          "CROSS_SELL",
                "campaign_objective": "cross_sell",
                "success_metric": "Cross-category purchase rate > 8%",
                "target_segment":     "ALL_CUSTOMERS",
                "parser_reason":      "Matched goal phrase 'increase repeat purchases'.",
            },
            {
                "goal_type":           "CROSS_SELL",
                "campaign_objective":  "cross_sell",
                "audience_size":       50,
                "selected_customers":  _sample_ids(
                    intel_df["clv_tier"].isin(["MEDIUM", "HIGH"])
                ),
                "segment_distribution": {},
                "priority_distribution": {},
                "selection_reason":    "MEDIUM and HIGH clv_tier customers selected.",
            },
        ),
        (
            {
                "original_goal":      "Reward our most loyal customers",
                "goal_type":          "LOYALTY",
                "campaign_objective": "loyalty",
                "success_metric": "Loyalty programme enrolment uplift of 25%",
                "target_segment":     "ALL_CUSTOMERS",
                "parser_reason":      "Matched goal phrase 'reward loyal customers'.",
            },
            {
                "goal_type":           "LOYALTY",
                "campaign_objective":  "loyalty",
                "audience_size":       50,
                "selected_customers":  _sample_ids(
                    (intel_df["churn_risk"] == "LOW")
                    & (intel_df["clv_tier"] == "HIGH")
                ),
                "segment_distribution": {},
                "priority_distribution": {},
                "selection_reason":    "LOW churn_risk AND HIGH clv_tier customers selected.",
            },
        ),
    ]

    for parsed_goal, audience_result in scenarios:
        goal_type: str = parsed_goal["goal_type"]
        print(f"\n{'=' * 60}")
        print(f"  Scenario: {goal_type}")
        print("=" * 60)
        try:
            plan: dict[str, Any] = build_campaign_plan(
                parsed_goal=parsed_goal,
                audience_result=audience_result,
                data_path=data_path,
            )
            print_summary(plan)
            save_campaign_plan(plan)
        except (FileNotFoundError, ValueError, AssertionError) as exc:
            print(f"  ERROR ({goal_type}): {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()