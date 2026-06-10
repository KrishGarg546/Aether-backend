"""
generate_customer_intelligence.py
==================================
Aether CRM — Customer Intelligence Layer

Consumes:
    - customers.csv
    - orders.csv
    - products.csv
    - story_customers.csv
    - customer_features.csv

Produces:
    - customer_intelligence.csv  (one row per customer)

Output schema:
    customer_id, segment, churn_risk, clv_tier,
    recommended_offer, recommended_channel,
    campaign_priority, recommended_campaign_type

Design principles:
    - Fully deterministic (RANDOM_SEED = 42)
    - No ML models — rule-based intelligence engine
    - pandas + numpy only
    - Production-quality code with comprehensive docstrings
    - Strong validation and summary reporting

Author: Aether CRM Project
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RANDOM_SEED: int = 42

# Input file paths (relative; override via CLI args if needed)
# ==============================================================================
# FILE PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data_generation" / "data"

CUSTOMERS_PATH = DATA_DIR / "customers.csv"
ORDERS_PATH = DATA_DIR / "orders.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
STORY_CUSTOMERS_PATH = DATA_DIR / "story_customers.csv"
CUSTOMER_FEATURES_PATH = DATA_DIR / "customer_features.csv"

OUTPUT_PATH = DATA_DIR / "customer_intelligence.csv"

# Allowed categorical values — used for validation
ALLOWED_CHURN_RISK = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_CLV_TIER = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_CAMPAIGN_PRIORITY = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_CHANNELS = {"EMAIL", "WHATSAPP", "SMS", "RCS"}
ALLOWED_CAMPAIGN_TYPES = {
    "Retention",
    "Reactivation",
    "Upsell",
    "Cross-sell",
    "Loyalty",
    "Awareness",
}

# Churn risk thresholds (recency_days)
CHURN_HIGH_RECENCY = 120      # inactive for 4+ months → high risk
CHURN_MEDIUM_RECENCY = 60     # inactive 2–4 months   → medium risk

# CLV monetary thresholds (INR lifetime spend)
CLV_HIGH_MONETARY = 10_000
CLV_MEDIUM_MONETARY = 4_000

# Frequency thresholds for CLV scoring
CLV_HIGH_FREQUENCY = 8
CLV_MEDIUM_FREQUENCY = 4

# Campaign priority thresholds
PRIORITY_HIGH_CLV_MONETARY = 10_000
PRIORITY_HIGH_CHURN_RECENCY = 90


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load all input CSV files into DataFrames.

    Returns
    -------
    tuple of (customers, orders, products, story_customers, customer_features)

    Raises
    ------
    FileNotFoundError
        If any required input file is missing.
    """
    for path in [CUSTOMERS_PATH, ORDERS_PATH, PRODUCTS_PATH,
                 STORY_CUSTOMERS_PATH, CUSTOMER_FEATURES_PATH]:
        if not path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {path.resolve()}"
            )

    customers = pd.read_csv(CUSTOMERS_PATH)
    orders = pd.read_csv(ORDERS_PATH)
    products = pd.read_csv(PRODUCTS_PATH)
    story_customers = pd.read_csv(STORY_CUSTOMERS_PATH)
    customer_features = pd.read_csv(CUSTOMER_FEATURES_PATH)

    print(f"[load]  customers:         {len(customers):,} rows")
    print(f"[load]  orders:            {len(orders):,} rows")
    print(f"[load]  products:          {len(products):,} rows")
    print(f"[load]  story_customers:   {len(story_customers):,} rows")
    print(f"[load]  customer_features: {len(customer_features):,} rows")

    return customers, orders, products, story_customers, customer_features


# ---------------------------------------------------------------------------
# Segment Assignment
# ---------------------------------------------------------------------------

# Segment mapping keyed by (persona, engagement_tier, frequency_tier)
# Falls back gracefully to persona-only rules.

_SEGMENT_PERSONA_MAP: dict[str, str] = {
    "Wellness Seekers":   "Wellness Advocates",
    "Premium Self-Care":  "Premium Wellness Advocates",
    "Seasoned Parents":   "Loyal Parents",
    "New Parents":        "Growing Family Shoppers",
    "Budget Families":    "Budget Family Shoppers",
    "Dormant Customers":  "Dormant Reactivation Targets",
}

