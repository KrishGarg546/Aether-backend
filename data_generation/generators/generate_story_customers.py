"""
generate_story_customers.py
---------------------------
Aether CRM — Story Customer Generation Layer

Selects and enriches 75 "story customers" from the existing customers.csv.
Story customers carry narrative detail that powers:
    - realistic order generation,
    - campaign simulation,
    - churn modelling,
    - customer journey analytics,
    - recommendation use cases,
    - interview storytelling.

Run AFTER generate_customers.py.

Inputs:
    data/customers.csv

Outputs:
    data/story_customers.csv          (new file — 75 rows)
    data/customers.csv                (updated in-place — is_story_customer / story_customer_id)
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Deterministic seeds — must match generate_customers.py convention
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR          = Path(__file__).resolve().parent.parent
CUSTOMERS_PATH    = BASE_DIR / "data" / "customers.csv"
STORY_OUTPUT_PATH = BASE_DIR / "data" / "story_customers.csv"

# ---------------------------------------------------------------------------
# Story customer configuration
# ---------------------------------------------------------------------------
TOTAL_STORY_CUSTOMERS   = 75
CUSTOMERS_PER_STORY_TYPE = 15   # exactly 15 per group; 5 groups × 15 = 75

# Story type labels — used as keys throughout the script
STORY_TYPE_LOYAL_PARENTS    = "Loyal New Parents"
STORY_TYPE_PREMIUM_SELFCARE = "Premium Self-Care Enthusiasts"
STORY_TYPE_WELLNESS         = "Wellness Transformation Customers"
STORY_TYPE_BUDGET           = "Budget-Conscious Family Shoppers"
STORY_TYPE_DORMANT          = "Dormant Customers Returning"

STORY_TYPES = [
    STORY_TYPE_LOYAL_PARENTS,
    STORY_TYPE_PREMIUM_SELFCARE,
    STORY_TYPE_WELLNESS,
    STORY_TYPE_BUDGET,
    STORY_TYPE_DORMANT,
]

# ---------------------------------------------------------------------------
# Persona → story type mapping
# ---------------------------------------------------------------------------
STORY_TYPE_PERSONA = {
    STORY_TYPE_LOYAL_PARENTS:    "New Parents",
    STORY_TYPE_PREMIUM_SELFCARE: "Premium Self-Care",
    STORY_TYPE_WELLNESS:         "Wellness Seekers",
    STORY_TYPE_BUDGET:           "Budget Families",
    STORY_TYPE_DORMANT:          "Dormant Customers",
}

# ---------------------------------------------------------------------------
# Journey stages per story type
# ---------------------------------------------------------------------------
STORY_TYPE_JOURNEY_STAGE = {
    STORY_TYPE_LOYAL_PARENTS:    "Loyal",
    STORY_TYPE_PREMIUM_SELFCARE: "Advocate",
    STORY_TYPE_WELLNESS:         "Growing",
    STORY_TYPE_BUDGET:           "Stable",
    STORY_TYPE_DORMANT:          "Reactivated",
}

# ---------------------------------------------------------------------------
# Category interests per story type  [primary, secondary]
# ---------------------------------------------------------------------------
STORY_TYPE_CATEGORIES = {
    STORY_TYPE_LOYAL_PARENTS:    ("Baby Care",         "Family Essentials"),
    STORY_TYPE_PREMIUM_SELFCARE: ("Self Care",         "Wellness"),
    STORY_TYPE_WELLNESS:         ("Wellness",          "Self Care"),
    STORY_TYPE_BUDGET:           ("Family Essentials", "Baby Care"),
    STORY_TYPE_DORMANT:          ("Wellness",          "Family Essentials"),
}

# ---------------------------------------------------------------------------
# Engagement levels per story type
# Wellness and Dormant allow variance; others are fixed.
# ---------------------------------------------------------------------------
ENGAGEMENT_LEVELS = ["High", "Medium", "Low"]   # allowed values

STORY_TYPE_ENGAGEMENT = {
    STORY_TYPE_LOYAL_PARENTS:    ["High"],                 # always High
    STORY_TYPE_PREMIUM_SELFCARE: ["High"],                 # always High
    STORY_TYPE_WELLNESS:         ["Medium", "High"],       # mix
    STORY_TYPE_BUDGET:           ["Medium"],               # always Medium
    STORY_TYPE_DORMANT:          ["Low", "Medium"],        # mix
}

# ---------------------------------------------------------------------------
# Valid journey stage values for validation
# ---------------------------------------------------------------------------
VALID_JOURNEY_STAGES = {"Loyal", "Advocate", "Growing", "Stable", "Reactivated"}

# ---------------------------------------------------------------------------
# Story summary sentence templates
#
# Each template is a (opener, behaviour, channel) triple so that summaries
# are composable without being identical.  Placeholders:
#   {first_name}, {city}, {source}, {channel}
# ---------------------------------------------------------------------------

SUMMARY_TEMPLATES = {
    STORY_TYPE_LOYAL_PARENTS: [
        (
            "{first_name} from {city} joined Aether after discovering the brand through {source}.",
            "They regularly purchase baby skincare essentials and family wellness bundles, making them one of the brand's most consistent repeat buyers.",
            "They prefer receiving personalised recommendations via {channel}.",
        ),
        (
            "{first_name} became an Aether customer shortly after welcoming a new addition to the family in {city}.",
            "Since joining, they have reordered baby care products multiple times and show strong loyalty to trusted product lines.",
            "{first_name} relies on {channel} for order updates and product suggestions.",
        ),
        (
            "As a new parent in {city}, {first_name} turned to Aether for safe, trusted baby care products.",
            "Their consistent purchasing cadence and high product ratings reflect deep brand trust built over repeated positive experiences.",
            "Communication via {channel} has been the primary driver of repeat engagement.",
        ),
        (
            "{first_name} discovered Aether via {source} while researching newborn essentials in {city}.",
            "They have since built a reliable replenishment routine around baby care and family wellness categories.",
            "{first_name} actively engages with product drops shared on {channel}.",
        ),
    ],

    STORY_TYPE_PREMIUM_SELFCARE: [
        (
            "{first_name} from {city} found Aether through {source} while exploring premium skincare options.",
            "As a discerning self-care enthusiast, they gravitate towards high-quality formulations and values ingredient transparency.",
            "{first_name} responds strongly to curated content delivered via {channel}.",
        ),
        (
            "{first_name} treats self-care as a lifestyle investment and was drawn to Aether's premium positioning.",
            "Based in {city}, they consistently shop in the higher AOV tier, favouring skincare and wellness bundles.",
            "Digital campaigns via {channel} are their preferred discovery channel.",
        ),
        (
            "After discovering Aether via {source}, {first_name} in {city} became a regular in the premium self-care category.",
            "Their basket consistently reflects a preference for curated, efficacious products over volume-driven purchases.",
            "{first_name} engages most actively with personalised outreach through {channel}.",
        ),
        (
            "{first_name} is a self-care advocate in {city} who holds brand quality to a high standard.",
            "Acquired through {source}, they have maintained high average order values while exploring Aether's skincare range.",
            "They are most responsive to exclusive early-access offers shared via {channel}.",
        ),
    ],

    STORY_TYPE_WELLNESS: [
        (
            "{first_name} started their Aether journey modestly, picking up entry-level wellness products after discovering the brand via {source}.",
            "Over time, their order frequency and basket value have grown steadily, reflecting a deepening wellness commitment.",
            "They now actively engage with supplement recommendations delivered through {channel}.",
        ),
        (
            "Based in {city}, {first_name} began exploring Aether's wellness range following a personal health goal.",
            "What started as occasional supplement purchases has evolved into a structured wellness routine supported by Aether products.",
            "{first_name} relies on {channel} for personalised guidance on their next steps.",
        ),
        (
            "{first_name} was introduced to Aether through {source} and initially focused on one or two wellness SKUs.",
            "Their engagement has since broadened to include complementary self-care products as their confidence in the brand grew.",
            "Regular {channel} touchpoints have been instrumental in nurturing this growth trajectory.",
        ),
        (
            "In {city}, {first_name} sought a brand that could support a longer-term wellness transformation — and found it in Aether.",
            "Their purchase history shows a clear upward trend in both category breadth and spend, aligning with their personal health journey.",
            "{first_name} cites {channel} updates as a key driver of ongoing discovery.",
        ),
    ],

    STORY_TYPE_BUDGET: [
        (
            "{first_name} from {city} discovered Aether through {source} while looking for affordable family essentials.",
            "They prioritise value-for-money bundles and are quick to respond to promotional pricing on household staples.",
            "Offer alerts through {channel} consistently drive purchase decisions for {first_name}.",
        ),
        (
            "Managing a household budget carefully, {first_name} in {city} shops with Aether for trusted essentials at accessible price points.",
            "Their cart typically contains high-utility, frequently replenished items rather than premium or discretionary products.",
            "{first_name} engages most with discount-led campaigns communicated via {channel}.",
        ),
        (
            "{first_name} joined Aether via {source} seeking reliable family products without overspending.",
            "They demonstrate steady purchasing behaviour, gravitating toward value packs and bundle offers in the family essentials category.",
            "Promotions and reminders delivered through {channel} help sustain their purchase rhythm.",
        ),
        (
            "As a budget-conscious parent in {city}, {first_name} values Aether for its balance of quality and affordability.",
            "Their order history reflects careful spend management, with a clear preference for essential categories over premium lines.",
            "Timely {channel} communications are the primary conversion lever for this customer.",
        ),
    ],

    STORY_TYPE_DORMANT: [
        (
            "{first_name} had limited activity with Aether for several months before re-engaging via a reactivation campaign.",
            "Since returning, they have shown renewed interest in wellness and family-focused products, signalling potential for recovery.",
            "Re-engagement has been primarily driven by targeted outreach through {channel}.",
        ),
        (
            "After a period of inactivity, {first_name} in {city} reconnected with Aether following a personalised win-back campaign.",
            "Their recent browsing and purchase signals suggest a genuine rekindling of interest in the wellness category.",
            "{first_name} responds best to low-pressure, informational content via {channel}.",
        ),
        (
            "{first_name} was originally acquired through {source} but drifted away after initial purchases.",
            "A well-timed reactivation message brought them back, and early signals suggest they are rebuilding a relationship with the brand.",
            "Continued nurturing through {channel} will be key to converting this re-engagement into sustained loyalty.",
        ),
        (
            "Originally from {city}, {first_name} became dormant after early-stage purchases but returned following a targeted campaign.",
            "Their reactivation behaviour suggests cost or relevance were barriers — recent interactions indicate those barriers may be lowering.",
            "{first_name} now engages selectively with {channel} communications that feel personally relevant.",
        ),
    ],
}

# Map preferred_channel codes to friendly labels used in narrative text
CHANNEL_DISPLAY = {
    "EMAIL":     "email",
    "WHATSAPP":  "WhatsApp",
    "SMS":       "SMS",
    "RCS":       "RCS messaging",
}

# Map acquisition source codes to friendly labels used in narrative text
SOURCE_DISPLAY = {
    "ORGANIC":    "organic search",
    "INSTAGRAM":  "Instagram",
    "GOOGLE":     "Google",
    "REFERRAL":   "a personal referral",
    "WHATSAPP":   "a WhatsApp recommendation",
    "INFLUENCER": "an influencer recommendation",
}


# ---------------------------------------------------------------------------
# Helper: extract first name from full name
# ---------------------------------------------------------------------------
def _first_name(full_name: str) -> str:
    """Return the first token of a full name string."""
    return full_name.strip().split()[0]


# ---------------------------------------------------------------------------
# Helper: select story customers for one story type
# ---------------------------------------------------------------------------
def select_story_group(
    customers_df: pd.DataFrame,
    story_type: str,
    already_selected: set[str],
    n: int = CUSTOMERS_PER_STORY_TYPE,
) -> pd.DataFrame:
    """
    Deterministically select `n` eligible customers for a given story type.

    Eligibility criteria:
        - Persona matches STORY_TYPE_PERSONA[story_type].
        - customer_id not already assigned to another story group.

    The eligible pool is shuffled with a type-specific seed offset so each
    group's ordering is independent yet still reproducible.

    Args:
        customers_df:      Full customers DataFrame.
        story_type:        One of the STORY_TYPES constants.
        already_selected:  Set of customer_ids already assigned to other groups.
        n:                 Number of customers to select (default 15).

    Returns:
        DataFrame slice of exactly n selected customers.

    Raises:
        ValueError: If the eligible pool contains fewer than n candidates.
    """
    required_persona = STORY_TYPE_PERSONA[story_type]

    # Filter to matching persona, excluding already-selected customers
    eligible = customers_df[
        (customers_df["persona"] == required_persona) &
        (~customers_df["customer_id"].isin(already_selected))
    ].copy()

    if len(eligible) < n:
        raise ValueError(
            f"Insufficient eligible customers for '{story_type}': "
            f"need {n}, found {len(eligible)}"
        )

    # Shuffle deterministically using a story-type-specific seed offset
    # so group ordering is independent but reproducible
    type_seed = RANDOM_SEED + STORY_TYPES.index(story_type)
    eligible_shuffled = eligible.sample(frac=1, random_state=type_seed)

    return eligible_shuffled.head(n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Helper: generate engagement level for a customer given story type
# ---------------------------------------------------------------------------
def assign_engagement_level(story_type: str, idx: int) -> str:
    """
    Assign an engagement level for a customer within a story group.

    For story types with a single allowed level, that level is always returned.
    For story types with multiple options, the assignment cycles through the
    allowed values to ensure diversity within the group while remaining
    deterministic (no random.choice — uses positional index modulo).

    Args:
        story_type: One of the STORY_TYPES constants.
        idx:        Position of the customer within their story group (0-based).

    Returns:
        One of "High", "Medium", "Low".
    """
    options = STORY_TYPE_ENGAGEMENT[story_type]
    # Cycle through options by position; single-option groups always return same value
    return options[idx % len(options)]


# ---------------------------------------------------------------------------
# Helper: build a story summary for one customer
# ---------------------------------------------------------------------------
def build_story_summary(row: pd.Series, story_type: str, idx: int) -> str:
    """
    Compose a 2–3 sentence personalised story summary from reusable templates.

    Template selection uses `idx` modulo the template pool size so summaries
    vary across the 15 customers in each group without pure randomness.

    Args:
        row:        A single row from the selected customers DataFrame.
        story_type: One of the STORY_TYPES constants.
        idx:        Position within the story group (0-based) — drives template cycling.

    Returns:
        A 2–3 sentence string narrative.
    """
    templates = SUMMARY_TEMPLATES[story_type]
    opener, behaviour, channel_line = templates[idx % len(templates)]

    first = _first_name(str(row["name"]))
    city  = str(row["city"])

    # Translate coded values to readable narrative labels
    source_label  = SOURCE_DISPLAY.get(str(row["source"]),           str(row["source"]))
    channel_label = CHANNEL_DISPLAY.get(str(row["preferred_channel"]), str(row["preferred_channel"]))

    # Apply placeholders — not all templates use every variable
    def fill(template: str) -> str:
        return (
            template
            .replace("{first_name}", first)
            .replace("{city}",       city)
            .replace("{source}",     source_label)
            .replace("{channel}",    channel_label)
        )

    sentences = [fill(opener), fill(behaviour), fill(channel_line)]

    # The opener and behaviour are always included; the channel line adds
    # a natural third sentence, making summaries feel complete without padding.
    return " ".join(s.strip() for s in sentences)


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------
def generate_story_customers(customers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Select 75 story customers (15 per story type) and build their enrichment records.

    Process:
        1. Iterate through STORY_TYPES in order.
        2. For each type, filter eligible customers and select exactly 15.
        3. Track selected customer_ids to prevent cross-group duplication.
        4. Assign story metadata: story_type, journey_stage, categories,
           engagement_level, and a personalised story_summary.
        5. Assign sequential story_customer_ids: SC001 … SC075.
        6. Return a clean 75-row DataFrame.

    Args:
        customers_df: Full 10,000-row customers DataFrame.

    Returns:
        story_df: 75-row DataFrame ready for CSV export.
    """
    already_selected: set[str] = set()
    group_records: list[dict] = []

    for story_type in STORY_TYPES:
        # ------------------------------------------------------------------
        # Select the group
        # ------------------------------------------------------------------
        group_df = select_story_group(customers_df, story_type, already_selected)

        # Mark these customer_ids as taken so no downstream group can reuse them
        already_selected.update(group_df["customer_id"].tolist())

        # ------------------------------------------------------------------
        # Build enrichment rows
        # ------------------------------------------------------------------
        primary_cat, secondary_cat = STORY_TYPE_CATEGORIES[story_type]
        journey_stage              = STORY_TYPE_JOURNEY_STAGE[story_type]

        for idx, (_, row) in enumerate(group_df.iterrows()):
            engagement = assign_engagement_level(story_type, idx)
            summary    = build_story_summary(row, story_type, idx)

            group_records.append({
                # story_customer_id assigned after all groups are collected
                "customer_id":                row["customer_id"],
                "story_type":                 story_type,
                "journey_stage":              journey_stage,
                "primary_category_interest":  primary_cat,
                "secondary_category_interest": secondary_cat,
                "engagement_level":           engagement,
                "story_summary":              summary,
            })

    # ------------------------------------------------------------------
    # Assign sequential story_customer_ids
    # ------------------------------------------------------------------
    story_df = pd.DataFrame(group_records)
    story_df.insert(
        0,
        "story_customer_id",
        [f"SC{str(i).zfill(3)}" for i in range(1, len(story_df) + 1)],
    )

    return story_df


