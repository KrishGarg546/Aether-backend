"""
================================================================================
Aether CRM — Synthetic Data Generator
File: generate_orders.py
================================================================================

PURPOSE
-------
Generates a realistic synthetic order dataset (data/orders.csv) representing
customer purchasing behaviour for the Aether family wellness brand.

The resulting dataset is designed to support:
  - RFM (Recency, Frequency, Monetary) analysis
  - Customer Lifetime Value (CLV) estimation
  - Product recommendation systems
  - Cohort analysis
  - Churn modelling
  - Campaign attribution
  - Behavioural segmentation
  - Dashboard demonstrations

INPUTS
------
  data/customers.csv      — Customer master with persona labels
  data/products.csv       — Product catalogue with prices and categories
  data/story_customers.csv — Curated story customers for narrative-rich demos

OUTPUT
------
  data/orders.csv         — ~40,000–50,000 orders (emergent from behaviour rules)

DESIGN PRINCIPLES
-----------------
  - Deterministic: RANDOM_SEED = 42 ensures full reproducibility
  - Persona-driven: each customer segment exhibits distinct purchasing patterns
  - Seasonality-aware: real-world uplift events modelled across 2024–2026
  - India-realistic: payment methods match Indian e-commerce distributions
  - Story-amplified: story customers produce highly interpretable, demo-ready rows
  - Validated: strict post-generation checks catch any schema or logic drift


================================================================================
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

# ==============================================================================
# CONSTANTS
# ==============================================================================

RANDOM_SEED = 42  # Guarantees deterministic, reproducible output

# ---------------------------------------------------------------------------
# Date window for all generated orders
# ---------------------------------------------------------------------------
ORDER_START_DATE = date(2024, 6, 1)
ORDER_END_DATE   = date(2026, 6, 30)

# ---------------------------------------------------------------------------
# Allowed categorical values — validated post-generation
# ---------------------------------------------------------------------------
ALLOWED_DISCOUNTS       = {0, 5, 10, 15, 20, 25, 30}
ALLOWED_CHANNELS        = {"WEBSITE", "APP", "WHATSAPP"}
ALLOWED_PAYMENT_METHODS = {"UPI", "CARD", "COD", "NETBANKING"}

# ---------------------------------------------------------------------------
# Quantity bounds (business rule: 1–4 units per line item)
# ---------------------------------------------------------------------------
QTY_MIN = 1
QTY_MAX = 4

# ---------------------------------------------------------------------------
# I/O paths — relative to project root
# ---------------------------------------------------------------------------
INPUT_CUSTOMERS_PATH       = "data/customers.csv"
INPUT_PRODUCTS_PATH        = "data/products.csv"
INPUT_STORY_CUSTOMERS_PATH = "data/story_customers.csv"
OUTPUT_ORDERS_PATH         = "data/orders.csv"


# ==============================================================================
# PERSONA CONFIGURATION
# ==============================================================================
# Each entry defines the probabilistic behavioural profile for a customer
# segment.  These weights are calibrated to produce realistic but clearly
# distinguishable patterns for interview / demo purposes.
#
# Keys used per persona:
#   orders_range       : (min, max) total lifetime orders for a typical customer
#   category_weights   : dict mapping product category → relative sampling weight
#   discount_weights   : dict mapping discount_pct → relative sampling weight
#   channel_weights    : dict mapping channel → relative sampling weight
#   payment_weights    : dict mapping payment method → relative sampling weight
#   qty_weights        : list of 4 weights for quantity 1,2,3,4
#   story_multiplier   : factor applied to orders_range for story customers
# ==============================================================================

PERSONA_CONFIG = {

    # -------------------------------------------------------------------------
    # New Parents — moderate-to-high frequency, baby care focus
    # -------------------------------------------------------------------------
    "New Parents": {
        "orders_range": (4, 12),
        "category_weights": {
            "Baby Care":        0.45,
            "Family Essentials": 0.30,
            "Wellness":         0.10,
            "Self-Care":        0.10,
            "Nutrition":        0.05,
        },
        "discount_weights":  {0: 25, 5: 20, 10: 25, 15: 15, 20: 10, 25: 4, 30: 1},
        "channel_weights":   {"WEBSITE": 0.45, "APP": 0.40, "WHATSAPP": 0.15},
        "payment_weights":   {"UPI": 0.45, "CARD": 0.30, "COD": 0.15, "NETBANKING": 0.10},
        # Family essentials often bought in multiples (qty 2–3 common)
        "qty_weights":       [0.25, 0.40, 0.25, 0.10],
        "story_multiplier":  2.0,   # story New Parents place many more orders
    },

    # -------------------------------------------------------------------------
    # Premium Self-Care — lower frequency, high-value, minimal discounts
    # -------------------------------------------------------------------------
    "Premium Self-Care": {
        "orders_range": (2, 7),
        "category_weights": {
            "Self-Care":        0.55,
            "Wellness":         0.25,
            "Nutrition":        0.15,
            "Family Essentials": 0.04,
            "Baby Care":        0.01,
        },
        "discount_weights":  {0: 60, 5: 20, 10: 12, 15: 5, 20: 2, 25: 1, 30: 0},
        "channel_weights":   {"WEBSITE": 0.35, "APP": 0.55, "WHATSAPP": 0.10},
        "payment_weights":   {"UPI": 0.25, "CARD": 0.60, "COD": 0.05, "NETBANKING": 0.10},
        # Premium customers typically buy 1 unit of a single item
        "qty_weights":       [0.65, 0.25, 0.08, 0.02],
        "story_multiplier":  1.5,
    },

    # -------------------------------------------------------------------------
    # Wellness Seekers — growing engagement, wellness preference
    # -------------------------------------------------------------------------
    "Wellness Seekers": {
        "orders_range": (3, 10),
        "category_weights": {
            "Wellness":         0.50,
            "Nutrition":        0.25,
            "Self-Care":        0.15,
            "Family Essentials": 0.07,
            "Baby Care":        0.03,
        },
        "discount_weights":  {0: 35, 5: 25, 10: 20, 15: 10, 20: 7, 25: 2, 30: 1},
        "channel_weights":   {"WEBSITE": 0.30, "APP": 0.60, "WHATSAPP": 0.10},
        "payment_weights":   {"UPI": 0.55, "CARD": 0.30, "COD": 0.05, "NETBANKING": 0.10},
        "qty_weights":       [0.45, 0.35, 0.15, 0.05],
        "story_multiplier":  1.8,
    },

    # -------------------------------------------------------------------------
    # Budget Families — moderate frequency, high discount sensitivity
    # -------------------------------------------------------------------------
    "Budget Families": {
        "orders_range": (4, 12),
        "category_weights": {
            "Family Essentials": 0.50,
            "Baby Care":        0.20,
            "Nutrition":        0.15,
            "Wellness":         0.10,
            "Self-Care":        0.05,
        },
        "discount_weights":  {0: 5, 5: 10, 10: 20, 15: 25, 20: 20, 25: 12, 30: 8},
        "channel_weights":   {"WEBSITE": 0.50, "APP": 0.25, "WHATSAPP": 0.25},
        "payment_weights":   {"UPI": 0.40, "CARD": 0.10, "COD": 0.40, "NETBANKING": 0.10},
        # Bulk buying is common for budget-sensitive shoppers
        "qty_weights":       [0.15, 0.30, 0.35, 0.20],
        "story_multiplier":  1.6,
    },

    # -------------------------------------------------------------------------
    # Dormant Customers — infrequent, with reactivation bursts
    # -------------------------------------------------------------------------
    "Dormant Customers": {
        "orders_range": (1, 4),
        "category_weights": {
            "Family Essentials": 0.30,
            "Wellness":         0.25,
            "Self-Care":        0.20,
            "Baby Care":        0.15,
            "Nutrition":        0.10,
        },
        "discount_weights":  {0: 15, 5: 15, 10: 20, 15: 20, 20: 15, 25: 10, 30: 5},
        "channel_weights":   {"WEBSITE": 0.55, "APP": 0.20, "WHATSAPP": 0.25},
        "payment_weights":   {"UPI": 0.35, "CARD": 0.25, "COD": 0.30, "NETBANKING": 0.10},
        "qty_weights":       [0.50, 0.30, 0.15, 0.05],
        "story_multiplier":  1.3,
    },
}

# Fallback config for any persona label not explicitly listed above.
# This prevents KeyError on unseen segment values in customers.csv.
DEFAULT_PERSONA_CONFIG = {
    "orders_range": (4, 12),
    "category_weights": {
        "Family Essentials": 0.30,
        "Wellness":          0.25,
        "Self-Care":         0.20,
        "Baby Care":         0.15,
        "Nutrition":         0.10,
    },
    "discount_weights":  {0: 30, 5: 20, 10: 20, 15: 15, 20: 10, 25: 4, 30: 1},
    "channel_weights":   {"WEBSITE": 0.40, "APP": 0.40, "WHATSAPP": 0.20},
    "payment_weights":   {"UPI": 0.40, "CARD": 0.30, "COD": 0.20, "NETBANKING": 0.10},
    "qty_weights":       [0.35, 0.35, 0.20, 0.10],
    "story_multiplier":  1.5,
}

# ==============================================================================
# STORY CUSTOMER BEHAVIOUR OVERRIDES
# ==============================================================================
# Story customers receive behavioural amplification so they produce
# highly interpretable, demo-ready patterns in analytics dashboards.
#
# story_type values must match those in story_customers.csv.
# Unrecognised story types fall through to the base persona config.
# ==============================================================================

STORY_TYPE_OVERRIDES = {
    # Loyal New Parents — very high frequency, near-zero churn
    "Loyal New Parents": {
        "orders_range":     (20, 35),
        "discount_weights": {0: 30, 5: 25, 10: 20, 15: 15, 20: 8, 25: 2, 30: 0},
        "qty_weights":      [0.20, 0.40, 0.30, 0.10],
    },
    # Premium Enthusiasts — consistently high spend, rare discounts
    "Premium Self-Care Enthusiasts": {
        "orders_range":     (12, 22),
        "discount_weights": {0: 75, 5: 15, 10: 8, 15: 2, 20: 0, 25: 0, 30: 0},
        "qty_weights":      [0.70, 0.22, 0.06, 0.02],
    },
    # Wellness Transformation — order frequency climbs over time (handled in
    # date generation by shifting weights toward later months)
    "Wellness Transformation Customers": {
        "orders_range":     (14, 24),
        "discount_weights": {0: 30, 5: 25, 10: 22, 15: 12, 20: 8, 25: 2, 30: 1},
        "qty_weights":      [0.40, 0.35, 0.18, 0.07],
    },
    # Budget Family Shoppers — maximum promo sensitivity
    "Budget-Concious Family Shoppers": {
        "orders_range":     (16, 28),
        "discount_weights": {0: 2, 5: 5, 10: 15, 15: 25, 20: 25, 25: 18, 30: 10},
        "qty_weights":      [0.10, 0.25, 0.40, 0.25],
    },
    # Dormant Returning Customers — long gap, then renewed burst
    "Dormant Customers Returning": {
        "orders_range":     (6, 12),
        "discount_weights": {0: 10, 5: 15, 10: 20, 15: 22, 20: 18, 25: 10, 30: 5},
        "qty_weights":      [0.45, 0.30, 0.15, 0.10],
    },
}


# ==============================================================================
# SEASONALITY WEIGHTS
# ==============================================================================
# Monthly uplift multipliers applied during order date generation.
# A value of 1.0 is baseline; values > 1.0 increase order density in that month.
#
# Business rationale:
#   Jan  — New Year / wellness resolutions spike
#   May  — Mother's Day self-care uplift
#   Aug  — Back-to-school family purchasing
#   Oct  — Dussehra / festive gifting begins
#   Nov  — Diwali / festive gifting peak (Indian e-commerce's biggest month)
# ==============================================================================

MONTH_WEIGHTS = {
    1:  1.40,   # January — New Year wellness resolutions
    2:  0.90,
    3:  0.95,
    4:  1.00,
    5:  1.15,   # May — Mother's Day uplift
    6:  0.95,
    7:  0.90,
    8:  1.10,   # August — Back-to-school
    9:  1.00,
    10: 1.25,   # October — festive season begins
    11: 1.35,   # November — Diwali peak
    12: 1.05,
}


# ==============================================================================
# HELPER: DATA LOADING
# ==============================================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load and lightly validate the three input files required for order
    generation.

    Returns
    -------
    customers : pd.DataFrame
        Customer master — must contain [customer_id, persona, join_date].
    products : pd.DataFrame
        Product catalogue — must contain [product_id, category, price].
    story_customers : pd.DataFrame
        Curated story customers — must contain [customer_id, story_type].

    Raises
    ------
    FileNotFoundError
        If any of the three required input files are missing.
    AssertionError
        If required columns are absent from a file.
    """
    print("=" * 70)
    print("LOADING INPUT FILES")
    print("=" * 70)

    # --- customers.csv -------------------------------------------------------
    print(f"  Loading customers from : {INPUT_CUSTOMERS_PATH}")
    customers = pd.read_csv(INPUT_CUSTOMERS_PATH)
    assert "customer_id" in customers.columns, "customers.csv missing 'customer_id'"
    assert "persona"     in customers.columns, "customers.csv missing 'persona'"
    assert "join_date"   in customers.columns, "customers.csv missing 'join_date'"
    customers["join_date"] = pd.to_datetime(customers["join_date"]).dt.date
    print(f"    → {len(customers):,} customers loaded")

    # --- products.csv --------------------------------------------------------
    print(f"  Loading products from  : {INPUT_PRODUCTS_PATH}")
    products = pd.read_csv(INPUT_PRODUCTS_PATH)
    assert "product_id" in products.columns, "products.csv missing 'product_id'"
    assert "category"   in products.columns, "products.csv missing 'category'"
    assert "price"      in products.columns, "products.csv missing 'price'"
    print(f"    → {len(products):,} products loaded")

    print("    Categories:", sorted(products["category"].unique()))

    # --- story_customers.csv -------------------------------------------------
    print(f"  Loading story customers: {INPUT_STORY_CUSTOMERS_PATH}")
    story_customers = pd.read_csv(INPUT_STORY_CUSTOMERS_PATH)
    assert "customer_id" in story_customers.columns, \
        "story_customers.csv missing 'customer_id'"
    assert "story_type"  in story_customers.columns, \
        "story_customers.csv missing 'story_type'"
    print(f"    → {len(story_customers):,} story customers loaded")
    print()

    return customers, products, story_customers