_HIGH_FREQUENCY_SUFFIX = {
    "Wellness Advocates":            "Growing Wellness Customers",
    "Premium Wellness Advocates":    "Premium Wellness Advocates",   # already premium
    "Loyal Parents":                 "Loyal Parents",
    "Growing Family Shoppers":       "Growing Family Shoppers",
    "Budget Family Shoppers":        "Budget Family Shoppers",
    "Dormant Reactivation Targets":  "Dormant Reactivation Targets",
}

_LOW_FREQUENCY_SUFFIX = {
    "Wellness Advocates":            "Occasional Wellness Shoppers",
    "Premium Wellness Advocates":    "Premium Wellness Advocates",
    "Loyal Parents":                 "Occasional Parents",
    "Growing Family Shoppers":       "New Family Shoppers",
    "Budget Family Shoppers":        "Budget Family Shoppers",
    "Dormant Reactivation Targets":  "Dormant Reactivation Targets",
}


def assign_segment(row: pd.Series) -> str:
    """
    Assign a human-readable marketing segment to a customer.

    Logic (in order):
    1.  Dormant by recency (≥ 180 days) → override to "Dormant Reactivation Targets".
    2.  Map persona to a base segment label.
    3.  Refine by frequency tier (high / low).

    Parameters
    ----------
    row : pd.Series
        A single row from the merged customer_features + customers DataFrame.

    Returns
    -------
    str
        Segment label.
    """
    recency: float = row.get("recency_days", 0)
    frequency: float = row.get("frequency", 0)
    persona: str = row.get("persona", "")

    # Hard override for dormant customers regardless of persona
    if recency >= 180:
        return "Dormant Reactivation Targets"

    base = _SEGMENT_PERSONA_MAP.get(persona, "General Shoppers")

    if frequency >= CLV_HIGH_FREQUENCY:
        return _HIGH_FREQUENCY_SUFFIX.get(base, base)
    elif frequency <= 2:
        return _LOW_FREQUENCY_SUFFIX.get(base, base)
    else:
        return base


# ---------------------------------------------------------------------------
# Churn Risk Scoring
# ---------------------------------------------------------------------------


def assign_churn_risk(row: pd.Series) -> str:
    """
    Determine churn risk using deterministic rules.

    Rules evaluated in order of severity:

    HIGH:
        - recency_days >= CHURN_HIGH_RECENCY (120 days)
        - OR orders_per_month < 0.3 AND tenure > 90 days
        - OR frequency == 1 AND recency_days > 60

    MEDIUM:
        - recency_days >= CHURN_MEDIUM_RECENCY (60 days)
        - OR orders_per_month < 0.7 AND tenure > 60 days

    LOW:
        - All remaining customers.

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        "HIGH", "MEDIUM", or "LOW"
    """
    recency: float = row.get("recency_days", 0)
    frequency: int = int(row.get("frequency", 1))
    opm: float = float(row.get("orders_per_month", 0) or 0)
    tenure: float = float(row.get("customer_tenure_days", 0) or 0)

    # HIGH risk conditions
    if recency >= CHURN_HIGH_RECENCY:
        return "HIGH"
    if opm < 0.3 and tenure > 90:
        return "HIGH"
    if frequency == 1 and recency > 60:
        return "HIGH"

    # MEDIUM risk conditions
    if recency >= CHURN_MEDIUM_RECENCY:
        return "MEDIUM"
    if opm < 0.7 and tenure > 60:
        return "MEDIUM"

    return "LOW"


# ---------------------------------------------------------------------------
# CLV Tier Assignment
# ---------------------------------------------------------------------------


