

"""Generate explainable product affinity recommendations.

This module analyzes historical orders and identifies products that are
frequently purchased together. The output is used by Aether to support
cross-sell campaigns and next-best-product recommendations.
"""

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import json

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data_generation" / "data"
ORDERS_PATH = DATA_DIR / "orders.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
OUTPUT_CSV = DATA_DIR / "product_affinity.csv"
OUTPUT_JSON = DATA_DIR / "product_affinity.json"


TOP_N_RECOMMENDATIONS = 3


def build_product_affinity():
    """Generate product affinity outputs from historical orders."""

    print("[pipeline] building product affinity recommendations ...")

    orders_df = pd.read_csv(ORDERS_PATH)
    products_df = pd.read_csv(PRODUCTS_PATH)

    product_lookup = dict(
        zip(
            products_df["product_id"],
            products_df["name"],
        )
    )

    required_columns = {"customer_id", "product_id"}
    missing = required_columns - set(orders_df.columns)

    if missing:
        raise ValueError(
            f"orders.csv missing required columns: {sorted(missing)}"
        )

    customer_products = (
        orders_df.groupby("customer_id")["product_id"]
        .apply(lambda products: sorted(set(products)))
    )

    affinity_counter = defaultdict(Counter)

    for products in customer_products:
        for product_a, product_b in combinations(products, 2):
            affinity_counter[product_a][product_b] += 1
            affinity_counter[product_b][product_a] += 1

    affinity_json = {}
    affinity_rows = []

    for product_id, related_products in affinity_counter.items():
        top_matches = related_products.most_common(TOP_N_RECOMMENDATIONS)

        affinity_json[product_id] = {
            "product_name": product_lookup.get(
                product_id,
                product_id,
            ),
            "recommendations": [
                {
                    "product_id": related_product,
                    "product_name": product_lookup.get(
                        related_product,
                        related_product,
                    ),
                    "co_purchase_count": frequency,
                }
                for related_product, frequency in top_matches
            ],
        }

        for related_product, frequency in top_matches:
            affinity_rows.append(
                {
                    "product_id": product_id,
                    "product_name": product_lookup.get(
                        product_id,
                        product_id,
                    ),
                    "recommended_product_id": related_product,
                    "recommended_product_name": product_lookup.get(
                        related_product,
                        related_product,
                    ),
                    "co_purchase_count": frequency,
                }
            )

    pd.DataFrame(affinity_rows).to_csv(OUTPUT_CSV, index=False)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(affinity_json, file, indent=4)

    print(
        f"[pipeline] product affinity saved → {OUTPUT_JSON}"
    )

    return affinity_json


if __name__ == "__main__":
    build_product_affinity()