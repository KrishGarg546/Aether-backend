"""
generate_customers.py
---------------------
Aether CRM — Synthetic Customer Generation Layer
Generates 10,000 realistic Indian D2C customers for the Aether family wellness brand.

Fields exported:
    customer_id, name, email, phone, age, gender, city, state,
    persona, join_date, customer_since_month, preferred_channel,
    source, is_story_customer, story_customer_id
"""

import random
import numpy as np
import pandas as pd
from faker import Faker
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Deterministic seeds — ensures reproducible output across runs
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
Faker.seed(RANDOM_SEED)

# Use Indian locale for realistic names
fake = Faker("en_IN")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOTAL_CUSTOMERS = 10_000

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "customers.csv"

# ---------------------------------------------------------------------------
# Persona configuration
# ---------------------------------------------------------------------------
PERSONAS = [
    "New Parents",
    "Seasoned Parents",
    "Wellness Seekers",
    "Premium Self-Care",
    "Budget Families",
    "Dormant Customers",
]

# Exact persona counts — deterministic allocation guarantees the segmentation
# proportions are precise rather than approximate (no sampling variance).
PERSONA_COUNTS = {
    "New Parents":       1500,
    "Seasoned Parents":  2000,
    "Wellness Seekers":  2000,
    "Premium Self-Care": 2000,
    "Budget Families":   1500,
    "Dormant Customers": 1000,
}

# Weights derived from counts so validate() proportion checks stay in sync.
PERSONA_WEIGHTS = [PERSONA_COUNTS[p] / TOTAL_CUSTOMERS for p in PERSONAS]

# Age ranges per persona (min, max) — inclusive
PERSONA_AGE_RANGES = {
    "New Parents":       (24, 35),
    "Seasoned Parents":  (28, 42),
    "Wellness Seekers":  (22, 38),
    "Premium Self-Care": (25, 45),
    "Budget Families":   (25, 45),
    # Dormant customers are derived from a mix of all other personas
    # so their age range spans the union of all above
    "Dormant Customers": (22, 45),
}

# ---------------------------------------------------------------------------
# Gender distribution
# ---------------------------------------------------------------------------
GENDERS = ["Female", "Male", "Other"]
GENDER_WEIGHTS = [0.52, 0.47, 0.01]

# ---------------------------------------------------------------------------
# Geographic distribution
# City → (state, weight)  — weights will be normalised at runtime
# ---------------------------------------------------------------------------
CITY_DATA = {
    "Mumbai":       ("Maharashtra",     12),
    "Delhi":        ("Delhi",           12),
    "Bangalore":    ("Karnataka",       12),
    "Hyderabad":    ("Telangana",       10),
    "Chennai":      ("Tamil Nadu",       8),
    "Pune":         ("Maharashtra",      8),
    "Kolkata":      ("West Bengal",      5),
    "Ahmedabad":    ("Gujarat",          5),
    "Jaipur":       ("Rajasthan",        4),
    "Lucknow":      ("Uttar Pradesh",    4),
    "Indore":       ("Madhya Pradesh",   3),
    "Chandigarh":   ("Punjab",           3),
    "Kochi":        ("Kerala",           3),
    "Coimbatore":   ("Tamil Nadu",       2),
    "Nagpur":       ("Maharashtra",      2),
    "Bhopal":       ("Madhya Pradesh",   2),
    "Patna":        ("Bihar",            2),
    "Surat":        ("Gujarat",          1),
    "Guwahati":     ("Assam",            1),
    "Bhubaneswar":  ("Odisha",           1),
}

CITIES       = list(CITY_DATA.keys())
CITY_WEIGHTS_RAW = [CITY_DATA[c][1] for c in CITIES]
_total_w     = sum(CITY_WEIGHTS_RAW)
CITY_WEIGHTS = [w / _total_w for w in CITY_WEIGHTS_RAW]   # normalised

# ---------------------------------------------------------------------------
# Join-date configuration  (2024-06-01 → 2026-06-01)
# ---------------------------------------------------------------------------
JOIN_DATE_START = pd.Timestamp("2024-06-01")
JOIN_DATE_END   = pd.Timestamp("2026-06-01")

# Monthly seasonality multipliers (1 = baseline)
# January spike: wellness resolutions; Oct/Nov: festive shopping
MONTH_MULTIPLIERS = {
    1: 1.3, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0,  6: 1.0,
    7: 1.0, 8: 1.0, 9: 1.0, 10: 1.2, 11: 1.1, 12: 1.0,
}

# ---------------------------------------------------------------------------
# Preferred communication channel — per-persona probabilities
# Order: EMAIL, WHATSAPP, SMS, RCS
# ---------------------------------------------------------------------------
CHANNELS = ["EMAIL", "WHATSAPP", "SMS", "RCS"]