def assign_clv_tier(row: pd.Series) -> str:
    """
    Assign a Customer Lifetime Value tier.

    Scoring approach:
        Each dimension (monetary, frequency, avg_order_value, orders_per_month)
        contributes +1 if it exceeds its HIGH threshold, +0.5 for MEDIUM.
        Total score >= 3   → HIGH
        Total score >= 1.5 → MEDIUM
        Otherwise          → LOW

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        "HIGH", "MEDIUM", or "LOW"
    """
    monetary: float = float(row.get("monetary", 0) or 0)
    frequency: float = float(row.get("frequency", 0) or 0)
    aov: float = float(row.get("avg_order_value", 0) or 0)
    opm: float = float(row.get("orders_per_month", 0) or 0)
    tenure = float(row.get("customer_tenure_days", 0) or 0)

    score: float = 0.0

    # Monetary
    if monetary >= CLV_HIGH_MONETARY:
        score += 1.0
    elif monetary >= CLV_MEDIUM_MONETARY:
        score += 0.5

    # Frequency
    if frequency >= CLV_HIGH_FREQUENCY:
        score += 1.0
    elif frequency >= CLV_MEDIUM_FREQUENCY:
        score += 0.5

    # Average order value (top 30% ≈ > 800, median ≈ 600)
    if aov >= 900:
        score += 1.0
    elif aov >= 600:
        score += 0.5

    # Orders per month
    if opm >= 1.5:
        score += 1.0
    elif opm >= 0.7:
        score += 0.5
    # Customer longevity bonus
    if tenure >= 365:
        score += 0.5

    if score >= 3.0:
        return "HIGH"
    elif score >= 1.5:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Recommended Offer
# ---------------------------------------------------------------------------

_OFFER_MATRIX: dict[tuple[str, str], str] = {
    # (churn_risk, clv_tier) → offer
    ("HIGH",   "HIGH"):   "Win-back Discount",
    ("HIGH",   "MEDIUM"): "Win-back Discount",
    ("HIGH",   "LOW"):    "Win-back Discount",
    ("MEDIUM", "HIGH"):   "Loyalty Reward",
    ("MEDIUM", "MEDIUM"): "Bundle Discount",
    ("MEDIUM", "LOW"):    "Bundle Discount",
    ("LOW",    "HIGH"):   "Loyalty Reward",
    ("LOW",    "MEDIUM"): "Cross-sell Recommendation",
    ("LOW",    "LOW"):    "New Arrival Promotion",
}

_CATEGORY_OFFER_OVERRIDE: dict[str, str] = {
    "Wellness":          "Bundle Discount",
    "Baby Care":         "Bundle Discount",
    "Family Essentials": "Cross-sell Recommendation",
}


def assign_recommended_offer(row: pd.Series) -> str:
    """
    Determine the best offer for a customer.

    Base logic: matrix lookup by (churn_risk, clv_tier).
    Override: dormant customers always get Win-back Discount.
    Override: Loyalty Reward is preferred for HIGH CLV + LOW churn
              regardless of category.
    Category nudge: if the base offer is Cross-sell or New Arrival,
                    the favourite category can refine the offer.

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        Offer label.
    """
    churn: str = row["churn_risk"]
    clv: str = row["clv_tier"]
    segment: str = row.get("segment", "")
    category: str = row.get("favorite_category", "")

    if "Dormant" in segment:
        return "Win-back Discount"

    offer = _OFFER_MATRIX.get((churn, clv), "New Arrival Promotion")

    # Refine generic offers with category signal
    if offer in {"New Arrival Promotion", "Cross-sell Recommendation"}:
        offer = _CATEGORY_OFFER_OVERRIDE.get(category, offer)

    return offer


# ---------------------------------------------------------------------------
# Recommended Channel
# ---------------------------------------------------------------------------

_PERSONA_CHANNEL_MAP: dict[str, str] = {
    "Wellness Seekers":  "EMAIL",
    "Premium Self-Care": "EMAIL",
    "Seasoned Parents":  "WHATSAPP",
    "New Parents":       "WHATSAPP",
    "Budget Families":   "SMS",
    "Dormant Customers": "SMS",
}

_PAYMENT_CHANNEL_MAP: dict[str, str] = {
    "UPI":          "WHATSAPP",
    "Credit Card":  "EMAIL",
    "Debit Card":   "EMAIL",
    "Cash":         "SMS",
    "Net Banking":  "EMAIL",
}


