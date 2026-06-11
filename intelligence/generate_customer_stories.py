

"""Generate customer story intelligence.

This module identifies meaningful customer life-stage narratives from
historical purchasing behaviour. Unlike CRM lifecycle stages, these
stories represent what may be happening in a customer's life and guide
more empathetic marketing strategies.
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_generation" / "data"

ORDERS_PATH = DATA_DIR / "orders.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OUTPUT_PATH = DATA_DIR / "customer_stories.csv"


STORY_RULES = {
    "NEW_PARENT": {
        "baby_keywords": [
            "baby",
            "infant",
        ],
        "safety_keywords": [
            "cabinet",
            "safety",
            "first aid",
            "smoke detector",
        ],
        "stage": "CHILDPROOFING",
        "campaign": "Home Safety Essentials",
    },
    "WELLNESS_SEEKER": {
        "keywords": [
            "vitamin",
            "ashwagandha",
            "collagen",
            "omega",
            "journal",
            "lavender",
            "turmeric",
            "probiotic",
        ],
        "stage": "HABIT_BUILDING",
        "campaign": "Wellness Routine Bundle",
    },
    "ECO_CONSCIOUS_HOME": {
        "keywords": [
            "beeswax",
            "compost",
            "reusable",
            "food storage",
            "eco",
        ],
        "stage": "SUSTAINABLE_LIVING",
        "campaign": "Healthy Home Collection",
    },
}


def generate_customer_stories():
    print("[pipeline] generating customer stories ...")

    orders_df = pd.read_csv(ORDERS_PATH)
    products_df = pd.read_csv(PRODUCTS_PATH)

    enriched_orders = orders_df.merge(
        products_df[["product_id", "name"]],
        on="product_id",
        how="left",
    )

    customer_products = (
        enriched_orders.groupby("customer_id")["name"]
        .apply(lambda values: " ".join(values.astype(str)).lower())
        .reset_index(name="purchase_history")
    )

    stories = []

    for _, row in customer_products.iterrows():
        customer_id = row["customer_id"]
        history = row["purchase_history"]

        assigned_story = "GENERAL"
        story_stage = "ENGAGED_CUSTOMER"
        recommended_campaign = "Personalized Recommendations"
        reason = (
            "No dominant life-stage pattern detected from purchasing behaviour."
        )

        for story, config in STORY_RULES.items():
            if story == "NEW_PARENT":
                baby_match = any(
                    keyword in history
                    for keyword in config["baby_keywords"]
                )

                safety_match = any(
                    keyword in history
                    for keyword in config["safety_keywords"]
                )

                if baby_match and safety_match:
                    assigned_story = story
                    story_stage = config["stage"]
                    recommended_campaign = config["campaign"]
                    reason = (
                        "Detected a progression from infant care products to home safety products, suggesting a childproofing journey."
                    )
                    break

                continue
            matches = sum(
                keyword in history
                for keyword in config["keywords"]
            )

            if matches >= 2:
                assigned_story = story
                story_stage = config["stage"]
                recommended_campaign = config["campaign"]
                reason = (
                    f"Detected {matches} behavioural signals associated with {story.lower().replace('_', ' ')}."
                )
                break

        stories.append(
            {
                "customer_id": customer_id,
                "story_segment": assigned_story,
                "story_stage": story_stage,
                "recommended_campaign": recommended_campaign,
                "story_reason": reason,
            }
        )

    stories_df = pd.DataFrame(stories)
    stories_df.to_csv(OUTPUT_PATH, index=False)

    print(
        f"[pipeline] customer stories saved → {OUTPUT_PATH}"
    )

    return stories_df


if __name__ == "__main__":
    generate_customer_stories()