CHANNEL_WEIGHTS_BY_PERSONA = {
    "New Parents":       [0.40, 0.35, 0.15, 0.10],
    "Seasoned Parents":  [0.30, 0.45, 0.20, 0.05],
    "Wellness Seekers":  [0.50, 0.20, 0.10, 0.20],
    "Premium Self-Care": [0.45, 0.25, 0.05, 0.25],
    "Budget Families":   [0.20, 0.35, 0.40, 0.05],
    "Dormant Customers": [0.35, 0.30, 0.30, 0.05],
}

# ---------------------------------------------------------------------------
# Acquisition source — per-persona probabilities
# Order: ORGANIC, INSTAGRAM, GOOGLE, REFERRAL, WHATSAPP, INFLUENCER
# ---------------------------------------------------------------------------
SOURCES = ["ORGANIC", "INSTAGRAM", "GOOGLE", "REFERRAL", "WHATSAPP", "INFLUENCER"]

# Business rationale:
#   New Parents      — heavy Instagram/Influencer discovery
#   Seasoned Parents — more WhatsApp word-of-mouth / referral
#   Wellness Seekers — Google search-led + Influencer content
#   Premium Self-Care— Instagram aspirational + Google research
#   Budget Families  — WhatsApp forwards + Organic
#   Dormant Customers— mostly Organic / older acquisition, lower social
SOURCE_WEIGHTS_BY_PERSONA = {
    "New Parents":       [0.15, 0.30, 0.15, 0.15, 0.10, 0.15],
    "Seasoned Parents":  [0.20, 0.15, 0.15, 0.25, 0.20, 0.05],
    "Wellness Seekers":  [0.15, 0.20, 0.25, 0.10, 0.10, 0.20],
    "Premium Self-Care": [0.10, 0.30, 0.20, 0.15, 0.05, 0.20],
    "Budget Families":   [0.25, 0.15, 0.15, 0.15, 0.25, 0.05],
    "Dormant Customers": [0.35, 0.15, 0.20, 0.15, 0.10, 0.05],
}

# ---------------------------------------------------------------------------
# Email providers — realistic Indian distribution
# ---------------------------------------------------------------------------
EMAIL_PROVIDERS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com"]
EMAIL_PROVIDER_WEIGHTS = [0.60, 0.15, 0.12, 0.08, 0.05]


# ---------------------------------------------------------------------------
# Helper: generate weighted join-date array respecting seasonality
# ---------------------------------------------------------------------------
def _build_join_date_weights() -> np.ndarray:
    """
    Build a day-level probability array over the generation window,
    scaled by per-month multipliers to simulate acquisition seasonality.
    """
    date_range = pd.date_range(JOIN_DATE_START, JOIN_DATE_END - pd.Timedelta(days=1), freq="D")
    weights = np.array([MONTH_MULTIPLIERS[d.month] for d in date_range], dtype=float)
    return weights / weights.sum(), date_range


JOIN_DATE_WEIGHTS, JOIN_DATE_RANGE = _build_join_date_weights()


def sample_join_dates(n: int) -> pd.Series:
    """Sample n join dates using seasonality-aware weights."""
    indices = np.random.choice(len(JOIN_DATE_RANGE), size=n, replace=True, p=JOIN_DATE_WEIGHTS)
    return pd.Series([JOIN_DATE_RANGE[i].date() for i in indices])


# ---------------------------------------------------------------------------
# Helper: generate unique Indian phone numbers
# ---------------------------------------------------------------------------
def generate_phone_numbers(n: int) -> list[str]:
    """
    Generate n unique 10-digit Indian mobile numbers.
    Indian mobiles start with 6, 7, 8, or 9.
    Stored as strings to preserve leading zeros if ever present.
    """
    prefixes = [6, 7, 8, 9]
    generated: set[str] = set()
    phones: list[str] = []

    while len(phones) < n:
        prefix = random.choice(prefixes)
        # zfill(9) preserves leading zeros in the suffix, covering the full
        # 000_000_000–999_999_999 space for a realistic number distribution.
        suffix = str(random.randint(0, 999_999_999)).zfill(9)
        number = f"{prefix}{suffix}"
        if number not in generated:
            generated.add(number)
            phones.append(number)

    return phones


