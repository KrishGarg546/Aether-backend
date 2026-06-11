

"""Generate personalized campaign recommendations.

This module combines Aether's intelligence layers to determine the
most appropriate campaign, offer, message, and channel for each
customer.
"""

import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_generation" / "data"

INTELLIGENCE_PATH = DATA_DIR / "customer_intelligence.csv"
HEALTH_PATH = DATA_DIR / "customer_health.csv"
STORIES_PATH = DATA_DIR / "customer_stories.csv"
OUTPUT_PATH = DATA_DIR / "personalized_campaigns.csv"


CAMPAIGN_RULES = {
    "NEW_PARENT": {
        "campaign": "Home Safety Essentials",
        "offer": "20% off Childproofing Bundle",
        "message": (
            "As your family grows, keeping your home safe becomes even more important. "
            "Explore our curated childproofing essentials."
        ),
    },
    "WELLNESS_SEEKER": {
        "campaign": "Wellness Habit Bundle",
        "offer": "15% off Wellness Collection",
        "message": (
            "Support your wellness journey with products designed to help you build healthy habits that last."
        ),
    },
    "ECO_CONSCIOUS_HOME": {
        "campaign": "Healthy Home Collection",
        "offer": "Free Shipping on Eco Bundles",
        "message": (
            "Continue building a more sustainable lifestyle with our eco-conscious essentials."
        ),
    },
    "GENERAL": {
        "campaign": "Personalized Recommendations",
        "offer": "10% off Selected Products",
        "message": (
            "Discover products chosen specifically for customers with similar preferences."
        ),
    },
}


def generate_personalized_campaigns():
    print("[pipeline] generating personalized campaigns ...")

    intelligence_df = pd.read_csv(INTELLIGENCE_PATH)
    health_df = pd.read_csv(HEALTH_PATH)
    stories_df = pd.read_csv(STORIES_PATH)

    campaign_df = (
        intelligence_df
        .merge(
            health_df[
                [
                    "customer_id",
                    "health_status",
                    "lifecycle_stage",
                ]
            ],
            on="customer_id",
            how="left",
        )
        .merge(
            stories_df[
                [
                    "customer_id",
                    "story_segment",
                ]
            ],
            on="customer_id",
            how="left",
        )
    )

    campaigns = []

    for _, row in campaign_df.iterrows():
        story = row.get("story_segment", "GENERAL")
        story = story if story in CAMPAIGN_RULES else "GENERAL"

        config = CAMPAIGN_RULES[story]

        offer = config["offer"]

        if row.get("health_status") == "AT_RISK":
            offer = f"URGENT: {offer}"

        elif row.get("health_status") == "CRITICAL":
            offer = f"WIN-BACK: {offer}"

        campaigns.append(
            {
                "customer_id": row["customer_id"],
                "story_segment": story,
                "health_status": row.get("health_status"),
                "lifecycle_stage": row.get("lifecycle_stage"),
                "campaign_name": config["campaign"],
                "offer": offer,
                "channel": row.get(
                    "recommended_channel",
                    "EMAIL",
                ),
                "message": config["message"],
            }
        )

    result_df = pd.DataFrame(campaigns)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print(
        f"[pipeline] personalized campaigns saved → {OUTPUT_PATH}"
    )

    return result_df


if __name__ == "__main__":
    generate_personalized_campaigns()