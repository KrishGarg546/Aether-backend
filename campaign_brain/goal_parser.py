GOAL_CATALOG = {
    "REACTIVATION": {
        "phrases": [
            "reduce churn",
            "win back",
            "reactivate",
            "bring back",
            "recover inactive",
            "reduce customer loss",
            "reduce cancellations",
            "inactive customers",
            "dormant customers",
        ],
        "goal_type": "REACTIVATION",
        "success_metric": "retention_rate",
        "default_objective": "reactivation",
    },
    "RETENTION": {
        "phrases": [
            "increase retention",
            "improve retention",
            "increase repeat purchases",
            "encourage repeat purchases",
            "retain customers",
            "keep customers",
        ],
        "goal_type": "RETENTION",
        "success_metric": "repeat_purchase_rate",
        "default_objective": "retention",
    },
    "UPSELL": {
        "phrases": [
            "increase average order value",
            "increase basket size",
            "upsell",
            "sell premium products",
            "increase customer lifetime value",
            "move customers to premium tiers",
            "upsell premium products",
            "encourage customers to buy higher value items",
        ],
        "goal_type": "UPSELL",
        "success_metric": "average_order_value",
        "default_objective": "upsell",
    },
    "CROSS_SELL": {
        "phrases": [
            "cross sell",
            "recommend complementary products",
            "promote related products",
            "product recommendations",
            "suggest related products",
            "cross sell relevant items",
        ],
        "goal_type": "CROSS_SELL",
        "success_metric": "cross_sell_conversion_rate",
        "default_objective": "cross_sell",
    },
    "LOYALTY": {
        "phrases": [
            "reward loyal customers",
            "strengthen loyalty",
            "increase loyalty engagement",
            "loyalty program",
            "retain our best customers",
            "increase loyalty among repeat buyers",
        ],
        "goal_type": "LOYALTY",
        "success_metric": "loyalty_engagement_rate",
        "default_objective": "loyalty",
    },
}
PERSONA_MAPPING = {
    "new parents": "Growing Family Shoppers",
    "seasoned parents": "Loyal Parents",
    "wellness seekers": "Wellness Advocates",
    "premium customers": "Premium Wellness Advocates",
    "budget families": "Budget Family Shoppers",
    "dormant customers": "Dormant Reactivation Targets",
}

def parse_goal(goal: str) -> dict:
    """
    Convert a marketer's business goal into a structured campaign intent.
    """

    goal_lower = goal.lower().strip()
    goal_lower = goal_lower.replace("-", " ")
    goal_lower = " ".join(goal_lower.split())

    parsed_goal = None
    parsed_persona = None
    matched_goal_phrase = None
    matched_persona_phrase = None

    # Identify goal type
    for _, goal_info in GOAL_CATALOG.items():
        for phrase in goal_info["phrases"]:
            if phrase in goal_lower:
                parsed_goal = goal_info.copy()
                matched_goal_phrase = phrase
                break

        if parsed_goal is not None:
            break

    if parsed_goal is None:
        return {
            "original_goal": goal,
            "goal_type": "MANUAL_REVIEW",
            "objective": "MANUAL_REVIEW",
            "campaign_objective": "manual_review",
            "success_metric": None,
            "target_segment": "ALL_CUSTOMERS",
            "parser_reason": "No supported business objective could be inferred from the supplied goal.",
        }

    # Identify target persona
    for persona_phrase, segment in PERSONA_MAPPING.items():
        if persona_phrase in goal_lower:
            parsed_persona = segment
            matched_persona_phrase = persona_phrase
            break

    return {
        "original_goal": goal,
        "goal_type": parsed_goal["goal_type"],
        "objective": parsed_goal["goal_type"],
        "campaign_objective": parsed_goal["default_objective"],
        "success_metric": parsed_goal["success_metric"],
        "target_segment": parsed_persona or "ALL_CUSTOMERS",
        "parser_reason": (
            f"Matched goal phrase '{matched_goal_phrase}'. "
            f"Matched audience phrase '{matched_persona_phrase}'."
            if matched_persona_phrase
            else f"Matched goal phrase '{matched_goal_phrase}'. No audience phrase detected."
        )
    }

if __name__ == "__main__":

    examples = [
        "Reduce churn among dormant customers",
        "Bring back inactive premium customers",
        "Increase average order value among premium customers",
        "Recommend complementary products to new parents",
        "Reward loyal customers",
    ]

    for example in examples:
        print("\nGoal:", example)
        print(parse_goal(example))
