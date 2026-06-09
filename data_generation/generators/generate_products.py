# generate_products.py
#
# Purpose: Generate the Aether product catalog (80 products) and export to data/products.csv
#
# Run this FIRST in the generation pipeline before any other script.
# All downstream scripts (customers, orders) will reference product_ids from this file.
#
# Revision notes:
#   - is_premium is now an explicit field on ProductTemplate (editorial decision,
#     not inferred from price). A premium product is one the brand positions as
#     premium — price alone cannot determine this reliably.
#   - All 80 products are fully specified in PRODUCT_CATALOG with no programmatic
#     derivation of names, categories, or flags.

import random
import numpy as np
import pandas as pd
from pathlib import Path

# ── Reproducibility ────────────────────────────────────────────────────────────
# Both seeds are set at module level so every random call in this file
# produces the same output on every run, regardless of execution environment.
random.seed(42)
np.random.seed(42)

# ── Output path ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data"
OUTPUT_FILE = OUTPUT_DIR / "products.csv"


# ── Dataclass: ProductTemplate ─────────────────────────────────────────────────
# Represents one product as defined by the brand team.
# Every field here is an intentional editorial decision — nothing is derived
# from other fields at template-definition time.
#
# is_premium: True if the brand positions this SKU as a premium product.
#             This is a brand/marketing designation, not a price calculation.
#             A ₹299 herbal powder can be premium; a ₹999 commodity cannot.
@dataclass
class ProductTemplate:
    name:               str
    category:           str
    subcategory:        str
    price_min:          int   # Lower bound for seeded price randomisation
    price_max:          int   # Upper bound for seeded price randomisation
    replenishment_days: int     # Expected days between repeat purchases
    is_premium:         bool    # Brand-designated premium flag (NOT derived from price)


# ── Product Catalog Blueprint ──────────────────────────────────────────────────
# All 80 products are listed explicitly.
#
# Premium designation rationale per category:
#   Baby Care     — premium = advanced formulation (organic, clinically tested)
#   Self Care     — premium = actives-based skincare (serums, retinol, peptides)
#   Wellness      — premium = high-bioavailability or branded ingredient (KSM-66, etc.)
#   Family Essentials — premium = durable, safety-certified, or long-life hardware
#
# Category counts: Baby Care 25 | Self Care 25 | Wellness 20 | Family Essentials 10