# ==============================================================================
# HELPER: PRODUCT LOOKUP TABLE
# ==============================================================================

def build_product_lookup(
    products: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """
    Build a mapping from product category to the subset of products in that
    category.  This allows O(1) category-based product sampling during the
    inner order generation loop.

    Parameters
    ----------
    products : pd.DataFrame
        Full product catalogue with [product_id, category, price].

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys are category strings; values are filtered DataFrames.
    """
    lookup = {}
    for category, group in products.groupby("category"):
        lookup[category] = group.reset_index(drop=True)
    return lookup


# ==============================================================================
# HELPER: WEIGHTED RANDOM CHOICE
# ==============================================================================

def weighted_choice(options: list, weights: list, rng: random.Random) -> object:
    """
    Select a single item from *options* using the supplied relative *weights*.

    This thin wrapper around random.choices keeps the inner loop readable and
    ensures we always pass through the seeded RNG rather than the global state.

    Parameters
    ----------
    options : list
        Items to sample from.
    weights : list
        Relative sampling weights (need not sum to 1).
    rng : random.Random
        Seeded random instance for determinism.

    Returns
    -------
    object
        A single item drawn from options.
    """
    return rng.choices(options, weights=weights, k=1)[0]


# ==============================================================================
# HELPER: DATE GENERATION
# ==============================================================================

def generate_order_dates(
    n_orders: int,
    join_date: date,
    story_type: str | None,
    rng: random.Random,
) -> list[date]:
    """
    Generate *n_orders* order dates for a single customer, respecting:
      1. Dates must fall on or after the customer's join_date.
      2. Dates must not exceed ORDER_END_DATE.
      3. Monthly seasonality weights (MONTH_WEIGHTS).
      4. Wellness Transformation story type: order density skews toward
         later dates to simulate a customer whose engagement increases over
         time (progressive onboarding arc).

    Strategy
    --------
    We build a pool of all valid calendar dates between join_date and
    ORDER_END_DATE, assign each a weight derived from MONTH_WEIGHTS (and
    position-in-window for Wellness Transformation), then sample without
    replacement (capped at pool size) or with replacement when n_orders
    exceeds available unique dates.

    Parameters
    ----------
    n_orders : int
        How many order dates to generate for this customer.
    join_date : date
        Customer's signup date — orders cannot precede this.
    story_type : str | None
        Story type label (None for non-story customers).
    rng : random.Random
        Seeded RNG.

    Returns
    -------
    list[date]
        Sorted list of order dates, length == n_orders.
    """
    # Compute valid date window for this customer
    effective_start = max(join_date, ORDER_START_DATE)
    effective_end   = ORDER_END_DATE

    # Edge-case: customer joined after the global end date — return empty
    if effective_start > effective_end:
        return []

    # Build list of all valid calendar days
    total_days = (effective_end - effective_start).days + 1
    all_dates  = [effective_start + timedelta(days=d) for d in range(total_days)]

    # Assign seasonality weights to each date
    if story_type == "Wellness Transformation":
        # Progressive engagement: weight increases linearly from start to end
        # of the window so later dates are disproportionately sampled.
        weights = []
        for i, d in enumerate(all_dates):
            base_w     = MONTH_WEIGHTS.get(d.month, 1.0)
            # Linear ramp: ranges from 0.3× to 1.7× the base weight
            ramp_factor = 0.3 + 1.4 * (i / max(len(all_dates) - 1, 1))
            weights.append(base_w * ramp_factor)
    elif story_type == "Dormant Returning Customers":
        # Long gap followed by a burst: suppress the first 60% of the window,
        # then amplify the final 40% (the "return" phase).
        threshold_idx = int(0.60 * len(all_dates))
        weights = []
        for i, d in enumerate(all_dates):
            base_w = MONTH_WEIGHTS.get(d.month, 1.0)
            if i < threshold_idx:
                weights.append(base_w * 0.15)   # near-dormant period
            else:
                weights.append(base_w * 2.50)   # reactivation burst
    else:
        weights = [MONTH_WEIGHTS.get(d.month, 1.0) for d in all_dates]

    # Clamp n_orders to available dates to avoid infinite retries
    n_to_draw = min(n_orders, len(all_dates))

    # Sample dates using weighted selection (with replacement to allow repeat
    # purchases on the same day, which is realistic for a multi-SKU brand)
    chosen = rng.choices(all_dates, weights=weights, k=n_to_draw)

    return sorted(chosen)


# ==============================================================================
# HELPER: PRODUCT SAMPLING
# ==============================================================================

def sample_product(
    category_weights: dict[str, float],
    product_lookup: dict[str, pd.DataFrame],
    available_categories: set[str],
    rng: random.Random,
) -> pd.Series | None:
    """
    Sample a single product row from products.csv using persona-driven
    category preferences.

    1. Filter category_weights to only categories that exist in the
       product catalogue (guards against catalogue changes).
    2. Sample a category proportionally.
    3. Sample a product uniformly within that category.

    Parameters
    ----------
    category_weights : dict[str, float]
        Persona's category preference map.
    product_lookup : dict[str, pd.DataFrame]
        Pre-built lookup by category.
    available_categories : set[str]
        Set of categories actually present in products.csv.
    rng : random.Random
        Seeded RNG.

    Returns
    -------
    pd.Series or None
        A single product row, or None if no valid category found.
    """
    # Intersect persona preferences with catalogue categories
    valid = {
        cat: w
        for cat, w in category_weights.items()
        if cat in available_categories
    }
    if not valid:
        return None

    cats    = list(valid.keys())
    weights = list(valid.values())
    chosen_cat = weighted_choice(cats, weights, rng)

    # Uniform sample within category
    cat_df = product_lookup[chosen_cat]
    idx    = rng.randint(0, len(cat_df) - 1)
    return cat_df.iloc[idx]


# ==============================================================================
# HELPER: EFFECTIVE PERSONA CONFIG
# ==============================================================================

def get_persona_config(
    persona: str,
    is_story: bool,
    story_type: str | None,
) -> dict:
    """
    Resolve the effective behavioural configuration for a customer by merging:
      1. Base persona config (or DEFAULT_PERSONA_CONFIG for unknown personas).
      2. Story-type overrides (if the customer is a story customer).

    Story overrides are applied as shallow updates: only the keys present in
    STORY_TYPE_OVERRIDES[story_type] replace the corresponding base values.
    This means a story customer inherits all non-overridden properties (e.g.
    category_weights, channel_weights) from their parent persona.

    Parameters
    ----------
    persona : str
        Customer's persona label from customers.csv.
    is_story : bool
        Whether this customer appears in story_customers.csv.
    story_type : str | None
        Story type label (None for non-story customers).

    Returns
    -------
    dict
        Merged configuration dictionary ready for order generation.
    """
    # Start with base persona or fallback default
    config = dict(PERSONA_CONFIG.get(persona, DEFAULT_PERSONA_CONFIG))

    # Deep-copy mutable sub-dicts to prevent cross-customer mutation
    config["category_weights"] = dict(config["category_weights"])
    config["discount_weights"] = dict(config["discount_weights"])
    config["channel_weights"]  = dict(config["channel_weights"])
    config["payment_weights"]  = dict(config["payment_weights"])
    config["qty_weights"]      = list(config["qty_weights"])

    if is_story and story_type and story_type in STORY_TYPE_OVERRIDES:
        overrides = STORY_TYPE_OVERRIDES[story_type]
        for key, value in overrides.items():
            # Overrides for dict values are merged; list/tuple are replaced
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key] = dict(value)
            else:
                config[key] = value

    return config


