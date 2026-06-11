

"""Generate explainable customer health scores.

This module evaluates customer purchasing behaviour and produces a
customer health score that Aether can use for churn prevention,
retention campaigns, and lifecycle-based marketing decisions.
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_generation" / "data"

ORDERS_PATH = DATA_DIR / "orders.csv"
INTELLIGENCE_PATH = DATA_DIR / "customer_intelligence.csv"
OUTPUT_PATH = DATA_DIR / "customer_health.csv"


REFERENCE_BUFFER_DAYS = 30



def generate_customer_health():
    """Generate customer health scores and risk levels."""

    print("[pipeline] generating customer health scores ...")

    orders_df = pd.read_csv(ORDERS_PATH)
    intelligence_df = pd.read_csv(INTELLIGENCE_PATH)

    orders_df["order_date"] = pd.to_datetime(
        orders_df["order_date"]
    )

    customer_metrics = (
        orders_df.groupby("customer_id")
        .agg(
            total_spend=("final_price", "sum"),
            total_orders=("order_id", "count"),
            average_order_value=("final_price", "mean"),
            last_order_date=("order_date", "max"),
        )
        .reset_index()
    )

    reference_date = (
        orders_df["order_date"].max()
        + pd.Timedelta(days=REFERENCE_BUFFER_DAYS)
    )

    customer_metrics["days_since_last_order"] = (
        reference_date - customer_metrics["last_order_date"]
    ).dt.days

    health_df = intelligence_df.merge(
        customer_metrics,
        on="customer_id",
        how="left",
    )

    def calculate_health_score(row):
        score = 50

        days = row["days_since_last_order"]

        if days <= 30:
            score += 30
        elif days <= 60:
            score += 20
        elif days <= 90:
            score += 10
        else:
            score -= 10

        if row["total_orders"] >= 12:
            score += 15
        elif row["total_orders"] >= 6:
            score += 8

        if row.get("clv_tier") == "HIGH":
            score += 15
        elif row.get("clv_tier") == "MEDIUM":
            score += 8

        return round(max(0, min(100, score)))

    health_df["health_score"] = health_df.apply(
        calculate_health_score,
        axis=1,
    )

    def determine_health_status(score):
        if score >= 80:
            return "CHAMPION"
        if score >= 60:
            return "LOYAL"
        if score >= 40:
            return "AT_RISK"
        return "CRITICAL"

    health_df["health_status"] = health_df[
        "health_score"
    ].apply(determine_health_status)

    def generate_reason(row):
        if row["health_status"] == "CHAMPION":
            return (
                "Strong purchasing behaviour with consistent engagement."
            )

        if row["health_status"] == "LOYAL":
            return (
                "Healthy relationship with minor signs of disengagement."
            )

        if row["health_status"] == "AT_RISK":
            return (
                "Declining activity suggests a retention campaign may be beneficial."
            )

        return (
            "Immediate intervention recommended due to prolonged inactivity."
        )

    health_df["health_reason"] = health_df.apply(
        generate_reason,
        axis=1,
    )

    def determine_lifecycle_stage(row):
        days = row["days_since_last_order"]
        orders = row["total_orders"]
        health = row["health_status"]

        if days > 240:
            return "LOST"

        if days > 120:
            return "HIBERNATING"

        if orders <= 2 and days <= 60:
            return "NEW"

        if health == "CHAMPION":
            return "CHAMPION"

        if health == "LOYAL":
            return "LOYAL"

        return "ACTIVE"

    health_df["lifecycle_stage"] = health_df.apply(
        determine_lifecycle_stage,
        axis=1,
    )

    def generate_lifecycle_reason(row):
        stage = row["lifecycle_stage"]

        if stage == "NEW":
            return (
                "Recently acquired customer beginning their relationship with the brand."
            )

        if stage == "ACTIVE":
            return (
                "Engaged customer with potential to develop stronger loyalty."
            )

        if stage == "LOYAL":
            return (
                "Consistently returning customer demonstrating stable engagement."
            )

        if stage == "CHAMPION":
            return (
                "Highly valuable customer with strong purchasing behaviour and advocacy potential."
            )

        if stage == "HIBERNATING":
            return (
                "Previously engaged customer showing extended inactivity requiring reactivation efforts."
            )

        return (
            "Customer appears disengaged and may require aggressive win-back strategies or suppression."
        )

    health_df["lifecycle_reason"] = health_df.apply(
        generate_lifecycle_reason,
        axis=1,
    )

    output_columns = [
        "customer_id",
        "health_score",
        "health_status",
        "days_since_last_order",
        "total_orders",
        "total_spend",
        "lifecycle_stage",
        "lifecycle_reason",
        "health_reason",
    ]

    health_df[output_columns].to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        f"[pipeline] customer health saved → {OUTPUT_PATH}"
    )

    return health_df[output_columns]


if __name__ == "__main__":
    generate_customer_health()