PRODUCT_CATALOG = [

    # ── BABY CARE (25 products) ────────────────────────────────────────────────
    # Subcategories: Bath & Body, Skin Care, Diapering, Feeding, Health & Safety
    # Replenishment is fast (15–45 days) — baby consumables deplete quickly.
    # Premium = organic certification, clinically tested, or dermatologist-approved.

    ProductTemplate("Gentle Baby Shampoo 200ml",          "Baby Care", "Bath & Body",     180,  320,  30,  False),
    ProductTemplate("Tear-Free Baby Wash 400ml",          "Baby Care", "Bath & Body",     220,  380,  30,  False),
    ProductTemplate("Baby Bubble Bath Liquid 500ml",      "Baby Care", "Bath & Body",     250,  420,  45,  False),
    ProductTemplate("Organic Cotton Baby Towel",          "Baby Care", "Bath & Body",     480,  780,  180, True),
    ProductTemplate("Soft Baby Massage Oil 100ml",        "Baby Care", "Skin Care",       300,  500,  45,  False),
    ProductTemplate("Baby Moisturising Lotion 200ml",     "Baby Care", "Skin Care",       280,  460,  30,  False),
    ProductTemplate("Nappy Rash Cream 50g",               "Baby Care", "Skin Care",       350,  580,  45,  False),
    ProductTemplate("Baby Sunscreen SPF 50 100ml",        "Baby Care", "Skin Care",       550,  899,  60,  True),
    ProductTemplate("Baby Talc-Free Powder 200g",         "Baby Care", "Skin Care",       180,  300,  30,  False),
    ProductTemplate("Organic Nappy Rash Balm 75g",        "Baby Care", "Skin Care",       520,  850,  45,  True),
    ProductTemplate("Baby Hair & Scalp Oil 50ml",         "Baby Care", "Skin Care",       340,  560,  45,  False),
    ProductTemplate("Biodegradable Baby Wipes 80ct",      "Baby Care", "Diapering",       220,  360,  15,  False),
    ProductTemplate("Sensitive Skin Diapers S 40ct",      "Baby Care", "Diapering",       580,  920,  15,  False),
    ProductTemplate("Sensitive Skin Diapers M 36ct",      "Baby Care", "Diapering",       620,  980,  15,  False),
    ProductTemplate("Sensitive Skin Diapers L 32ct",      "Baby Care", "Diapering",       650,  999,  15,  False),
    ProductTemplate("Baby Feeding Bottle 150ml",          "Baby Care", "Feeding",         380,  650,  90,  False),
    ProductTemplate("Anti-Colic Feeding Bottle 250ml",    "Baby Care", "Feeding",         550,  899,  90,  True),
    ProductTemplate("Silicone Baby Spoon Set",            "Baby Care", "Feeding",         320,  520,  180, False),
    ProductTemplate("Baby Food Masher & Bowl",            "Baby Care", "Feeding",         420,  680,  180, False),
    ProductTemplate("Breast Milk Storage Bags 25ct",      "Baby Care", "Feeding",         380,  580,  30,  False),
    ProductTemplate("Baby Nasal Saline Drops 15ml",       "Baby Care", "Health & Safety", 280,  420,  60,  False),
    ProductTemplate("Infant Gripe Water 100ml",           "Baby Care", "Health & Safety", 180,  320,  30,  False),
    ProductTemplate("Baby Digital Thermometer",           "Baby Care", "Health & Safety", 650,  999,  365, True),
    ProductTemplate("Baby Nail Care Kit",                 "Baby Care", "Health & Safety", 350,  580,  180, False),
    ProductTemplate("Baby Mosquito Repellent Patch 24ct", "Baby Care", "Health & Safety", 220,  380,  30,  False),

    # ── SELF CARE (25 products) ────────────────────────────────────────────────
    # Subcategories: Face Care, Body Care, Hair Care, Personal Hygiene, Relaxation
    # Replenishment is moderate (30–90 days) — adult products last longer.
    # Premium = actives-based formulations (vitamin C, retinol, hyaluronic acid, peptides).

    ProductTemplate("Vitamin C Face Serum 30ml",          "Self Care", "Face Care",       699,  1199, 60,  True),
    ProductTemplate("Hyaluronic Acid Moisturiser 50ml",   "Self Care", "Face Care",       599,  999,  60,  True),
    ProductTemplate("Niacinamide Toner 100ml",            "Self Care", "Face Care",       449,  749,  45,  True),
    ProductTemplate("SPF 50 Sunscreen Fluid 50ml",        "Self Care", "Face Care",       499,  849,  45,  False),
    ProductTemplate("Retinol Night Cream 50g",            "Self Care", "Face Care",       799,  1399, 60,  True),
    ProductTemplate("Clay Detox Face Mask 75ml",          "Self Care", "Face Care",       399,  699,  30,  False),
    ProductTemplate("Micellar Cleansing Water 200ml",     "Self Care", "Face Care",       299,  499,  45,  False),
    ProductTemplate("Under Eye Gel Cream 20ml",           "Self Care", "Face Care",       549,  899,  60,  True),
    ProductTemplate("Brightening Face Scrub 100g",        "Self Care", "Face Care",       349,  599,  30,  False),
    ProductTemplate("Rose Hip Body Oil 100ml",            "Self Care", "Body Care",       599,  999,  60,  True),
    ProductTemplate("Shea Butter Body Lotion 250ml",      "Self Care", "Body Care",       349,  599,  30,  False),
    ProductTemplate("Exfoliating Body Scrub 200g",        "Self Care", "Body Care",       399,  649,  30,  False),
    ProductTemplate("Stretch Mark Cream 150ml",           "Self Care", "Body Care",       549,  899,  60,  True),
    ProductTemplate("Argan Oil Hair Serum 50ml",          "Self Care", "Hair Care",       449,  749,  45,  True),
    ProductTemplate("Biotin Shampoo 300ml",               "Self Care", "Hair Care",       349,  599,  30,  False),
    ProductTemplate("Keratin Hair Mask 200ml",            "Self Care", "Hair Care",       499,  849,  30,  True),
    ProductTemplate("Scalp Scrub 100g",                   "Self Care", "Hair Care",       399,  649,  30,  False),
    ProductTemplate("Dry Shampoo Spray 150ml",            "Self Care", "Hair Care",       299,  499,  30,  False),
    ProductTemplate("Charcoal Teeth Whitening Powder 50g","Self Care", "Personal Hygiene",299,  499,  45,  False),
    ProductTemplate("Natural Deodorant Stick 75g",        "Self Care", "Personal Hygiene",349,  549,  45,  False),
    ProductTemplate("Tongue Cleaner Copper",              "Self Care", "Personal Hygiene",199,  349,  365, False),
    ProductTemplate("Bamboo Toothbrush Set 4pk",          "Self Care", "Personal Hygiene",199,  349,  90,  False),
    ProductTemplate("Lavender Bath Salts 500g",           "Self Care", "Relaxation",      299,  499,  30,  False),
    ProductTemplate("Aromatherapy Shower Steamer 6pk",    "Self Care", "Relaxation",      399,  649,  30,  False),
    ProductTemplate("Silk Sleep Eye Mask",                "Self Care", "Relaxation",      349,  599,  365, True),

    # ── WELLNESS (20 products) ─────────────────────────────────────────────────
    # Subcategories: Supplements, Herbal, Nutrition, Fitness, Mental Wellness
    # Supplements replenish on strict 30-day cycles (monthly purchase pattern).
    # Premium = branded ingredient (KSM-66 Ashwagandha, Albion chelated minerals),
    #           high CFU count, or clinical-grade bioavailability.

    ProductTemplate("Multivitamin Women 60 Tablets",      "Wellness",  "Supplements",     599,  999,  30,  False),
    ProductTemplate("Multivitamin Men 60 Tablets",        "Wellness",  "Supplements",     599,  999,  30,  False),
    ProductTemplate("Omega-3 Fish Oil 60 Softgels",       "Wellness",  "Supplements",     649,  1099, 30,  True),
    ProductTemplate("Vitamin D3 + K2 60 Tablets",         "Wellness",  "Supplements",     499,  849,  30,  False),
    ProductTemplate("Probiotic 10B CFU 30 Capsules",      "Wellness",  "Supplements",     699,  1199, 30,  True),
    ProductTemplate("Iron + Folic Acid 60 Tablets",       "Wellness",  "Supplements",     349,  599,  30,  False),
    ProductTemplate("Collagen Peptides Powder 200g",      "Wellness",  "Supplements",     899,  1499, 30,  True),
    ProductTemplate("Ashwagandha KSM-66 60 Capsules",     "Wellness",  "Herbal",          499,  849,  30,  True),
    ProductTemplate("Triphala Churna 100g",               "Wellness",  "Herbal",          199,  349,  30,  False),
    ProductTemplate("Turmeric Curcumin 500mg 60 Caps",    "Wellness",  "Herbal",          399,  699,  30,  False),
    ProductTemplate("Moringa Leaf Powder 100g",           "Wellness",  "Herbal",          249,  449,  30,  False),
    ProductTemplate("Giloy Tulsi Immunity Drops 30ml",    "Wellness",  "Herbal",          299,  499,  30,  False),
    ProductTemplate("Protein Granola Bars 6pk",           "Wellness",  "Nutrition",       349,  549,  15,  False),
    ProductTemplate("Cold Pressed Coconut Oil 500ml",     "Wellness",  "Nutrition",       449,  749,  30,  False),
    ProductTemplate("Raw Wildflower Honey 500g",          "Wellness",  "Nutrition",       399,  649,  30,  False),
    ProductTemplate("Organic Chia Seeds 250g",            "Wellness",  "Nutrition",       299,  499,  30,  False),
    ProductTemplate("Eco-Friendly Yoga Mat 6mm",          "Wellness",  "Fitness",         999,  1799, 365, True),
    ProductTemplate("Resistance Bands Set 5-Level",       "Wellness",  "Fitness",         599,  999,  365, False),
    ProductTemplate("Guided Mindfulness Journal",         "Wellness",  "Mental Wellness",  349,  599,  180, False),
    ProductTemplate("Lavender Pillow Mist 100ml",         "Wellness",  "Mental Wellness",  299,  499,  45,  False),

    # ── FAMILY ESSENTIALS (10 products) ───────────────────────────────────────
    # Subcategories: Home, Kitchen, Safety, Household
    # Premium = durable materials, safety-certified, or long-lifecycle hardware.
    # These are household staples with low replenishment frequency.

    ProductTemplate("Plant-Based Multi-Surface Cleaner 500ml","Family Essentials","Home",      299,  499,  30,  False),
    ProductTemplate("Eco Laundry Liquid 1L",               "Family Essentials", "Home",        449,  749,  30,  False),
    ProductTemplate("BPA-Free Food Storage Set 5pc",       "Family Essentials", "Kitchen",     599,  999,  180, True),
    ProductTemplate("Stainless Steel Water Bottle 750ml",  "Family Essentials", "Kitchen",     699,  1199, 365, True),
    ProductTemplate("Beeswax Wraps Set of 3",              "Family Essentials", "Kitchen",     349,  599,  90,  False),
    ProductTemplate("Family First Aid Kit 50pc",           "Family Essentials", "Safety",      799,  1299, 365, True),
    ProductTemplate("Child Safety Cabinet Locks 8pk",      "Family Essentials", "Safety",      299,  499,  365, False),
    ProductTemplate("Smoke & CO Detector Combo",           "Family Essentials", "Safety",      899,  1499, 730, True),
    ProductTemplate("Reusable Grocery Bags Set 5pk",       "Family Essentials", "Household",   199,  349,  180, False),
    ProductTemplate("Compostable Trash Bags 30ct",         "Family Essentials", "Household",   249,  399,  30,  False),
]