# ==============================================================================
# CORE GENERATOR: ORDERS FOR A SINGLE CUSTOMER
# ==============================================================================

def generate_customer_orders(
    customer: pd.Series,
    is_story: bool,
    story_type: str | None,
    story_customer_id: str | None,
    product_lookup: dict[str, pd.DataFrame],
    available_categories: set[str],
    rng: random.Random,
    order_id_counter: list[int],
) -> list[dict]:
    """
    Generate all orders for a single customer and return them as a list of
    row dictionaries ready for DataFrame construction.

    Business logic applied
    ----------------------
    - Persona config (+ optional story overrides) drives n_orders, product
      category affinity, discount distribution, channel, and payment method.
    - Order dates are sampled with seasonality and story-type-aware date
      distributions.
    - Quantity sampling uses category-informed weights: premium products
      skew toward qty=1; family essentials allow higher quantities.
    - Dormant reactivation orders (last 25% of the customer's date window)
      receive elevated discount probabilities.
    - final_price is computed as:
        unit_price × quantity × (1 − discount_pct / 100)

    Parameters
    ----------
    customer : pd.Series
        A single row from customers.csv.
    is_story : bool
        Whether this customer is a story customer.
    story_type : str | None
        Story type label (None for non-story customers).
    story_customer_id : str | None
        story_customer_id from story_customers.csv (None for non-story).
    product_lookup : dict[str, pd.DataFrame]
        Pre-built category → products mapping.
    available_categories : set[str]
        Set of categories present in the product catalogue.
    rng : random.Random
        Seeded RNG (shared across all customers for full determinism).
    order_id_counter : list[int]
        Single-element list used as a mutable counter; incremented in-place
        so callers share state without a global variable.

    Returns
    -------
    list[dict]
        List of order row dicts. Empty list if no valid dates exist.
    """
    persona    = customer["persona"]
    join_date  = customer["join_date"]
    customer_id = customer["customer_id"]

    # Resolve effective behavioural config
    config = get_persona_config(persona, is_story, story_type)

    # Determine number of lifetime orders for this customer
    lo, hi   = config["orders_range"]
    n_orders = rng.randint(lo, hi)

    # Generate order dates respecting join_date and seasonality
    order_dates = generate_order_dates(n_orders, join_date, story_type, rng)
    if not order_dates:
        return []

    # Pre-compute the "late window" threshold for dormant reactivation uplift
    # (applies when persona == Dormant Customers or story_type matches)
    is_dormant = (persona == "Dormant Customers") or \
                 (story_type == "Dormant Returning Customers")
    if is_dormant and order_dates:
        late_threshold = order_dates[int(len(order_dates) * 0.75)] \
                         if len(order_dates) > 4 else order_dates[-1]
    else:
        late_threshold = None

    rows = []
    for order_date in order_dates:

        # ── Product selection ────────────────────────────────────────────────
        product = sample_product(
            config["category_weights"],
            product_lookup,
            available_categories,
            rng,
        )
        if product is None:
            continue   # Skip if catalogue filtering leaves nothing valid

        product_id = product["product_id"]
        unit_price = float(product["price"])
        category   = product["category"]

        # ── Quantity ─────────────────────────────────────────────────────────
        # Premium products (Self-Care, Wellness) skew qty=1
        # Family/Baby essentials allow higher quantities
        if category in ("Self-Care", "Wellness"):
            qty_weights = [0.65, 0.25, 0.08, 0.02]
        elif category in ("Family Essentials", "Baby Care"):
            qty_weights = config["qty_weights"]   # persona-driven
        else:
            qty_weights = config["qty_weights"]

        quantity = weighted_choice([1, 2, 3, 4], qty_weights, rng)

        # ── Discount ─────────────────────────────────────────────────────────
        disc_cfg = config["discount_weights"]

        # Dormant reactivation uplift: orders in the late window receive
        # a heavier discount to simulate re-engagement promotions.
        if is_dormant and late_threshold and order_date >= late_threshold:
            disc_cfg = {0: 5, 5: 10, 10: 20, 15: 25, 20: 20, 25: 12, 30: 8}

        disc_keys    = list(disc_cfg.keys())
        disc_weights = list(disc_cfg.values())
        discount_pct = weighted_choice(disc_keys, disc_weights, rng)

        # ── Pricing ──────────────────────────────────────────────────────────
        final_price = round(
            unit_price * quantity * (1 - discount_pct / 100),
            2,
        )

        # ── Channel ──────────────────────────────────────────────────────────
        ch_keys    = list(config["channel_weights"].keys())
        ch_weights = list(config["channel_weights"].values())
        channel    = weighted_choice(ch_keys, ch_weights, rng)

        # ── Payment method ───────────────────────────────────────────────────
        pm_keys    = list(config["payment_weights"].keys())
        pm_weights = list(config["payment_weights"].values())
        payment_method = weighted_choice(pm_keys, pm_weights, rng)

        # ── Order ID (sequential, zero-padded to 6 digits) ───────────────────
        order_id = f"ORD{order_id_counter[0]:06d}"
        order_id_counter[0] += 1

        # ── Story customer flag ───────────────────────────────────────────────
        rows.append({
            "order_id":         order_id,
            "customer_id":      customer_id,
            "order_date":       order_date,
            "product_id":       product_id,
            "quantity":         quantity,
            "unit_price":       unit_price,
            "discount_pct":     discount_pct,
            "final_price":      final_price,
            "channel":          channel,
            "payment_method":   payment_method,
            "is_story_customer": 1 if is_story else 0,
            "story_customer_id": story_customer_id if is_story else None,
        })

    return rows