# ---------------------------------------------------------------------------
# customers.csv update
# ---------------------------------------------------------------------------
def update_customers_csv(customers_df: pd.DataFrame, story_df: pd.DataFrame) -> pd.DataFrame:
    """
    Write story customer flags back onto the master customers DataFrame.

    For each selected story customer:
        is_story_customer  → True
        story_customer_id  → e.g. "SC001"

    All other rows remain:
        is_story_customer  → False
        story_customer_id  → ""

    Args:
        customers_df: Full 10,000-row customers DataFrame (will not be mutated).
        story_df:     75-row story customers DataFrame.

    Returns:
        Updated copy of customers_df.
    """
    updated = customers_df.copy()

    # Build a lookup: customer_id → story_customer_id
    sc_map = dict(zip(story_df["customer_id"], story_df["story_customer_id"]))

    # Reset all customers to safe defaults before applying story flags
    # (guards against partial updates if the script is re-run on a dirty file)
    updated["is_story_customer"] = False
    updated["story_customer_id"] = ""

    # Apply flags for selected story customers
    mask = updated["customer_id"].isin(sc_map)
    updated.loc[mask, "is_story_customer"] = True
    updated.loc[mask, "story_customer_id"] = updated.loc[mask, "customer_id"].map(sc_map)

    return updated


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(story_df: pd.DataFrame, updated_customers_df: pd.DataFrame) -> None:
    """
    Run data-quality checks on the story customers output and the updated
    customers DataFrame.  Raises AssertionError immediately on any violation.

    Args:
        story_df:              75-row story customers DataFrame.
        updated_customers_df:  Updated full customers DataFrame.
    """
    # ------------------------------------------------------------------
    # Story customers DataFrame checks
    # ------------------------------------------------------------------
    assert len(story_df) == TOTAL_STORY_CUSTOMERS, (
        f"Expected {TOTAL_STORY_CUSTOMERS} story customers, got {len(story_df)}"
    )

    assert story_df["story_customer_id"].nunique() == TOTAL_STORY_CUSTOMERS, (
        "Duplicate story_customer_ids detected"
    )

    assert story_df["customer_id"].nunique() == TOTAL_STORY_CUSTOMERS, (
        "Duplicate customer_ids in story customers — cross-group overlap detected"
    )

    # Exactly 15 customers per story type
    story_type_counts = story_df["story_type"].value_counts()
    for story_type in STORY_TYPES:
        count = story_type_counts.get(story_type, 0)
        assert count == CUSTOMERS_PER_STORY_TYPE, (
            f"Story type '{story_type}': expected {CUSTOMERS_PER_STORY_TYPE}, got {count}"
        )

    # All selected customers match required personas
    # Build a lookup: customer_id → persona from the updated customers DataFrame
    persona_lookup = updated_customers_df.set_index("customer_id")["persona"]
    for _, row in story_df.iterrows():
        actual_persona   = persona_lookup.get(row["customer_id"])
        expected_persona = STORY_TYPE_PERSONA[row["story_type"]]
        assert actual_persona == expected_persona, (
            f"Customer {row['customer_id']} has persona '{actual_persona}' "
            f"but story type '{row['story_type']}' requires '{expected_persona}'"
        )

    # Journey stage values are all valid
    invalid_stages = set(story_df["journey_stage"]) - VALID_JOURNEY_STAGES
    assert not invalid_stages, (
        f"Invalid journey_stage values detected: {invalid_stages}"
    )

    # Engagement level values are all valid
    invalid_engagement = set(story_df["engagement_level"]) - set(ENGAGEMENT_LEVELS)
    assert not invalid_engagement, (
        f"Invalid engagement_level values detected: {invalid_engagement}"
    )

    # No null or empty story summaries
    assert story_df["story_summary"].notna().all(), (
        "Null story_summary values detected"
    )
    assert (story_df["story_summary"].str.strip() != "").all(), (
        "Empty story_summary values detected"
    )

    # ------------------------------------------------------------------
    # Updated customers.csv checks
    # ------------------------------------------------------------------
    story_customer_ids_in_master = updated_customers_df[
        updated_customers_df["is_story_customer"]
    ]["customer_id"].tolist()

    assert len(story_customer_ids_in_master) == TOTAL_STORY_CUSTOMERS, (
        f"Expected {TOTAL_STORY_CUSTOMERS} story flags in customers.csv, "
        f"found {len(story_customer_ids_in_master)}"
    )

    # Every story customer_id in story_df must appear as flagged in customers.csv
    flagged_set  = set(story_customer_ids_in_master)
    selected_set = set(story_df["customer_id"])
    assert flagged_set == selected_set, (
        "Mismatch between customers flagged in customers.csv and story_df customer_ids"
    )

    # story_customer_id values in customers.csv must match story_df
    flagged_rows = updated_customers_df[updated_customers_df["is_story_customer"]].copy()
    sc_map_from_df = dict(zip(story_df["customer_id"], story_df["story_customer_id"]))
    for _, row in flagged_rows.iterrows():
        expected_sc_id = sc_map_from_df.get(row["customer_id"])
        assert row["story_customer_id"] == expected_sc_id, (
            f"story_customer_id mismatch for {row['customer_id']}: "
            f"expected {expected_sc_id}, got {row['story_customer_id']}"
        )

    print("✅  All validation checks passed.\n")


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def print_summary(story_df: pd.DataFrame) -> None:
    """Print a human-readable summary for quick sanity checking."""
    sep = "-" * 60

    print(sep)
    print(f"  Story customers generated : {len(story_df)}")
    print(sep)

    print("\n  By story type:")
    for story_type, count in story_df["story_type"].value_counts().items():
        print(f"    {story_type:<38} {count:>3}")

    print("\n  By journey stage:")
    for stage, count in story_df["journey_stage"].value_counts().items():
        print(f"    {stage:<15} {count:>3}")

    print("\n  By engagement level:")
    for level, count in story_df["engagement_level"].value_counts().items():
        print(f"    {level:<10} {count:>3}")

    print("\n  Example records (first 5):")
    print(sep)
    sample_cols = [
        "story_customer_id", "customer_id", "story_type",
        "journey_stage", "engagement_level",
    ]
    print(story_df[sample_cols].head(5).to_string(index=False))

    print(f"\n  Sample story summary (SC001):")
    print(sep)
    first_summary = story_df.loc[story_df["story_customer_id"] == "SC001", "story_summary"].values[0]
    print(f"  {first_summary}")
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if STORY_OUTPUT_PATH.exists():
        raise FileExistsError(
            f"{STORY_OUTPUT_PATH} already exists. "
            "Delete existing story data before regenerating."
        )
    print("\n🚀  Aether CRM — Generating story customers...\n")

    # Ensure output directory exists
    STORY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load customers
    # ------------------------------------------------------------------
    if not CUSTOMERS_PATH.exists():
        raise FileNotFoundError(
            f"customers.csv not found at {CUSTOMERS_PATH}. "
            "Run generate_customers.py first."
        )

    customers_df = pd.read_csv(CUSTOMERS_PATH, dtype={"phone": str})
    print(f"  Loaded {len(customers_df):,} customers from {CUSTOMERS_PATH}\n")

    # ------------------------------------------------------------------
    # Generate story customers
    # ------------------------------------------------------------------
    story_df = generate_story_customers(customers_df)

    # ------------------------------------------------------------------
    # Apply story flags back to customers DataFrame
    # ------------------------------------------------------------------
    updated_customers_df = update_customers_csv(customers_df, story_df)

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    validate(story_df, updated_customers_df)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print_summary(story_df)

    # ------------------------------------------------------------------
    # Export story_customers.csv
    # ------------------------------------------------------------------
    story_df.to_csv(STORY_OUTPUT_PATH, index=False)
    print(f"\n✅  Exported {len(story_df)} story customers → {STORY_OUTPUT_PATH}")

    # ------------------------------------------------------------------
    # Overwrite customers.csv with updated flags
    # ------------------------------------------------------------------
    updated_customers_df.to_csv(CUSTOMERS_PATH, index=False)
    print(f"✅  Updated customers.csv → {CUSTOMERS_PATH}\n")


if __name__ == "__main__":
    main()