def assign_recommended_channel(row: pd.Series) -> str:
    """
    Recommend the most effective communication channel.

    Decision hierarchy:
    1.  If engagement_level is High → prefer RCS (rich messaging for
        active users).
    2.  Payment method signal overrides persona (behavioural indicator).
    3.  Persona-based default.
    4.  Fallback: EMAIL.

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        One of EMAIL, WHATSAPP, SMS, RCS.
    """
    engagement: str = str(row.get("engagement_level", "UNKNOWN"))
    preferred_channel: str = str(row.get("preferred_channel", ""))
    payment: str = str(row.get("preferred_payment_method", ""))
    persona: str = str(row.get("persona", ""))

# Highly engaged users can receive richer experiences
    if engagement.lower() == "high":
        return "RCS"

    # Respect historical customer behaviour first
    if preferred_channel in ALLOWED_CHANNELS:
        return preferred_channel

    # Behavioural payment signals
    channel = _PAYMENT_CHANNEL_MAP.get(payment)
    if channel:
        return channel

    # Persona defaults
    channel = _PERSONA_CHANNEL_MAP.get(persona)
    if channel:
        return channel

# Final fallback
    return "EMAIL"

def get_channel_reason(row: pd.Series) -> str:
    """
    Explain why a communication channel was selected.
    Must mirror assign_recommended_channel().
    """

    channel = row["recommended_channel"]

    if row.get("engagement_level") == "High":
        return (
            f"{channel} selected because high engagement customers "
            "respond better to rich and interactive messaging experiences."
        )

    payment = row.get("preferred_payment_method", "")

    if payment == "UPI":
        return (
            f"{channel} selected because customers preferring UPI "
            "typically demonstrate strong responsiveness through this channel."
        )

    if payment in ["Credit Card", "Debit Card", "Net Banking"]:
        return (
            f"{channel} selected because digitally engaged customers "
            "often respond effectively through this channel."
        )

    if payment == "Cash":
        return (
            f"{channel} selected because customers preferring cash "
            "historically engage better through simpler communication channels."
        )

    persona = row.get("persona", "")

    return (
        f"{channel} selected because customers within the "
        f"'{persona}' persona historically engage better through this channel."
    )
# ---------------------------------------------------------------------------
# Campaign Priority
# ---------------------------------------------------------------------------


def assign_campaign_priority(row: pd.Series) -> str:
    """
    Determine campaign execution priority.

    HIGH:
        - Story customers (they are strategic showcase assets).
        - HIGH CLV tier customers (protect revenue).
        - HIGH churn risk customers with MEDIUM or HIGH CLV
          (save at-risk high-value customers).

    MEDIUM:
        - HIGH churn risk with LOW CLV (still worth re-engaging).
        - MEDIUM CLV tier customers.
        - Customers with monetary spend above 75th percentile (~9,000).

    LOW:
        - Everything else.

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        "HIGH", "MEDIUM", or "LOW"
    """
    is_story: int = int(row.get("is_story_customer", 0) or 0)
    clv: str = row["clv_tier"]
    churn: str = row["churn_risk"]
    monetary: float = float(row.get("monetary", 0) or 0)

    if is_story == 1:
        return "HIGH"

    if clv == "HIGH":
        return "HIGH"

    if churn == "HIGH" and clv in {"MEDIUM", "HIGH"}:
        return "HIGH"

    if churn == "HIGH" and clv == "LOW":
        return "MEDIUM"

    if clv == "MEDIUM":
        return "MEDIUM"

    if monetary >= PRIORITY_HIGH_CLV_MONETARY * 0.9:  # ~9,000 INR
        return "MEDIUM"

    return "LOW"


# ---------------------------------------------------------------------------
# Recommended Campaign Type
# ---------------------------------------------------------------------------

_CAMPAIGN_TYPE_MATRIX: dict[tuple[str, str, str], str] = {
    # (segment_keyword, churn_risk, clv_tier) → campaign_type
    # Dormant overrides everything
}

_CHURN_CAMPAIGN_MAP: dict[str, str] = {
    "HIGH":   "Reactivation",
    "MEDIUM": "Retention",
    "LOW":    "Loyalty",
}