# ==============================================================================
# MAIN GENERATOR
# ==============================================================================

def generate_orders(
    customers: pd.DataFrame,
    products: pd.DataFrame,
    story_customers: pd.DataFrame,
) -> pd.DataFrame:
    """
    Orchestrate order generation across all customers and return the
    complete orders DataFrame.

    Steps
    -----
    1. Seed the RNG for full determinism.
    2. Build product lookup table (category → sub-DataFrame).
    3. Build a set of story customer_ids for O(1) membership checks.
    4. Iterate customers in a deterministic order (sorted by customer_id).
    5. For each customer, resolve persona config, generate dates, products,
       quantities, discounts, channels, and payment methods.
    6. Concatenate all row dicts into a single DataFrame.
    7. Sort by order_date then order_id for natural ordering.

    Parameters
    ----------
    customers : pd.DataFrame
    products : pd.DataFrame
    story_customers : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        Complete orders dataset with schema matching OUTPUT spec.
    """
    print("=" * 70)
    print("GENERATING ORDERS")
    print("=" * 70)

    # Seed the global Python random instance and local RNG
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    rng = random.Random(RANDOM_SEED)

    # Build product lookup
    product_lookup       = build_product_lookup(products)
    available_categories = set(product_lookup.keys())
    print(f"  Product categories available: {sorted(available_categories)}")
    print(f"  Total products in catalogue : {len(products):,}")

    # Build story customer lookup: customer_id → row
    story_lookup: dict[str, pd.Series] = {
        row["customer_id"]: row
        for _, row in story_customers.iterrows()
    }
    print(f"  Story customers             : {len(story_lookup):,}")
    print()

    # Sort customers for determinism (avoid pandas default ordering)
    customers_sorted = customers.sort_values("customer_id").reset_index(drop=True)

    # Mutable counter shared across all customer loops
    order_id_counter = [1]

    all_rows: list[dict] = []

    for i, customer in customers_sorted.iterrows():
        customer_id = customer["customer_id"]
        is_story    = customer_id in story_lookup

        if is_story:
            story_row         = story_lookup[customer_id]
            story_type        = story_row.get("story_type", None)
            story_customer_id = story_row.get("story_customer_id", None)   # fallback if column absent
            
        else:
            story_type        = None
            story_customer_id = None

        customer_orders = generate_customer_orders(
            customer          = customer,
            is_story          = is_story,
            story_type        = story_type,
            story_customer_id = story_customer_id,
            product_lookup    = product_lookup,
            available_categories = available_categories,
            rng               = rng,
            order_id_counter  = order_id_counter,
        )
        all_rows.extend(customer_orders)

        # Lightweight progress indicator every 500 customers
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1:,} / {len(customers_sorted):,} customers "
                  f"| orders so far: {len(all_rows):,}")

    print(f"\n  Total orders generated: {len(all_rows):,}")
    print()

    # Assemble DataFrame
    orders = pd.DataFrame(all_rows)

    # Normalise order_date to pandas datetime (export as date string)
    orders["order_date"] = pd.to_datetime(orders["order_date"])

    # Sort for natural ordering: primary by date, secondary by ID
    orders = orders.sort_values(
        ["order_date", "order_id"],
        ascending=[True, True],
    ).reset_index(drop=True)

    # Enforce schema column order
    orders = orders[[
        "order_id", "customer_id", "order_date", "product_id",
        "quantity", "unit_price", "discount_pct", "final_price",
        "channel", "payment_method", "is_story_customer", "story_customer_id",
    ]]

    return orders


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    story_customers: pd.DataFrame,
) -> None:
    """
    Run a comprehensive suite of data-quality assertions over the generated
    orders DataFrame.  Any failure raises AssertionError immediately, printing
    the failing check name so the engineer can diagnose issues quickly.

    Checks performed
    ----------------
    1.  Dataset is non-empty.
    2.  order_id values are globally unique.
    3.  All customer_ids appear in customers.csv.
    4.  All product_ids appear in products.csv.
    5.  order_date >= customer join_date for every row.
    6.  quantity is between 1 and 4 (inclusive).
    7.  discount_pct values are all from ALLOWED_DISCOUNTS.
    8.  final_price is strictly positive for all rows.
    9.  final_price matches the formula:
          unit_price × quantity × (1 − discount_pct/100), rounded to 2dp.
    10. payment_method values are all from ALLOWED_PAYMENT_METHODS.
    11. channel values are all from ALLOWED_CHANNELS.
    12. is_story_customer is 0 or 1 only.
    13. Rows flagged is_story_customer == 1 have a non-null story_customer_id.
    14. story_customer_id references are consistent with story_customers.csv.
    15. Order dates fall within the global ORDER_START_DATE–ORDER_END_DATE window.

    Parameters
    ----------
    orders : pd.DataFrame
    customers : pd.DataFrame
    products : pd.DataFrame
    story_customers : pd.DataFrame

    Raises
    ------
    AssertionError
        On the first failing check, with a descriptive message.
    """
    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)

    valid_customer_ids     = set(customers["customer_id"].unique())
    valid_product_ids      = set(products["product_id"].unique())
    story_customer_id_set  = set(story_customers["customer_id"].unique())

    # Build join_date lookup: customer_id → date
    join_date_map = {
        row["customer_id"]: pd.to_datetime(row["join_date"])
        for _, row in customers.iterrows()
    }

    checks = []

    # 1. Non-empty
    result = len(orders) > 0
    checks.append(("Non-empty dataset", result,
                   f"Expected > 0 rows; got {len(orders)}"))

    # 2. Unique order_id
    result = orders["order_id"].nunique() == len(orders)
    checks.append(("Unique order_id", result,
                   f"Duplicate order_ids found: "
                   f"{len(orders) - orders['order_id'].nunique()}"))

    # 3. Valid customer_ids
    invalid_cids = set(orders["customer_id"].unique()) - valid_customer_ids
    checks.append(("Valid customer_ids", len(invalid_cids) == 0,
                   f"Unknown customer_ids: {invalid_cids}"))

    # 4. Valid product_ids
    invalid_pids = set(orders["product_id"].unique()) - valid_product_ids
    checks.append(("Valid product_ids", len(invalid_pids) == 0,
                   f"Unknown product_ids: {invalid_pids}"))

    # 5. order_date >= join_date
    orders_dates = orders.copy()
    orders_dates["join_date"] = orders_dates["customer_id"].map(join_date_map)
    bad_dates = orders_dates[
        orders_dates["order_date"] < orders_dates["join_date"]
    ]
    checks.append(("order_date >= join_date", len(bad_dates) == 0,
                   f"{len(bad_dates)} orders predate customer join_date"))

    # 6. Quantity in [1, 4]
    bad_qty = orders[~orders["quantity"].between(QTY_MIN, QTY_MAX)]
    checks.append(("Quantity 1–4", len(bad_qty) == 0,
                   f"{len(bad_qty)} rows with quantity outside [1,4]"))

    # 7. Allowed discount values
    bad_disc = orders[~orders["discount_pct"].isin(ALLOWED_DISCOUNTS)]
    checks.append(("discount_pct allowed values", len(bad_disc) == 0,
                   f"{len(bad_disc)} rows with invalid discount_pct"))

    # 8. final_price > 0
    bad_price = orders[orders["final_price"] <= 0]
    checks.append(("final_price > 0", len(bad_price) == 0,
                   f"{len(bad_price)} rows with non-positive final_price"))

    # 9. Pricing formula consistency
    expected_final = (
        orders["unit_price"] * orders["quantity"]
        * (1 - orders["discount_pct"] / 100)
    ).round(2)
    price_mismatch = (orders["final_price"] - expected_final).abs() > 0.01
    checks.append(("Pricing formula correct", price_mismatch.sum() == 0,
                   f"{price_mismatch.sum()} rows fail pricing formula check"))

    # 10. Valid payment methods
    bad_pm = orders[~orders["payment_method"].isin(ALLOWED_PAYMENT_METHODS)]
    checks.append(("Valid payment_method", len(bad_pm) == 0,
                   f"{len(bad_pm)} rows with invalid payment_method"))

    # 11. Valid channels
    bad_ch = orders[~orders["channel"].isin(ALLOWED_CHANNELS)]
    checks.append(("Valid channel", len(bad_ch) == 0,
                   f"{len(bad_ch)} rows with invalid channel"))

    # 12. is_story_customer is binary (0 or 1)
    bad_flag = orders[~orders["is_story_customer"].isin([0, 1])]
    checks.append(("is_story_customer binary", len(bad_flag) == 0,
                   f"{len(bad_flag)} rows with non-binary is_story_customer"))

    # 13. Story-flagged rows have non-null story_customer_id
    story_rows = orders[orders["is_story_customer"] == 1]
    null_sid   = story_rows["story_customer_id"].isna().sum()
    checks.append(("Story rows have story_customer_id", null_sid == 0,
                   f"{null_sid} story-flagged rows missing story_customer_id"))

    # 14. Non-story rows have null story_customer_id
    non_story_rows = orders[orders["is_story_customer"] == 0]
    non_null_sid   = non_story_rows["story_customer_id"].notna().sum()
    checks.append(("Non-story rows have null story_customer_id",
                   non_null_sid == 0,
                   f"{non_null_sid} non-story rows have unexpected story_customer_id"))

    # 15. Dates within global window
    min_date = pd.Timestamp(ORDER_START_DATE)
    max_date = pd.Timestamp(ORDER_END_DATE)
    out_of_window = orders[
        (orders["order_date"] < min_date) | (orders["order_date"] > max_date)
    ]
    checks.append(("Order dates in window", len(out_of_window) == 0,
                   f"{len(out_of_window)} orders outside global date window"))

    # ── Report and assert ────────────────────────────────────────────────────
    all_passed = True
    for check_name, passed, message in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check_name}")
        if not passed:
            all_passed = False
            print(f"         ↳ {message}")

    print()
    if all_passed:
        print("  ✓ All validation checks passed.\n")
    else:
        raise AssertionError(
            "Validation failed — see FAIL entries above for details."
        )


