"""
generate_customer_features.py
================================================================================
Aether CRM — Customer Feature Engineering Pipeline
================================================================================

Purpose
-------
Transforms raw transactional CRM data (customers, orders, products, story
customers) into a flat, machine-learning-ready feature table with exactly one
row per customer.

The pipeline is:
    Load inputs
    → Generate customer features
    → Validate
    → Print summary
    → Export

Design principles
-----------------
- Deterministic: seeded with RANDOM_SEED = 42; no randomness in the pipeline.
- Complete coverage: every customer in customers.csv appears in the output,
  even customers with zero orders (sensible defaults are applied).
- Production quality: typed, documented, testable, no TODO comments.
- Pandas-only: no heavy ML dependencies required to run this script.

Usage
-----
    python generate_customer_features.py

Output
------
    data/customer_features.csv  — one row per customer, no date columns.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import os
import sys
import warnings
from typing import List

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# ==============================================================================
# CONSTANTS
# ==============================================================================

RANDOM_SEED: int = 42
np.random.seed(RANDOM_SEED)

# Input paths
INPUT_CUSTOMERS_PATH: str = "data_generation/data/customers.csv"
INPUT_ORDERS_PATH: str = "data_generation/data/orders.csv"
INPUT_STORY_CUSTOMERS_PATH: str = "data_generation/data/story_customers.csv"
INPUT_PRODUCTS_PATH: str = "data_generation/data/products.csv"

# Output path
OUTPUT_FEATURES_PATH: str = "data_generation/data/customer_features.csv"

# Sentinel values for customers with no orders
DEFAULT_NUMERIC: float = 0.0
DEFAULT_CATEGORICAL: str = "UNKNOWN"

# Product categories tracked as individual order-count features.
# Must match the values in products.csv exactly (case-sensitive).
TRACKED_CATEGORIES: List[str] = [
    "Baby Care",
    "Family Essentials",
    "Wellness",
    "Self Care",
    "Nutrition",          # included per spec; will be 0 if absent in data
]

# Column name mapping: category → feature column name
CATEGORY_COL_MAP: dict = {
    "Baby Care":          "baby_care_orders",
    "Family Essentials":  "family_essentials_orders",
    "Wellness":           "wellness_orders",
    "Self Care":          "self_care_orders",
    "Nutrition":          "nutrition_orders",
}

# Channel columns expected in the output
CHANNEL_COLS: List[str] = [
    "website_orders_pct",
    "app_orders_pct",
    "whatsapp_orders_pct",
]

# Ordered list of all output columns (defines final column order in the CSV)
OUTPUT_COLUMNS: List[str] = [
    # Identity
    "customer_id",
    "persona",
    "is_story_customer",
    "story_customer_id",
    # RFM
    "recency_days",
    "frequency",
    "monetary",
    # Order behaviour
    "avg_order_value",
    "max_order_value",
    "min_order_value",
    "total_quantity",
    # Discount behaviour
    "avg_discount_pct",
    "discount_usage_rate",
    # Channel behaviour
    "website_orders_pct",
    "app_orders_pct",
    "whatsapp_orders_pct",
    # Payment behaviour
    "preferred_payment_method",
    # Purchase behaviour — per-category counts
    "baby_care_orders",
    "family_essentials_orders",
    "wellness_orders",
    "self_care_orders",
    "nutrition_orders",
    # Purchase behaviour — favourite category
    "favorite_category",
    # Lifecycle
    "customer_tenure_days",
    "days_since_last_order",
    "avg_days_between_orders",
    "orders_per_month",
    # Story features
    "story_type",
    "journey_stage",
    "engagement_level",
]

# ==============================================================================
# DATA LOADING
# ==============================================================================


def load_customers(path: str) -> pd.DataFrame:
    """
    Load and lightly validate the customers table.

    Expected columns (subset used downstream):
        customer_id, persona, join_date, is_story_customer, story_customer_id

    Parameters
    ----------
    path : str
        File-system path to customers.csv.

    Returns
    -------
    pd.DataFrame
        Customers table with join_date parsed as datetime.
    """
    df = pd.read_csv(path)
    required = {"customer_id", "persona", "join_date",
                 "is_story_customer", "story_customer_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"customers.csv is missing columns: {missing}")

    df["join_date"] = pd.to_datetime(df["join_date"])
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    return df


def load_orders(path: str) -> pd.DataFrame:
    """
    Load and lightly validate the orders table.

    Expected columns:
        order_id, customer_id, order_date, product_id, quantity,
        unit_price, discount_pct, final_price, channel,
        payment_method, is_story_customer, story_customer_id

    Parameters
    ----------
    path : str
        File-system path to orders.csv.

    Returns
    -------
    pd.DataFrame
        Orders table with order_date parsed as datetime.
    """
    df = pd.read_csv(path)
    required = {
        "order_id", "customer_id", "order_date", "product_id",
        "quantity", "unit_price", "discount_pct", "final_price",
        "channel", "payment_method",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"orders.csv is missing columns: {missing}")

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    df["channel"] = df["channel"].astype(str).str.upper().str.strip()
    return df


def load_story_customers(path: str) -> pd.DataFrame:
    """
    Load and lightly validate the story_customers table.

    Expected columns (subset used downstream):
        customer_id, story_customer_id, story_type,
        journey_stage, engagement_level

    Parameters
    ----------
    path : str
        File-system path to story_customers.csv.

    Returns
    -------
    pd.DataFrame
        Story-customers table.
    """
    df = pd.read_csv(path)
    required = {
        "customer_id", "story_customer_id",
        "story_type", "journey_stage", "engagement_level",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"story_customers.csv is missing columns: {missing}")

    df["customer_id"] = df["customer_id"].astype(str).str.strip()
    return df


def load_products(path: str) -> pd.DataFrame:
    """
    Load and lightly validate the products table.

    Expected columns (subset used downstream):
        product_id, category

    Parameters
    ----------
    path : str
        File-system path to products.csv.

    Returns
    -------
    pd.DataFrame
        Products table.
    """
    df = pd.read_csv(path)
    required = {"product_id", "category"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"products.csv is missing columns: {missing}")

    df["product_id"] = df["product_id"].astype(str).str.strip()
    return df


# ==============================================================================
# FEATURE COMPUTATION HELPERS
# ==============================================================================


def compute_rfm_features(
    orders: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Compute Recency, Frequency, and Monetary (RFM) features per customer.

    Definitions
    -----------
    recency_days : int
        Number of days between reference_date and the customer's most recent
        order date.  A lower value means a more recent customer.
    frequency : int
        Total number of orders placed by the customer.
    monetary : float
        Total spend (sum of final_price across all orders).

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table (must contain customer_id, order_date, final_price).
    reference_date : pd.Timestamp
        The virtual "today" used for recency calculation.
        Defined as max(order_date) + 1 day.

    Returns
    -------
    pd.DataFrame
        One row per customer with columns:
        customer_id, recency_days, frequency, monetary.
    """
    rfm = (
        orders.groupby("customer_id", as_index=False)
        .agg(
            latest_order_date=("order_date", "max"),
            frequency=("order_id", "count"),
            monetary=("final_price", "sum"),
        )
    )
    rfm["recency_days"] = (
        reference_date - rfm["latest_order_date"]
    ).dt.days.astype(int)

    return rfm[["customer_id", "recency_days", "frequency", "monetary"]]