# ---------------------------------------------------------------------------
# Helper: generate unique email addresses
# ---------------------------------------------------------------------------
def generate_emails(names: list[str], n: int) -> list[str]:
    """
    Generate n unique email addresses derived from customer names.
    Formats: firstname.lastname@provider, firstname123@provider
    """
    generated: set[str] = set()
    emails: list[str] = []

    provider_choices = random.choices(
        EMAIL_PROVIDERS, weights=EMAIL_PROVIDER_WEIGHTS, k=n * 2  # oversample for collision headroom
    )
    provider_idx = 0

    for i, full_name in enumerate(names):
        parts = full_name.lower().split()
        first = parts[0] if parts else "user"
        last  = parts[-1] if len(parts) > 1 else str(i)

        provider = provider_choices[provider_idx % len(provider_choices)]
        provider_idx += 1

        # Alternate between two common formats
        if random.random() < 0.6:
            base = f"{first}.{last}"
        else:
            base = f"{first}{random.randint(1, 999)}"

        # Strip non-alpha characters that sneak in from Faker names
        base = "".join(c for c in base if c.isalnum() or c == ".")

        candidate = f"{base}@{provider}"

        # Resolve collisions by appending a numeric suffix
        attempt = 0
        while candidate in generated:
            attempt += 1
            candidate = f"{base}{attempt}@{provider}"

        generated.add(candidate)
        emails.append(candidate)

    return emails


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------
def generate_customers() -> pd.DataFrame:
    """
    Build the full 10,000-row customers DataFrame.
    Returns a validated DataFrame ready for CSV export.
    """

    # ------------------------------------------------------------------
    # 1. Assign personas — exact counts, then shuffle to avoid grouping
    # ------------------------------------------------------------------
    # Build the list by repeating each persona label exactly PERSONA_COUNTS[p]
    # times, then shuffle in-place so personas are interleaved uniformly.
    # This eliminates sampling variance: proportions will be exact, not ~exact.
    personas: list[str] = []
    for persona in PERSONAS:
        personas.extend([persona] * PERSONA_COUNTS[persona])
    random.shuffle(personas)

    # ------------------------------------------------------------------
    # 2. Assign genders
    # ------------------------------------------------------------------
    genders = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=TOTAL_CUSTOMERS)

    # ------------------------------------------------------------------
    # 3. Generate ages — drawn per-persona from uniform integer range
    # ------------------------------------------------------------------
    ages = [
        random.randint(*PERSONA_AGE_RANGES[p])
        for p in personas
    ]

    # ------------------------------------------------------------------
    # 4. Generate names using Faker (Indian locale)
    # ------------------------------------------------------------------
    # Using explicit first_name() + last_name() produces more diverse
    # combinations than fake.name(), which can lean on a narrower template set.
    names = [
        f"{fake.first_name()} {fake.last_name()}"
        for _ in range(TOTAL_CUSTOMERS)
    ]

    # ------------------------------------------------------------------
    # 5. Generate emails (unique)
    # ------------------------------------------------------------------
    emails = generate_emails(names, TOTAL_CUSTOMERS)

    # ------------------------------------------------------------------
    # 6. Generate phone numbers (unique)
    # ------------------------------------------------------------------
    phones = generate_phone_numbers(TOTAL_CUSTOMERS)

    # ------------------------------------------------------------------
    # 7. Assign cities and states (weighted by tier)
    # ------------------------------------------------------------------
    city_indices = np.random.choice(len(CITIES), size=TOTAL_CUSTOMERS, p=CITY_WEIGHTS)
    cities = [CITIES[i] for i in city_indices]
    states = [CITY_DATA[c][0] for c in cities]

    # ------------------------------------------------------------------
    # 8. Sample join dates with seasonality
    # ------------------------------------------------------------------
    join_dates = sample_join_dates(TOTAL_CUSTOMERS)

    # Derived field: YYYY-MM string for easy cohort bucketing
    customer_since_months = join_dates.apply(lambda d: d.strftime("%Y-%m"))

    # ------------------------------------------------------------------
    # 9. Assign preferred communication channels (persona-specific)
    # ------------------------------------------------------------------
    channels = [
        random.choices(CHANNELS, weights=CHANNEL_WEIGHTS_BY_PERSONA[p], k=1)[0]
        for p in personas
    ]

    # ------------------------------------------------------------------
    # 10. Assign acquisition sources (persona-specific)
    # ------------------------------------------------------------------
    sources = [
        random.choices(SOURCES, weights=SOURCE_WEIGHTS_BY_PERSONA[p], k=1)[0]
        for p in personas
    ]

    # ------------------------------------------------------------------
    # 11. Story-customer placeholders — populated in a later script
    # ------------------------------------------------------------------
    is_story_customer = [False] * TOTAL_CUSTOMERS
    story_customer_id = [""] * TOTAL_CUSTOMERS   # empty string (not NaN) for clean CSV

    # ------------------------------------------------------------------
    # 12. Build deterministic customer IDs
    # ------------------------------------------------------------------
    customer_ids = [f"CUST{str(i).zfill(5)}" for i in range(1, TOTAL_CUSTOMERS + 1)]

    # ------------------------------------------------------------------
    # 13. Assemble DataFrame
    # ------------------------------------------------------------------
    df = pd.DataFrame({
        "customer_id":          customer_ids,
        "name":                 names,
        "email":                emails,
        "phone":                phones,
        "age":                  ages,
        "gender":               genders,
        "city":                 cities,
        "state":                states,
        "persona":              personas,
        "join_date":            join_dates,
        "customer_since_month": customer_since_months,
        "preferred_channel":    channels,
        "source":               sources,
        "is_story_customer":    is_story_customer,
        "story_customer_id":    story_customer_id,
    })

    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(df: pd.DataFrame) -> None:
    """
    Run data-quality checks.
    Raises AssertionError immediately if any constraint is violated.
    """
    assert len(df) == TOTAL_CUSTOMERS, \
        f"Expected {TOTAL_CUSTOMERS} rows, got {len(df)}"

    assert df["customer_id"].nunique() == TOTAL_CUSTOMERS, \
        "Duplicate customer_ids detected"
    assert (
    df["customer_id"]
    .str.match(r"^CUST\d{5}$")
    .all()
), "Customer ID format violation detected"

    assert df["email"].nunique() == TOTAL_CUSTOMERS, \
        "Duplicate emails detected"

    assert df["phone"].nunique() == TOTAL_CUSTOMERS, \
        "Duplicate phone numbers detected"

    assert df.isnull().sum().sum() == 0, \
        "Null values detected in the dataset"

    assert set(df["persona"].unique()).issubset(set(PERSONAS)), \
        "Unknown persona values detected"

    assert set(df["preferred_channel"].unique()).issubset(set(CHANNELS)), \
        "Unknown channel values detected"

    assert set(df["source"].unique()).issubset(set(SOURCES)), \
        "Unknown source values detected"

    # Persona proportion check — allow ±3% tolerance
    # Persona counts must match the exact deterministic allocation
    # Persona counts must match the exact deterministic allocation
    persona_counts = df["persona"].value_counts().to_dict()

    for persona, expected_count in PERSONA_COUNTS.items():
        actual_count = persona_counts.get(persona, 0)

        assert actual_count == expected_count, (
            f"{persona}: expected {expected_count}, got {actual_count}"
        )

    # Phone format: exactly 10 digits, starting with 6, 7, 8, or 9
    assert (
        df["phone"]
        .str.match(r"^[6789]\d{9}$")
        .all()
    ), "One or more phone numbers fail the Indian mobile format check"

    # customer_since_month format: YYYY-MM
    assert (
        df["customer_since_month"]
        .str.match(r"^\d{4}-\d{2}$")
        .all()
    ), "One or more customer_since_month values are not in YYYY-MM format"

    # Age validation per persona
    for persona, (age_min, age_max) in PERSONA_AGE_RANGES.items():

        subset = df[df["persona"] == persona]

        assert (
            subset["age"]
            .between(age_min, age_max)
            .all()
        ), (
            f"Age validation failed for persona '{persona}'"
        )

    print("✅  All validation checks passed.\n")
# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def print_summary(df: pd.DataFrame) -> None:
    """Print a human-readable summary for quick sanity checking."""
    sep = "-" * 50

    print(sep)
    print(f"  Total customers      : {len(df):,}")
    print(sep)

    print("\n  Persona distribution:")
    for persona, count in df["persona"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {persona:<22} {count:>6,}  ({pct:.1f}%)")

    print("\n  Gender distribution:")
    for gender, count in df["gender"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {gender:<10} {count:>6,}  ({pct:.1f}%)")

    print("\n  Top 10 cities:")
    for city, count in df["city"].value_counts().head(10).items():
        pct = count / len(df) * 100
        print(f"    {city:<15} {count:>6,}  ({pct:.1f}%)")

    print("\n  Channel distribution:")
    for channel, count in df["preferred_channel"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {channel:<12} {count:>6,}  ({pct:.1f}%)")

    print("\n  Acquisition source distribution:")
    for source, count in df["source"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {source:<12} {count:>6,}  ({pct:.1f}%)")

    print("\n  Join-date range:")
    print(f"    Earliest : {df['join_date'].min()}")
    print(f"    Latest   : {df['join_date'].max()}")

    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    print("\n🚀  Aether CRM — Generating customers...\n")

    # Ensure the output directory exists before any work begins
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Generate
    df = generate_customers()

    # Validate
    validate(df)

    # Print summary
    print_summary(df)

    # Normalise join_date to a pandas Timestamp so the CSV format is
    # consistent (YYYY-MM-DD) regardless of the execution environment.
    df["join_date"] = pd.to_datetime(df["join_date"])

    # Export
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n✅  Exported {len(df):,} customers → {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()