# ── Helper: Assign price ────────────────────────────────────────────────────────
def assign_price(template: ProductTemplate) -> int:
    """
    Assign an integer INR price within the product's defined range.

    Integer prices are more realistic for Indian ecommerce datasets
    and simplify downstream analytics.

    Deterministic because numpy's random seed is fixed.
    """
    return int(
        np.random.randint(
            template.price_min,
            template.price_max + 1
        )
    )


# ── Core builder: templates → DataFrame ────────────────────────────────────────
def build_products_dataframe(catalog: list[ProductTemplate]) -> pd.DataFrame:
    """
    Convert the list of ProductTemplate objects into a pandas DataFrame.

    Each template becomes exactly one row.
    product_id is zero-padded to 5 digits: PROD00001 … PROD00080.
    is_premium is passed through directly from the template — no inference applied.
    """
    rows = []

    for index, template in enumerate(catalog):
        product_number = index + 1          # 1-based so IDs start at PROD00001
        product_id = f"PROD{product_number:05d}"
        price = assign_price(template)

        row = {
            "product_id":         product_id,
            "name":               template.name,
            "category":           template.category,
            "subcategory":        template.subcategory,
            "price":              price,
            "replenishment_days": template.replenishment_days,
            "is_premium":         template.is_premium,   # Direct pass-through, no inference
        }

        rows.append(row)

    return pd.DataFrame(rows)