_CLV_CAMPAIGN_REFINEMENT: dict[tuple[str, str], str] = {
    ("LOW",    "HIGH"):   "Upsell",
    ("LOW",    "MEDIUM"): "Cross-sell",
    ("MEDIUM", "HIGH"):   "Upsell",
}


def assign_campaign_type(row: pd.Series) -> str:
    """
    Recommend the most suitable campaign type.

    Logic:
    1.  Dormant segment → Reactivation.
    2.  HIGH churn risk → Reactivation.
    3.  MEDIUM churn risk → Retention.
    4.  LOW churn risk + HIGH CLV → Loyalty.
    5.  LOW churn risk + MEDIUM CLV → Upsell or Cross-sell
        based on frequency.
    6.  LOW churn risk + LOW CLV → Awareness.

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    str
        Campaign type label.
    """
    segment: str = row.get("segment", "")
    churn: str = row["churn_risk"]
    clv: str = row["clv_tier"]
    frequency: float = float(row.get("frequency", 0) or 0)

    if "Dormant" in segment:
        return "Reactivation"

    if churn == "HIGH":
        return "Reactivation"

    if churn == "MEDIUM" and clv == "HIGH":
        return "Loyalty"

    if churn == "MEDIUM":
        return "Retention"

    if clv == "HIGH":
        return "Upsell"

    if clv == "MEDIUM":
        return "Cross-sell"

    return "Awareness"


# ---------------------------------------------------------------------------
# Core Pipeline
# ---------------------------------------------------------------------------
def get_churn_reason(row: pd.Series) -> str:
    recency = row.get("recency_days", 0)
    frequency = row.get("frequency", 0)
    opm = row.get("orders_per_month", 0)
    tenure = row.get("customer_tenure_days", 0)

    if recency >= CHURN_HIGH_RECENCY:
        return f"Customer inactive for {int(recency)} days indicating elevated churn risk."

    if opm < 0.3 and tenure > 90:
        return "Purchase frequency has declined significantly over time."

    if frequency == 1 and recency > 60:
        return "Customer has not returned after the initial purchase."

    if recency >= CHURN_MEDIUM_RECENCY:
        return f"Customer engagement has weakened over the last {int(recency)} days."

    if opm < 0.7 and tenure > 60:
        return "Customer activity levels suggest moderate disengagement."

    return "Customer engagement patterns indicate low churn risk."

def get_clv_reason(row: pd.Series) -> str:
    clv = row["clv_tier"]

    if clv == "HIGH":
        return (
            "Strong lifetime value driven by spending, purchase consistency, "
            "and long-term engagement."
        )

    if clv == "MEDIUM":
        return (
            "Customer demonstrates stable purchasing behaviour with "
            "opportunities for growth."
        )

    return (
        "Customer currently contributes lower lifetime value relative "
        "to the broader shopper base."
    )


def get_campaign_reason(row: pd.Series) -> str:
    campaign = row["recommended_campaign_type"]
    channel = row["recommended_channel"]

    return (
        f"{campaign} campaign selected for execution through {channel} "
        f"based on customer intelligence signals."
    )


def generate_decision_reason(row: pd.Series) -> str:
    """
    Generate a human-readable explanation for why Aether made
    a particular campaign recommendation.

    Parameters
    ----------
    row : pd.Series
        Customer intelligence row.

    Returns
    -------
    str
        Plain-English explanation describing the reasoning behind
        the campaign decision.
    """

    reasons = []

    # Churn reasoning
    recency = row.get("recency_days", 0)

    if row["churn_risk"] == "HIGH":
        reasons.append(
            f"Customer inactive for {int(recency)} days indicating elevated churn risk."
        )

    elif row["churn_risk"] == "MEDIUM":
        reasons.append(
            f"Customer inactive for {int(recency)} days suggesting moderate disengagement."
        )

    else:
        reasons.append(
            "Recent purchasing activity indicates low likelihood of churn."
        )

        # CLV reasoning
    if row["clv_tier"] == "HIGH":
        reasons.append(
            "Strong lifetime value driven by spending, purchase consistency, and long-term engagement."
        )

    elif row["clv_tier"] == "MEDIUM":
        reasons.append(
            "Customer demonstrates stable purchasing behaviour with opportunities for value growth."
        )

    else:
        reasons.append(
            "Customer currently contributes lower lifetime value compared with other segments."
        )

    # Behaviour reasoning
    if row.get("frequency", 0) >= CLV_HIGH_FREQUENCY:
        reasons.append(
            "Customer has shown consistent repeat purchase behaviour."
        )

    # Story customer reasoning
    if row.get("is_story_customer", False):
        reasons.append(
            "Story customer prioritised for strategic engagement initiatives."
        )

    # Campaign reasoning
    reasons.append(get_campaign_reason(row))

    # Channel reasoning
    reasons.append(row["channel_reason"])

    return " ".join(reasons)