def compute_order_behaviour_features(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Compute order-level behavioural aggregates per customer.

    Definitions
    -----------
    avg_order_value : float
        Mean final_price across all orders for the customer.
    max_order_value : float
        Maximum final_price across all orders for the customer.
    min_order_value : float
        Minimum final_price across all orders for the customer.
    total_quantity : int
        Sum of quantity across all orders for the customer.

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table.

    Returns
    -------
    pd.DataFrame
        One row per customer.
    """
    agg = (
        orders.groupby("customer_id", as_index=False)
        .agg(
            avg_order_value=("final_price", "mean"),
            max_order_value=("final_price", "max"),
            min_order_value=("final_price", "min"),
            total_quantity=("quantity", "sum"),
        )
    )
    return agg


def compute_discount_features(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Compute discount-usage features per customer.

    Definitions
    -----------
    avg_discount_pct : float
        Mean discount_pct across all orders for the customer.
    discount_usage_rate : float
        Fraction of orders where discount_pct > 0.
        Range [0, 1].

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table.

    Returns
    -------
    pd.DataFrame
        One row per customer.
    """
    orders = orders.copy()
    orders["_discounted"] = (orders["discount_pct"] > 0).astype(int)

    agg = (
        orders.groupby("customer_id", as_index=False)
        .agg(
            avg_discount_pct=("discount_pct", "mean"),
            _total_orders=("order_id", "count"),
            _discounted_orders=("_discounted", "sum"),
        )
    )
    agg["discount_usage_rate"] = (
        agg["_discounted_orders"] / agg["_total_orders"]
    )
    return agg[["customer_id", "avg_discount_pct", "discount_usage_rate"]]


def compute_channel_features(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Compute channel-proportion features per customer.

    Each proportion is defined as:
        (orders placed through that channel) / (total orders)

    Channels handled:
        WEBSITE → website_orders_pct
        APP     → app_orders_pct
        WHATSAPP → whatsapp_orders_pct

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table.  channel column must be upper-cased.

    Returns
    -------
    pd.DataFrame
        One row per customer with columns:
        customer_id, website_orders_pct, app_orders_pct, whatsapp_orders_pct.
    """
    # Pivot: count orders per channel per customer
    orders = orders.copy()
    channel_counts = (
        orders.groupby(["customer_id", "channel"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all three channel columns exist even if no orders used them
    for col in ("WEBSITE", "APP", "WHATSAPP"):
        if col not in channel_counts.columns:
            channel_counts[col] = 0

    channel_counts["_total"] = (
        channel_counts["WEBSITE"]
        + channel_counts["APP"]
        + channel_counts["WHATSAPP"]
    )

    channel_counts["website_orders_pct"] = (
        channel_counts["WEBSITE"] / channel_counts["_total"]
    )
    channel_counts["app_orders_pct"] = (
        channel_counts["APP"] / channel_counts["_total"]
    )
    channel_counts["whatsapp_orders_pct"] = (
        channel_counts["WHATSAPP"] / channel_counts["_total"]
    )

    return channel_counts[[
        "customer_id",
        "website_orders_pct",
        "app_orders_pct",
        "whatsapp_orders_pct",
    ]]


def compute_payment_features(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the preferred payment method per customer.

    Definition
    ----------
    preferred_payment_method : str
        The payment method used most frequently across all orders.
        Ties are broken alphabetically (the alphabetically first method wins).
        Customers with no orders receive the sentinel value UNKNOWN.

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table.

    Returns
    -------
    pd.DataFrame
        One row per customer with columns:
        customer_id, preferred_payment_method.
    """
    # Sort alphabetically first so ties break in favour of the first
    # alphabetical method when idxmax is called later.
    orders_sorted = orders.sort_values("payment_method")

    payment_counts = (
        orders_sorted.groupby(["customer_id", "payment_method"])
        .size()
        .reset_index(name="count")
    )

    # For each customer, pick the payment method with the maximum count.
    # Because the data is already sorted alphabetically, ties resolve to
    # the alphabetically first method.
    preferred = (
        payment_counts.loc[
            payment_counts.groupby("customer_id")["count"].idxmax()
        ]
        [["customer_id", "payment_method"]]
        .rename(columns={"payment_method": "preferred_payment_method"})
    )

    return preferred


def compute_category_features(
    orders: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute per-category order counts and favourite category per customer.

    Steps
    -----
    1. Join orders with products on product_id to obtain category labels.
    2. Count orders per category per customer (a single order counts once per
       category even if the same order contains multiple product rows — but in
       this dataset each order row is already one product line).
    3. Identify the favourite category as the category with the highest count.
       Ties are broken alphabetically.

    Category columns generated
    --------------------------
    baby_care_orders, family_essentials_orders, wellness_orders,
    self_care_orders, nutrition_orders, favorite_category.

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table (must contain customer_id, product_id).
    products : pd.DataFrame
        Products table (must contain product_id, category).

    Returns
    -------
    pd.DataFrame
        One row per customer.
    """
    # Join to bring in category
    enriched = orders.merge(
        products[["product_id", "category"]],
        on="product_id",
        how="left",
    )

    # Fill any products not found in the catalogue
    enriched["category"] = enriched["category"].fillna("Unknown")

    # Pivot: count orders per customer per category
    cat_counts = (
        enriched.groupby(["customer_id", "category"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all tracked category columns exist
    for cat in TRACKED_CATEGORIES:
        if cat not in cat_counts.columns:
            cat_counts[cat] = 0

    # Rename to feature names
    rename_map = {
        cat: col for cat, col in CATEGORY_COL_MAP.items()
        if cat in cat_counts.columns
    }
    cat_counts = cat_counts.rename(columns=rename_map)

    # Derive favourite_category from the tracked categories only.
    # Sort columns alphabetically so ties resolve to the first alphabetically.
    tracked_feature_cols = sorted(
    CATEGORY_COL_MAP.values(),
    key=lambda col: {
        v: k for k, v in CATEGORY_COL_MAP.items()
    }[col]
)

    available_tracked = [
        c for c in tracked_feature_cols
        if c in cat_counts.columns
    ]

    # Map back from feature-col names to original category names for labelling
    col_to_cat = {v: k for k, v in CATEGORY_COL_MAP.items()}

    def _favorite_category(row: pd.Series) -> str:
        """Return the category name with the highest order count."""
        max_val = row[available_tracked].max()
        if max_val == 0:
            return DEFAULT_CATEGORICAL
        # Among columns with max value, idxmin gives alphabetically first
        # because available_tracked is already sorted alphabetically.
        best_col = row[available_tracked][
            row[available_tracked] == max_val
        ].index[0]
        return col_to_cat.get(best_col, DEFAULT_CATEGORICAL)

    cat_counts["favorite_category"] = cat_counts.apply(
        _favorite_category, axis=1
    )

    # Keep only the feature columns we need
    feature_cols = (
        ["customer_id"]
        + [CATEGORY_COL_MAP[c] for c in TRACKED_CATEGORIES if CATEGORY_COL_MAP[c] in cat_counts.columns]
        + ["favorite_category"]
    )
    return cat_counts[feature_cols]


def compute_lifecycle_features(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Compute lifecycle / temporal features per customer.

    Definitions
    -----------
    customer_tenure_days : int
        Number of days between reference_date and the customer's join_date.
    days_since_last_order : int
        Number of days between reference_date and the customer's most recent
        order date.  For customers with no orders: 0.
    avg_days_between_orders : float
        Average number of days between consecutive orders, computed as the
        mean of the sorted order-date differences within each customer.
        For customers with fewer than two orders: 0.

    Parameters
    ----------
    orders : pd.DataFrame
        Orders table (must contain customer_id, order_date).
    customers : pd.DataFrame
        Customers table (must contain customer_id, join_date already parsed).
    reference_date : pd.Timestamp
        Virtual "today".

    Returns
    -------
    pd.DataFrame
        One row per customer with columns:
        customer_id, customer_tenure_days,
        days_since_last_order, avg_days_between_orders.
    """
    # --- customer_tenure_days -------------------------------------------
    tenure = customers[["customer_id", "join_date"]].copy()
    tenure["customer_tenure_days"] = (
        reference_date - tenure["join_date"]
    ).dt.days.astype(int)

    # --- days_since_last_order ------------------------------------------
    last_order = (
        orders.groupby("customer_id", as_index=False)["order_date"]
        .max()
        .rename(columns={"order_date": "_last_order_date"})
    )
    last_order["days_since_last_order"] = (
        reference_date - last_order["_last_order_date"]
    ).dt.days.astype(int)

    # --- avg_days_between_orders ----------------------------------------
    def _avg_gap(dates: pd.Series) -> float:
        """
        Compute the mean gap in days between consecutive sorted order dates.
        Returns 0.0 if fewer than two orders are present.
        """
        if len(dates) < 2:
            return 0.0
        sorted_dates = dates.sort_values().reset_index(drop=True)
        gaps = sorted_dates.diff().dropna().dt.days
        return float(gaps.mean())

    avg_gap = (
        orders.groupby("customer_id")["order_date"]
        .apply(_avg_gap)
        .reset_index(name="avg_days_between_orders")
    )

    # --- Assemble --------------------------------------------------------
    lifecycle = (
        tenure[["customer_id", "customer_tenure_days"]]
        .merge(last_order[["customer_id", "days_since_last_order"]], on="customer_id", how="left")
        .merge(avg_gap, on="customer_id", how="left")
    )

    # Fill 0 for customers with no orders
    lifecycle["days_since_last_order"] = (
        lifecycle["days_since_last_order"].fillna(DEFAULT_NUMERIC).astype(int)
    )
    lifecycle["avg_days_between_orders"] = (
        lifecycle["avg_days_between_orders"].fillna(DEFAULT_NUMERIC)
    )

    return lifecycle[[
        "customer_id",
        "customer_tenure_days",
        "days_since_last_order",
        "avg_days_between_orders",
    ]]


def compute_story_features(story_customers: pd.DataFrame) -> pd.DataFrame:
    """
    Extract story-related features for story customers.

    Non-story customers (i.e. those not present in story_customers.csv) will
    receive the sentinel value UNKNOWN for all three feature columns.

    Feature columns
    ---------------
    story_type      : str   The narrative archetype of the customer's journey.
    journey_stage   : str   Current stage in the customer lifecycle story.
    engagement_level : str  Self-reported or inferred engagement category.

    Parameters
    ----------
    story_customers : pd.DataFrame
        Story-customers table.

    Returns
    -------
    pd.DataFrame
        One row per story customer with columns:
        customer_id, story_type, journey_stage, engagement_level.
    """
    return story_customers[[
        "customer_id",
        "story_type",
        "journey_stage",
        "engagement_level",
    ]].copy()


# ==============================================================================
# MAIN FEATURE GENERATION
# ==============================================================================


def generate_customer_features(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    story_customers: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    """
    Orchestrate the full feature engineering pipeline.

    This function is the single entry point for feature generation.  It:
    1. Computes the reference date from the orders table.
    2. Delegates each feature group to a dedicated helper function.
    3. Left-joins all feature groups onto the customers spine so that every
       customer, including those with zero orders, appears in the output.
    4. Fills default values (0 / UNKNOWN) for customers with no orders.
    5. Reorders columns to the canonical OUTPUT_COLUMNS order.

    Parameters
    ----------
    customers : pd.DataFrame
        Customers table (one row per customer).
    orders : pd.DataFrame
        Orders table (zero or more rows per customer).
    story_customers : pd.DataFrame
        Story customers enrichment table.
    products : pd.DataFrame
        Products reference table.

    Returns
    -------
    pd.DataFrame
        Feature table with exactly one row per customer and columns
        matching OUTPUT_COLUMNS.
    """
    print("[Pipeline] Computing reference date ...")
    if orders.empty:
        reference_date = pd.Timestamp.today().normalize()
    else:
        reference_date = (
        orders["order_date"].max()
        + pd.Timedelta(days=1)
    )
    print(f"[Pipeline] Reference date = {reference_date.date()}")

    # ------------------------------------------------------------------
    # Build the customer spine — one row per customer
    # ------------------------------------------------------------------
    print("[Pipeline] Building customer identity spine ...")
    spine = customers[[
        "customer_id", "persona", "is_story_customer", "story_customer_id"
    ]].copy()
    spine["is_story_customer"] = spine["is_story_customer"].astype(bool)

    # ------------------------------------------------------------------
    # Compute each feature group
    # ------------------------------------------------------------------
    print("[Pipeline] Computing RFM features ...")
    rfm = compute_rfm_features(orders, reference_date)

    print("[Pipeline] Computing order behaviour features ...")
    order_behaviour = compute_order_behaviour_features(orders)

    print("[Pipeline] Computing discount features ...")
    discount = compute_discount_features(orders)

    print("[Pipeline] Computing channel features ...")
    channel = compute_channel_features(orders)

    print("[Pipeline] Computing payment features ...")
    payment = compute_payment_features(orders)

    print("[Pipeline] Computing category features ...")
    category = compute_category_features(orders, products)

    print("[Pipeline] Computing lifecycle features ...")
    lifecycle = compute_lifecycle_features(orders, customers, reference_date)

    print("[Pipeline] Computing story features ...")
    story = compute_story_features(story_customers)

    # ------------------------------------------------------------------
    # Join all feature groups onto the spine
    # ------------------------------------------------------------------
    print("[Pipeline] Joining feature groups onto customer spine ...")
    features = spine.copy()

    for df_feat in [
        rfm,
        order_behaviour,
        discount,
        channel,
        payment,
        category,
        lifecycle,
        story,
    ]:
        features = features.merge(df_feat, on="customer_id", how="left")

    # ------------------------------------------------------------------
    # Apply defaults for customers with zero orders
    # ------------------------------------------------------------------
    print("[Pipeline] Applying zero-order defaults ...")

    numeric_zero_cols = [
    "frequency", "monetary",
    "avg_order_value", "max_order_value", "min_order_value",
    "total_quantity",
    "avg_discount_pct", "discount_usage_rate",
    "website_orders_pct", "app_orders_pct", "whatsapp_orders_pct",
    "baby_care_orders", "family_essentials_orders",
    "wellness_orders", "self_care_orders", "nutrition_orders",
    "days_since_last_order", "avg_days_between_orders",
]
    for col in numeric_zero_cols:
        if col in features.columns:
            features[col] = features[col].fillna(DEFAULT_NUMERIC)
            # Customers with no orders should have recency equal to their tenure,
# rather than appearing as if they ordered yesterday.
    features["recency_days"] = (
        features["recency_days"]
        .fillna(features["customer_tenure_days"])
        .astype(int)
    )

    categorical_unknown_cols = [
        "preferred_payment_method",
        "favorite_category",
        "story_type",
        "journey_stage",
        "engagement_level",
    ]
    for col in categorical_unknown_cols:
        if col in features.columns:
            features[col] = features[col].fillna(DEFAULT_CATEGORICAL)
# ------------------------------------------------------------------
# Purchase velocity feature
# ------------------------------------------------------------------
# Normalises order frequency by customer tenure.
# Useful for churn modelling and customer intensity scoring.

    features["orders_per_month"] = np.where(
        features["customer_tenure_days"] > 0,
        features["frequency"] / (features["customer_tenure_days"] / 30),
        0.0,
    )
    features["orders_per_month"] = (
    features["orders_per_month"]
    .round(3)
)
    # Cast integer-typed columns (they may have become float due to NaN merge)
    int_cols = [
        "recency_days", "frequency", "total_quantity",
        "baby_care_orders", "family_essentials_orders",
        "wellness_orders", "self_care_orders", "nutrition_orders",
        "customer_tenure_days", "days_since_last_order",
    ]
    for col in int_cols:
        if col in features.columns:
            features[col] = features[col].fillna(0).astype(int)

    # ------------------------------------------------------------------
    # Reorder to canonical column order
    # ------------------------------------------------------------------

    # Export story flag as integer (0/1) for ML compatibility
    features["is_story_customer"] = (
        features["is_story_customer"]
        .astype(int)
    )


    available_output_cols = [c for c in OUTPUT_COLUMNS if c in features.columns]
    features = features[available_output_cols].reset_index(drop=True)

    print(f"[Pipeline] Feature generation complete. Shape: {features.shape}")
    return features


# ==============================================================================
# VALIDATION
# ==============================================================================


def validate(features: pd.DataFrame, customers: pd.DataFrame) -> None:
    """
    Run a suite of correctness assertions on the generated feature table.

    Checks performed
    ----------------
    1.  Row count matches the number of rows in customers.csv.
    2.  customer_id is unique (no duplicate customers).
    3.  frequency >= 0 for all customers.
    4.  monetary >= 0 for all customers.
    5.  recency_days >= 0 for all customers.
    6.  customer_tenure_days >= 0 for all customers.
    7.  website_orders_pct in [0, 1] for all customers.
    8.  app_orders_pct in [0, 1] for all customers.
    9.  whatsapp_orders_pct in [0, 1] for all customers.
    10. For customers with at least one order (frequency > 0), the sum of
        channel proportions approximately equals 1.0 (tolerance 0.01).

    Parameters
    ----------
    features : pd.DataFrame
        The feature table produced by generate_customer_features().
    customers : pd.DataFrame
        The raw customers table (used to check row-count equality).

    Raises
    ------
    AssertionError
        With a descriptive message if any check fails.
    """
    print("[Validation] Running validation checks ...")

    # Check 1: row count
    assert len(features) == len(customers), (
        f"Row count mismatch: features has {len(features)} rows "
        f"but customers has {len(customers)} rows."
    )

    # Check 2: uniqueness of customer_id
    assert features["customer_id"].is_unique, (
        "Duplicate customer_id values found in the feature table. "
        f"Duplicates: {features[features.duplicated('customer_id')]['customer_id'].tolist()}"
    )
    assert features["customer_id"].nunique() == len(customers), (
        f"Unique customer_id count ({features['customer_id'].nunique()}) "
        f"does not match customers row count ({len(customers)})."
    )

    # Check 3: frequency >= 0
    assert features["frequency"].ge(0).all(), (
        "Negative frequency values detected."
    )
    assert features["orders_per_month"].ge(0).all(), (
    "Negative orders_per_month values detected."
)

    # Check 4: monetary >= 0
    assert features["monetary"].ge(0).all(), (
        "Negative monetary values detected."
    )

    # Check 5: recency_days >= 0
    assert features["recency_days"].ge(0).all(), (
        "Negative recency_days values detected."
    )

    # Check 6: customer_tenure_days >= 0
    assert features["customer_tenure_days"].ge(0).all(), (
        "Negative customer_tenure_days values detected."
    )

    # Checks 7-9: channel proportions in [0, 1]
    for col in ["website_orders_pct", "app_orders_pct", "whatsapp_orders_pct"]:
        assert features[col].between(0, 1).all(), (
            f"Column '{col}' contains values outside [0, 1]."
        )

    # Check 10: channel proportions sum to 1.0 for ordering customers
    ordered_mask = features["frequency"] > 0
    if ordered_mask.any():
        pct_sum = (
            features.loc[ordered_mask, "website_orders_pct"]
            + features.loc[ordered_mask, "app_orders_pct"]
            + features.loc[ordered_mask, "whatsapp_orders_pct"]
        )
        max_deviation = (pct_sum - 1.0).abs().max()
        assert max_deviation <= 0.01, (
            f"Channel proportions do not sum to 1.0 for customers with orders. "
            f"Max deviation: {max_deviation:.6f} (tolerance 0.01)."
        )

    print("[Validation] All checks passed. ✓")


# ==============================================================================
# SUMMARY REPORT
# ==============================================================================


def print_summary(features: pd.DataFrame) -> None:
    """
    Print a human-readable summary of the generated feature table.

    Designed for interview demonstrations and quick pipeline health checks.
    Displays:
    - Total customers
    - Story customers
    - Non-story customers
    - Average recency (days)
    - Average frequency (orders)
    - Average monetary value
    - Top 5 favourite categories
    - Average customer tenure (days)

    Parameters
    ----------
    features : pd.DataFrame
        The validated feature table.
    """
    sep = "=" * 66

    story_count = features["is_story_customer"].sum()
    non_story_count = len(features) - story_count

    # Metrics for customers with at least one order
    ordered = features[features["frequency"] > 0]

    avg_recency = ordered["recency_days"].mean() if len(ordered) > 0 else 0
    avg_frequency = ordered["frequency"].mean() if len(ordered) > 0 else 0
    avg_velocity = (
    ordered["orders_per_month"].mean()
    if len(ordered) > 0 else 0
)
    avg_monetary = ordered["monetary"].mean() if len(ordered) > 0 else 0
    avg_tenure = features["customer_tenure_days"].mean()

    top5_categories = (
        features.loc[
            features["favorite_category"] != DEFAULT_CATEGORICAL,
            "favorite_category",
        ]
        .value_counts()
        .head(5)
    )

    print()
    print(sep)
    print("  AETHER CRM — CUSTOMER FEATURE ENGINEERING SUMMARY")
    print(sep)
    print(f"  {'Total customers':<35} {len(features):>10,}")
    print(f"  {'Story customers':<35} {int(story_count):>10,}")
    print(f"  {'Non-story customers':<35} {int(non_story_count):>10,}")
    print(sep)
    print("  RFM STATISTICS  (ordering customers only)")
    print(sep)
    print(f"  {'Average recency (days)':<35} {avg_recency:>10.1f}")
    print(f"  {'Average frequency (orders)':<35} {avg_frequency:>10.2f}")
    print(f"  {'Average orders per month':<35} {avg_velocity:>10.2f}")
    print(f"  {'Average monetary value':<35} {avg_monetary:>10.2f}")
    print(sep)
    print("  TOP 5 FAVOURITE CATEGORIES")
    print(sep)
    for rank, (cat, count) in enumerate(top5_categories.items(), start=1):
        pct = 100.0 * count / len(features)
        print(f"  {rank}. {cat:<32} {count:>6,} customers  ({pct:5.1f}%)")
    print(sep)
    print(f"  {'Average customer tenure (days)':<35} {avg_tenure:>10.1f}")
    print(sep)
    print()


# ==============================================================================
# EXPORT
# ==============================================================================


def export_features(features: pd.DataFrame, path: str) -> None:
    """
    Export the feature table to a CSV file.

    Dates are intentionally excluded from the export: the output contains
    only engineered numeric and categorical features derived from the raw
    source data.

    The output directory is created automatically if it does not exist.

    Parameters
    ----------
    features : pd.DataFrame
        The validated feature table.
    path : str
        Destination file path (e.g. "data/customer_features.csv").
    """
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Safety check: ensure no raw date columns leaked into the export
    date_cols = [
        col for col in features.columns
        if pd.api.types.is_datetime64_any_dtype(features[col])
    ]
    if date_cols:
        features = features.drop(columns=date_cols)
        print(f"[Export] Dropped datetime columns before export: {date_cols}")

    features.to_csv(path, index=False)
    print(f"[Export] Features exported to '{path}'  ({len(features):,} rows)")


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    """
    Execute the full Aether CRM customer feature engineering pipeline.

    Pipeline order
    --------------
    1. Load input files from data/.
    2. Generate customer features (RFM, order behaviour, discount,
       channel, payment, category, lifecycle, story).
    3. Validate the generated features.
    4. Print a summary report.
    5. Export the feature table to data/customer_features.csv.
    """
    print()
    print("=" * 66)
    print("  AETHER CRM — CUSTOMER FEATURE ENGINEERING PIPELINE")
    print("=" * 66)

    # ------------------------------------------------------------------
    # Step 1: Load inputs
    # ------------------------------------------------------------------
    print(f"\n[Load] Loading customers from '{INPUT_CUSTOMERS_PATH}' ...")
    customers = load_customers(INPUT_CUSTOMERS_PATH)
    print(f"[Load] {len(customers):,} customers loaded.")

    print(f"[Load] Loading orders from '{INPUT_ORDERS_PATH}' ...")
    orders = load_orders(INPUT_ORDERS_PATH)
    print(f"[Load] {len(orders):,} orders loaded.")

    print(f"[Load] Loading story customers from '{INPUT_STORY_CUSTOMERS_PATH}' ...")
    story_customers = load_story_customers(INPUT_STORY_CUSTOMERS_PATH)
    print(f"[Load] {len(story_customers):,} story customer records loaded.")

    print(f"[Load] Loading products from '{INPUT_PRODUCTS_PATH}' ...")
    products = load_products(INPUT_PRODUCTS_PATH)
    print(f"[Load] {len(products):,} products loaded.")

    # ------------------------------------------------------------------
    # Step 2: Generate features
    # ------------------------------------------------------------------
    print("\n[Pipeline] Starting feature generation ...")
    features = generate_customer_features(
        customers=customers,
        orders=orders,
        story_customers=story_customers,
        products=products,
    )

    # ------------------------------------------------------------------
    # Step 3: Validate
    # ------------------------------------------------------------------
    print("\n[Validation] Starting validation ...")
    validate(features, customers)

    # ------------------------------------------------------------------
    # Step 4: Print summary
    # ------------------------------------------------------------------
    print_summary(features)

    # ------------------------------------------------------------------
    # Step 5: Export
    # ------------------------------------------------------------------
    print("[Export] Exporting features ...")
    export_features(features, OUTPUT_FEATURES_PATH)

    print("\n[Done] Aether CRM feature pipeline completed successfully.\n")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    main()