# ==============================================================================
# SUMMARY REPORT
# ==============================================================================

def print_summary(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
) -> None:
    """
    Print a structured summary report to stdout covering key metrics for
    the generated order dataset.  This serves as a quick sanity-check
    during development and a demonstration-ready output for interviews.

    Metrics reported
    ----------------
    - Total orders
    - Orders by persona
    - Revenue by persona
    - Story vs non-story customer breakdown
    - Revenue by channel
    - Average order value
    - Average discount percentage
    - Earliest and latest order dates

    Parameters
    ----------
    orders : pd.DataFrame
        Generated orders DataFrame.
    customers : pd.DataFrame
        Customer master (for persona join).
    """
    print("=" * 70)
    print("SUMMARY REPORT")
    print("=" * 70)

    # Join persona onto orders for segmented reporting
    orders_with_persona = orders.merge(
        customers[["customer_id", "persona"]],
        on="customer_id",
        how="left",
    )

    total_orders  = len(orders)
    total_revenue = orders["final_price"].sum()
    avg_order_val = orders["final_price"].mean()
    avg_discount  = orders["discount_pct"].mean()
    min_date      = orders["order_date"].min()
    max_date      = orders["order_date"].max()

    print(f"\n  Total Orders        : {total_orders:,}")
    print(f"  Total Revenue       : ₹{total_revenue:,.2f}")
    print(f"  Average Order Value : ₹{avg_order_val:,.2f}")
    print(f"  Average Discount    : {avg_discount:.2f}%")
    print(f"  Earliest Order Date : {min_date.date()}")
    print(f"  Latest Order Date   : {max_date.date()}")

    # ── Orders and revenue by persona ────────────────────────────────────────
    print("\n  ─── Orders & Revenue by Persona ───────────────────────────────")
    persona_stats = (
        orders_with_persona
        .groupby("persona", observed=True)
        .agg(
            order_count  = ("order_id",    "count"),
            total_rev    = ("final_price", "sum"),
            avg_val      = ("final_price", "mean"),
        )
        .sort_values("order_count", ascending=False)
    )
    for persona, row in persona_stats.iterrows():
        print(f"  {persona:<25}  "
              f"Orders: {int(row['order_count']):>6,}  |  "
              f"Revenue: ₹{row['total_rev']:>12,.2f}  |  "
              f"AOV: ₹{row['avg_val']:>7,.2f}")

    # ── Story vs non-story ────────────────────────────────────────────────────
    print("\n  ─── Story vs Non-Story Customers ───────────────────────────────")
    story_stats = (
        orders
        .groupby("is_story_customer")
        .agg(
            order_count = ("order_id",    "count"),
            revenue     = ("final_price", "sum"),
        )
    )
    for flag, row in story_stats.iterrows():
        label = "Story customers    " if flag == 1 else "Non-story customers"
        print(f"  {label}  Orders: {int(row['order_count']):>6,}  |  "
              f"Revenue: ₹{row['revenue']:>12,.2f}")

    # ── Revenue by channel ────────────────────────────────────────────────────
    print("\n  ─── Revenue by Channel ─────────────────────────────────────────")
    channel_stats = (
        orders
        .groupby("channel")
        .agg(
            order_count = ("order_id",    "count"),
            revenue     = ("final_price", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )
    for channel, row in channel_stats.iterrows():
        print(f"  {channel:<12}  Orders: {int(row['order_count']):>6,}  |  "
              f"Revenue: ₹{row['revenue']:>12,.2f}")

    print()


# ==============================================================================
# EXPORT
# ==============================================================================

def export_orders(orders: pd.DataFrame) -> None:
    """
    Export the generated orders to data/orders.csv.

    Normalisation applied before export
    ------------------------------------
    - order_date is formatted as YYYY-MM-DD string to ensure consistent
      date representation regardless of pandas version.
    - The output directory is created if it does not already exist.

    Parameters
    ----------
    orders : pd.DataFrame
        The fully validated orders DataFrame.
    """
    print("=" * 70)
    print("EXPORTING")
    print("=" * 70)

    output_dir = os.path.dirname(OUTPUT_ORDERS_PATH)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Normalise order_date to plain date string (no time component)
    export_df = orders.copy()
    export_df["order_date"] = export_df["order_date"].dt.strftime("%Y-%m-%d")

    export_df.to_csv(OUTPUT_ORDERS_PATH, index=False)

    file_size_kb = os.path.getsize(OUTPUT_ORDERS_PATH) / 1024
    print(f"  Exported {len(export_df):,} rows to: {OUTPUT_ORDERS_PATH}")
    print(f"  File size: {file_size_kb:,.1f} KB")
    print()


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main() -> None:
    """
    Main pipeline entry point for generate_orders.py.

    Execution order
    ---------------
    1.  Load input files (customers, products, story_customers).
    2.  Generate all orders using persona- and story-driven behaviour rules.
    3.  Validate the output against the full assertion suite.
    4.  Print summary metrics report.
    5.  Export to data/orders.csv.
    """
    print()
    print("=" * 70)
    print("  AETHER CRM — ORDER DATA GENERATOR")
    print(f"  RANDOM_SEED = {RANDOM_SEED}")
    print(f"  Date window : {ORDER_START_DATE} → {ORDER_END_DATE}")
    print("=" * 70)
    print()

    # ── Step 1: Load inputs ──────────────────────────────────────────────────
    customers, products, story_customers = load_inputs()

    # ── Step 2: Generate orders ──────────────────────────────────────────────
    orders = generate_orders(customers, products, story_customers)

    # ── Step 3: Validate ─────────────────────────────────────────────────────
    validate(orders, customers, products, story_customers)

    # ── Step 4: Summary report ───────────────────────────────────────────────
    print_summary(orders, customers)

    # ── Step 5: Export ───────────────────────────────────────────────────────
    export_orders(orders)

    print("=" * 70)
    print("  GENERATION COMPLETE")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()