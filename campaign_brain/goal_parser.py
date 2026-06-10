GOAL_CATALOG = {
    "reduce churn": {
        "goal_type": "reduce_churn",
        "success_metric": "retention_rate",
        "default_objective": "reactivation",
    },

    "increase repeat purchases": {
        "goal_type": "increase_repeat_purchases",
        "success_metric": "repeat_purchase_rate",
        "default_objective": "cross_sell",
    },

    "increase customer lifetime value": {
        "goal_type": "increase_clv",
        "success_metric": "average_clv",
        "default_objective": "upsell",
    },

    "promote new products": {
        "goal_type": "promote_products",
        "success_metric": "campaign_conversion_rate",
        "default_objective": "awareness",
    },

    "reward loyal customers": {
        "goal_type": "reward_loyalty",
        "success_metric": "loyalty_engagement_rate",
        "default_objective": "loyalty",
    }
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

    goal_lower = goal.lower()

    parsed_goal = None
    parsed_persona = None
    matched_goal_phrase = None
    matched_persona_phrase = None

    # Identify goal type
    for goal_phrase, goal_info in GOAL_CATALOG.items():
        if goal_phrase in goal_lower:
            parsed_goal = goal_info.copy()
            matched_goal_phrase = goal_phrase
            break

    if parsed_goal is None:
        return {
    "original_goal": goal,
    "goal_type": "unknown",
    "campaign_objective": "manual_review",
    "success_metric": None,
    "target_segment": "ALL_CUSTOMERS",
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
        "Increase repeat purchases among new parents",
        "Reward loyal customers",
    ]

    for example in examples:
        print("\nGoal:", example)
        print(parse_goal(example))