# ── Validation ─────────────────────────────────────────────────────────────────
def validate_products(df: pd.DataFrame) -> None:
    """
    Hard assertions confirming the dataset meets spec before writing to disk.

    Uses assert (not if/raise) because this is a controlled pipeline script.
    A silent failure here corrupts every downstream generator — loud failure is correct.
    """
    expected_total = 80
    expected_category_counts = {
        "Baby Care":         25,
        "Self Care":         25,
        "Wellness":          20,
        "Family Essentials": 10,
    }

    # ── Check 1: total product count
    actual_total = len(df)
    assert actual_total == expected_total, (
        f"Total product count mismatch — expected {expected_total}, got {actual_total}"
    )

    # ── Check 2: per-category counts
    category_counts = df["category"].value_counts().to_dict()
    for category, expected_count in expected_category_counts.items():
        actual_count = category_counts.get(category, 0)
        assert actual_count == expected_count, (
            f"Category '{category}': expected {expected_count} products, got {actual_count}"
        )

    # ── Check 3: product_id uniqueness
    assert df["product_id"].nunique() == expected_total, (
        "Duplicate product_ids detected — each product must have a unique ID"
    )

    # ── Check 4: no null values anywhere
    null_counts = df.isnull().sum()
    assert null_counts.sum() == 0, (
        f"Null values found: {null_counts[null_counts > 0].to_dict()}"
    )
    
    # ── Check 5: is_premium is strictly boolean (not inferred float or string)
    assert pd.api.types.is_bool_dtype(df["is_premium"]), (
    f"is_premium column must be boolean dtype, got {df['is_premium'].dtype}"
)
# Check 6: prices must be positive integers
    assert (df["price"] > 0).all(), (
        "All product prices must be positive"
    )

    assert pd.api.types.is_integer_dtype(df["price"]), (
        f"Price column must contain integer INR values, got {df['price'].dtype}"
    )


    print("✓ Validation passed:")
    print(f"  Total products    : {actual_total}")
    for category, count in expected_category_counts.items():
        print(f"  {category:<22}: {count}")
    print(f"  Unique IDs        : {df['product_id'].nunique()}")
    print(f"  Premium products  : {df['is_premium'].sum()}")
    print(f"  Standard products : {(~df['is_premium']).sum()}")


# ── Main entry point ───────────────────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating product catalog...")
    df = build_products_dataframe(PRODUCT_CATALOG)

    print("\nRunning validations...")
    validate_products(df)

    # index=False — product_id is our explicit identifier; pandas row index is noise
    df["story_customer_id"] = (
    df["story_customer_id"]
    .fillna("")
    .astype(str)
)

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n✓ Products saved to: {OUTPUT_FILE}")

    print("\nSample rows (first 5):")
    print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()