def build_intelligence(
    customers: pd.DataFrame,
    customer_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Run the full intelligence pipeline and return customer_intelligence DataFrame.

    Steps:
    1.  Merge customer_features with customers for channel/persona signals.
    2.  Apply rule-based functions for each intelligence dimension.
    3.  Select and return the output schema columns.

    Parameters
    ----------
    customers : pd.DataFrame
    customer_features : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        customer_intelligence with one row per customer_id.
    """
    # Merge to bring in preferred_channel from customers table
    # customer_features already has persona, engagement_level, payment_method
    df = customer_features.merge(
        customers[["customer_id", "preferred_channel"]],
        on="customer_id",
        how="left",
    )

    print(f"[pipeline]  merged dataset: {len(df):,} rows × {df.shape[1]} cols")

    # --- Segment ---
    print("[pipeline]  assigning segments …")
    df["segment"] = df.apply(assign_segment, axis=1)

    # --- Churn Risk ---
    print("[pipeline]  scoring churn risk …")
    df["churn_risk"] = df.apply(assign_churn_risk, axis=1)

    # --- CLV Tier ---
    print("[pipeline]  estimating CLV tiers …")
    df["clv_tier"] = df.apply(assign_clv_tier, axis=1)

    # --- Recommended Offer ---
    print("[pipeline]  generating offer recommendations …")
    df["recommended_offer"] = df.apply(assign_recommended_offer, axis=1)

    # --- Recommended Channel ---
    print("[pipeline]  selecting recommended channels …")
    df["recommended_channel"] = df.apply(assign_recommended_channel, axis=1)
    df["channel_reason"] = df.apply(get_channel_reason, axis=1)

    # --- Campaign Priority ---
    print("[pipeline]  calculating campaign priorities …")
    df["campaign_priority"] = df.apply(assign_campaign_priority, axis=1)

    # --- Campaign Type ---
    print("[pipeline]  determining campaign types …")
    df["recommended_campaign_type"] = df.apply(assign_campaign_type, axis=1)
    print("[pipeline] generating decision explanations …")
    df["decision_reason"] = df.apply(
    generate_decision_reason,
    axis=1,
)
    # Select output schema
    output_cols = [
    "customer_id",
    "segment",
    "churn_risk",
    "clv_tier",
    "recommended_offer",
    "recommended_channel",
    "campaign_priority",
    "recommended_campaign_type",
    "decision_reason",
]

    return df[output_cols].copy()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_output(df: pd.DataFrame, expected_customer_count: int) -> None:
    """
    Validate the customer_intelligence DataFrame against business rules.

    Assertions:
        - Row count matches total customer count.
        - No duplicate customer_ids.
        - No null values in any output column.
        - All categorical columns contain only allowed values.

    Parameters
    ----------
    df : pd.DataFrame
        The output intelligence DataFrame.
    expected_customer_count : int
        Total number of unique customers expected.

    Raises
    ------
    AssertionError
        On any failed validation with a descriptive message.
    """
    print("\n[validation]  running checks …")

    # Row count
    assert len(df) == expected_customer_count, (
        f"Row count mismatch: expected {expected_customer_count}, got {len(df)}. "
        "Each customer must appear exactly once."
    )

    # Duplicate customer_ids
    duplicates = df["customer_id"].duplicated().sum()
    assert duplicates == 0, (
        f"Found {duplicates} duplicate customer_id(s). "
        "customer_intelligence must have exactly one row per customer."
    )

    # No nulls in output columns
    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    assert cols_with_nulls.empty, (
        f"Null values found in output columns:\n{cols_with_nulls.to_string()}"
    )
    assert df["decision_reason"].str.len().gt(0).all(), (
    "Empty decision explanations found."
)

    # Categorical value checks
    _assert_allowed_values(df, "churn_risk",               ALLOWED_CHURN_RISK)
    _assert_allowed_values(df, "clv_tier",                 ALLOWED_CLV_TIER)
    _assert_allowed_values(df, "campaign_priority",        ALLOWED_CAMPAIGN_PRIORITY)
    _assert_allowed_values(df, "recommended_channel",      ALLOWED_CHANNELS)
    _assert_allowed_values(df, "recommended_campaign_type", ALLOWED_CAMPAIGN_TYPES)

    print("[validation]  all checks passed ✓")


def _assert_allowed_values(df: pd.DataFrame, col: str, allowed: set[str]) -> None:
    """
    Assert that a DataFrame column only contains values from the allowed set.

    Parameters
    ----------
    df : pd.DataFrame
    col : str
        Column name to check.
    allowed : set[str]
        Set of permitted values.

    Raises
    ------
    AssertionError
        If any disallowed value is found.
    """
    unique_vals = set(df[col].unique())
    disallowed = unique_vals - allowed
    assert not disallowed, (
        f"Column '{col}' contains disallowed values: {disallowed}. "
        f"Allowed values: {allowed}"
    )


# ---------------------------------------------------------------------------
# Summary Report
# ---------------------------------------------------------------------------


def print_summary_report(df: pd.DataFrame) -> None:
    """
    Print a human-readable distribution summary for all output columns.

    Parameters
    ----------
    df : pd.DataFrame
        The validated customer_intelligence DataFrame.
    """
    total = len(df)
    separator = "─" * 55

    print(f"\n{'═' * 55}")
    print("  AETHER CRM — CUSTOMER INTELLIGENCE SUMMARY REPORT")
    print(f"  Total customers: {total:,}")
    print(f"{'═' * 55}")

    dimensions = [
        ("Segment Distribution",          "segment"),
        ("Churn Risk Distribution",        "churn_risk"),
        ("CLV Tier Distribution",          "clv_tier"),
        ("Campaign Priority Distribution", "campaign_priority"),
        ("Recommended Channel",            "recommended_channel"),
        ("Recommended Campaign Type",      "recommended_campaign_type"),
    ]

    for title, col in dimensions:
        print(f"\n  {title}")
        print(f"  {separator}")
        counts = df[col].value_counts().sort_values(ascending=False)
        for val, count in counts.items():
            pct = count / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {str(val):<35} {count:>5,}  ({pct:5.1f}%)  {bar}")

    print(f"\n{'═' * 55}\n")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_output(df: pd.DataFrame) -> None:
    """
    Export the intelligence DataFrame to customer_intelligence.csv.

    Parameters
    ----------
    df : pd.DataFrame
    """
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"[export]  customer_intelligence.csv → {OUTPUT_PATH.resolve()}")
    print(f"[export]  {len(df):,} rows × {df.shape[1]} columns written.")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Orchestrate the full Aether customer intelligence pipeline.

    Execution sequence:
        1.  Load all input datasets.
        2.  Build intelligence (segment, churn, CLV, offers, channels, priority, type).
        3.  Validate output integrity.
        4.  Print summary report.
        5.  Export to CSV.
    """
    np.random.seed(RANDOM_SEED)

    print("╔══════════════════════════════════════════════════════╗")
    print("║   Aether CRM — Customer Intelligence Generator       ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    # Step 1: Load
    customers, orders, products, story_customers, customer_features = load_data()

    expected_count = customers["customer_id"].nunique()
    print(f"\n[info]  Expected output rows: {expected_count:,}")

    # Step 2: Build intelligence
    print("\n[pipeline]  Starting intelligence pipeline …")
    intelligence = build_intelligence(customers, customer_features)

    # Step 3: Validate
    validate_output(intelligence, expected_count)

    # Step 4: Summary
    print_summary_report(intelligence)

    # Step 5: Export
    export_output(intelligence)

    print("\n✓  Pipeline complete.\n")


if __name__ == "__main__":
    main()