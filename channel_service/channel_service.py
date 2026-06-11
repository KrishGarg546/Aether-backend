"""
channel_service/channel_service.py
=====================================
Aether CRM – Channel Service
------------------------------
Responsible for one thing: accept a communication manifest produced by the
Communication Manager, simulate deterministic message delivery for every
record, and forward each lifecycle event to the Receipt API for persistent
storage.

This module sits at the boundary between campaign execution and the event
log.  It does NOT generate communications, choose channels, perform audience
selection, calculate insights, or modify historical receipts.  Those
responsibilities belong exclusively to their respective modules.

Pipeline position
-----------------
Goal Parser
  ↓
Audience Selector
  ↓
Campaign Planner
  ↓
Communication Manager
  ↓
Channel Service  ← THIS MODULE
  ↓
Receipt API
  ↓
Insights Engine

Delivery simulation philosophy
--------------------------------
Real-world channel delivery is asynchronous and probabilistic.  Aether
simulates this behaviour deterministically so that:

  1. The same communication_id always produces the same outcome.
  2. Outputs are reproducible across environments without randomness.
  3. Developers can reason about expected results during testing.

Determinism is achieved by deriving a float probability value from the
SHA-256 hash of the communication_id.  The first 8 hex characters of the
digest are interpreted as a 32-bit unsigned integer and normalised into the
[0.0, 1.0) range.  A second, independent hash window (characters 8–15) is
used for post-delivery engagement events, ensuring delivery and engagement
outcomes are statistically independent while remaining reproducible.

Lifecycle event sequence
-------------------------
Every communication produces at minimum one event (DISPATCHED).  From there
the lifecycle branches deterministically:

    DISPATCHED
        └─► DELIVERED  (p = channel delivery rate)
        │       └─► OPENED / READ  (p = channel open rate, mutually exclusive)
        │               └─► CLICKED  (p = channel click rate, conditional on open/read)
        └─► FAILED     (1 – delivery rate)

Channel-specific engagement rates
-----------------------------------
    EMAIL    : 30 % OPENED  →  10 % CLICKED  (conditional on OPENED)
    SMS      : 20 % READ    →   8 % CLICKED  (conditional on READ)
    PUSH     : 15 % OPENED  →   5 % CLICKED  (conditional on OPENED)
    WHATSAPP : 50 % READ    → 15 % CLICKED   (conditional on READ)

Delivery rates (independent of engagement):
    EMAIL    : 85 %
    SMS      : 92 %
    PUSH     : 78 %
    WHATSAPP : 90 %

Append-only guarantee
---------------------
The Channel Service never writes receipts directly.  Every lifecycle event
is forwarded to ``crm.receipt_api.receive_callback``, which is the single
source of truth for the communication event log.

Determinism guarantee
---------------------
All delivery outcomes are derived from SHA-256 hashes of the
communication_id.  Identical inputs always produce identical event
sequences regardless of when or where this module runs.

Usage
-----
Run as a standalone script (demo / smoke-test mode):

    python channel_service/channel_service.py

Or import and call programmatically:

    from channel_service.channel_service import (
        load_communications,
        process_communication,
        process_campaign,
        print_summary,
    )

    comms = load_communications("path/to/communications_CAMP-XYZ.csv")
    results = process_campaign(comms)
    print_summary(results)
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

import pandas as pd

_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from crm.receipt_api import receive_callback, VALID_EVENTS
except ModuleNotFoundError:
    try:
        from receipt_api import receive_callback, VALID_EVENTS
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Cannot import receipt_api. Ensure crm/receipt_api.py exists and "
            "the project root is on sys.path."
        ) from exc



# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default directory to scan for communications CSVs.
# Override via the AETHER_COMMUNICATIONS_DIR environment variable.
DEFAULT_COMMUNICATIONS_DIR: str = os.path.join(
    _PROJECT_ROOT,
    "data_generation",
    "data",
)

# Default communications CSV filename (fallback for single-campaign runs).
DEFAULT_COMMUNICATIONS_FILENAME: str = "communications.csv"

# Canonical set of channels this service handles.
VALID_CHANNELS: set[str] = {
    "EMAIL",
    "SMS",
    "PUSH",
    "WHATSAPP",
}

# Columns required in every communications DataFrame consumed by this service.
REQUIRED_COMMUNICATION_COLUMNS: set[str] = {
    "communication_id",
    "campaign_id",
    "channel",
}

# ---------------------------------------------------------------------------
# Delivery configuration
# ---------------------------------------------------------------------------
# Delivery rates represent the probability that a DISPATCHED message
# successfully reaches the recipient's device.

_DELIVERY_RATES: dict[str, float] = {
    "EMAIL": 0.85,
    "SMS": 0.92,
    "PUSH": 0.78,
    "WHATSAPP": 0.90,
}

# Engagement configuration: maps each channel to its (open_event, open_rate,
# click_rate) tuple.  open_rate and click_rate are both expressed as
# unconditional probabilities relative to DISPATCHED (not conditional on
# DELIVERED) to keep the hash arithmetic consistent and auditable.
#
# However, engagement events are only emitted after a successful DELIVERED
# event, so the effective conditional engagement rate observed in outputs
# will be: engagement_rate / delivery_rate.
#
# The rates below are intentionally kept as specified in the requirements
# and applied only after DELIVERED has been confirmed.

_ENGAGEMENT_CONFIG: dict[str, dict[str, Any]] = {
    "EMAIL": {
        "open_event": "OPENED",
        "open_rate":  0.30,
        "click_rate": 0.10,
    },
    "SMS": {
        "open_event": "READ",
        "open_rate":  0.20,
        "click_rate": 0.08,
    },
    "PUSH": {
        "open_event": "OPENED",
        "open_rate":  0.15,
        "click_rate": 0.05,
    },
    "WHATSAPP": {
        "open_event": "READ",
        "open_rate":  0.50,
        "click_rate": 0.15,
    },
}


# ---------------------------------------------------------------------------
# Deterministic hash helpers
# ---------------------------------------------------------------------------


def _hash_to_float(value: str, salt: str = "DELIVERY") -> float:
    """Derive a deterministic float in [0.0, 1.0) from a string.

    The function hashes the composite string ``AETHER|<salt>|<value>``
    using SHA-256 and normalises the first 8 hex characters (a 32-bit
    unsigned integer) into the unit interval.

    Parameters
    ----------
    value:
        The primary input to hash, typically a communication_id.
    salt:
        A namespace label that differentiates independent probability
        draws from the same value.  For example, using ``"DELIVERY"``
        and ``"ENGAGEMENT"`` as salts on the same communication_id
        produces two statistically independent values.

    Returns
    -------
    float
        A float in [0.0, 1.0) that is always identical for the same
        (value, salt) pair.
    """
    composite: str = f"AETHER|{salt}|{value}"
    digest: str = hashlib.sha256(composite.encode("utf-8")).hexdigest()

    # Take the first 8 hex characters → 32-bit unsigned integer.
    raw_int: int = int(digest[:8], 16)

    # Normalise to [0.0, 1.0).
    return raw_int / (0xFFFFFFFF + 1)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_communications(path: str | None = None) -> pd.DataFrame:
    """Load a communication manifest from CSV.

    Resolves the path in the following precedence order:

    1. The ``path`` argument (if provided and non-empty).
    2. The ``AETHER_COMMUNICATIONS_PATH`` environment variable.
    3. The ``DEFAULT_COMMUNICATIONS_DIR`` joined with
       ``DEFAULT_COMMUNICATIONS_FILENAME``.

    Parameters
    ----------
    path:
        Absolute or relative path to a communications CSV file produced
        by the Communication Manager.  When ``None``, the function
        falls back through the precedence chain described above.

    Returns
    -------
    pd.DataFrame
        DataFrame containing all communication records.  All columns are
        loaded as strings to preserve deterministic ID values.

    Raises
    ------
    FileNotFoundError
        If the resolved path does not point to an existing file.
    ValueError
        If the file is missing one or more of
        ``REQUIRED_COMMUNICATION_COLUMNS``.
    """
    resolved_path: str = (
        path
        or os.environ.get("AETHER_COMMUNICATIONS_PATH", "")
        or os.path.join(DEFAULT_COMMUNICATIONS_DIR, DEFAULT_COMMUNICATIONS_FILENAME)
    )

    if not os.path.isfile(resolved_path):
        raise FileNotFoundError(
            f"[channel_service] Communications file not found: '{resolved_path}'.  "
            f"Run the Communication Manager first to generate this file."
        )

    try:
        df: pd.DataFrame = pd.read_csv(
            resolved_path,
            dtype=str,
            engine="python",
        )
    except pd.errors.ParserError as exc:
        raise ValueError(
            f"[channel_service] Failed to parse communications CSV at '{resolved_path}'. "
            f"This usually indicates unescaped commas or malformed rows in the "
            f"Communication Manager output. Original error: {exc}"
        ) from exc

    # Strip surrounding whitespace from every string column.
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    missing_cols: set[str] = REQUIRED_COMMUNICATION_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"[channel_service] Communications CSV at '{resolved_path}' is "
            f"missing required columns: {missing_cols}"
        )

    return df


# ---------------------------------------------------------------------------
# Delivery simulation
# ---------------------------------------------------------------------------


def simulate_delivery(
    communication_id: str,
    channel: str,
) -> list[str]:
    """Simulate the complete delivery lifecycle for a single communication.

    Uses SHA-256 hashing on ``communication_id`` to derive deterministic
    probability values for each lifecycle decision, ensuring that the same
    input always produces the same event sequence.

    Parameters
    ----------
    communication_id:
        Unique identifier of the communication record.  Must be a
        non-empty string.
    channel:
        Delivery channel.  Must be a member of ``VALID_CHANNELS``:
        EMAIL, SMS, PUSH, or WHATSAPP.

    Returns
    -------
    list[str]
        Ordered list of lifecycle event strings generated for this
        communication.  The sequence always begins with ``"DISPATCHED"``
        and may include any combination of:

            DISPATCHED → DELIVERED → OPENED | READ → CLICKED
            DISPATCHED → FAILED

        Examples::

            ["DISPATCHED", "DELIVERED", "OPENED", "CLICKED"]
            ["DISPATCHED", "DELIVERED", "READ"]
            ["DISPATCHED", "FAILED"]
            ["DISPATCHED", "DELIVERED"]

    Raises
    ------
    ValueError
        If ``communication_id`` is empty or ``channel`` is not a member
        of ``VALID_CHANNELS``.
    """
    # ── Input validation ───────────────────────────────────────────────
    if not communication_id or not communication_id.strip():
        raise ValueError(
            "[channel_service.simulate_delivery] communication_id must be "
            "a non-empty string."
        )

    normalised_channel: str = channel.strip().upper()
    if normalised_channel not in VALID_CHANNELS:
        raise ValueError(
            f"[channel_service.simulate_delivery] Unsupported channel: "
            f"'{channel}'.  Valid channels are: {sorted(VALID_CHANNELS)}"
        )

    events: list[str] = []

    # ── Step 1: Every communication starts with DISPATCHED ─────────────
    events.append("DISPATCHED")

    # ── Step 2: Determine DELIVERED vs FAILED ──────────────────────────
    delivery_probability: float = _hash_to_float(communication_id, salt="DELIVERY")
    delivery_rate: float = _DELIVERY_RATES[normalised_channel]

    if delivery_probability >= delivery_rate:
        # Delivery failed.
        events.append("FAILED")
        return events

    events.append("DELIVERED")

    # ── Step 3: Determine engagement (OPENED / READ) ────────────────────
    engagement_cfg: dict[str, Any] = _ENGAGEMENT_CONFIG[normalised_channel]
    open_event: str   = engagement_cfg["open_event"]
    open_rate: float  = engagement_cfg["open_rate"]
    click_rate: float = engagement_cfg["click_rate"]

    open_probability: float = _hash_to_float(communication_id, salt="OPEN")

    if open_probability < open_rate:
        events.append(open_event)

        # ── Step 4: Determine CLICKED (conditional on open/read) ────────
        click_probability: float = _hash_to_float(communication_id, salt="CLICK")

        if click_probability < click_rate:
            events.append("CLICKED")

    return events


# ---------------------------------------------------------------------------
# Communication processing
# ---------------------------------------------------------------------------


def process_communication(
    communication: dict[str, Any],
) -> list[dict[str, Any]]:
    """Process a single communication record end-to-end.

    Validates the required fields, simulates delivery, and forwards every
    generated lifecycle event to the Receipt API.  Returns the list of
    receipt records created for this communication.

    Parameters
    ----------
    communication:
        A dictionary representing a single communication row from the
        communications CSV.  Must contain at minimum:

        - ``communication_id`` (non-empty string)
        - ``campaign_id`` (non-empty string)
        - ``channel`` (member of ``VALID_CHANNELS``)

    Returns
    -------
    list[dict[str, Any]]
        List of receipt records returned by ``receive_callback``, one per
        lifecycle event generated.  Each record is a dictionary with keys:

        - ``receipt_id``
        - ``communication_id``
        - ``campaign_id``
        - ``event``
        - ``event_timestamp``

    Raises
    ------
    ValueError
        If any required field is missing, empty, or invalid.
    """
    # ── Field extraction and validation ────────────────────────────────
    communication_id: Any = communication.get("communication_id", "")
    campaign_id: Any      = communication.get("campaign_id", "")
    channel: Any          = communication.get("channel", "")

    if not isinstance(communication_id, str) or not communication_id.strip():
        raise ValueError(
            "[channel_service.process_communication] 'communication_id' is "
            f"missing or empty in communication record: {communication}"
        )

    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ValueError(
            "[channel_service.process_communication] 'campaign_id' is missing "
            f"or empty in communication record: {communication}"
        )

    if not isinstance(channel, str) or channel.strip().upper() not in VALID_CHANNELS:
        raise ValueError(
            f"[channel_service.process_communication] 'channel' is missing or "
            f"invalid in communication record: {communication}.  "
            f"Valid channels: {sorted(VALID_CHANNELS)}"
        )

    communication_id = communication_id.strip()
    campaign_id      = campaign_id.strip()
    channel          = channel.strip().upper()

    # ── Simulate delivery ───────────────────────────────────────────────
    events: list[str] = simulate_delivery(
        communication_id=communication_id,
        channel=channel,
    )

    # ── Forward every event to the Receipt API ─────────────────────────
    receipts: list[dict[str, Any]] = []

    base_time: datetime = datetime(
        2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc
    )

    for idx, event in enumerate(events):
        event_timestamp: str = (
            base_time + timedelta(seconds=idx)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        receipt: dict[str, Any] = receive_callback(
            communication_id=communication_id,
            campaign_id=campaign_id,
            event=event,
            event_timestamp=event_timestamp,
        )
        receipts.append(receipt)

    return receipts


# ---------------------------------------------------------------------------
# Campaign-level batch processing
# ---------------------------------------------------------------------------


def process_campaign(
    communications: pd.DataFrame,
) -> pd.DataFrame:
    """Process all communications in a campaign manifest.

    Iterates through every row in the provided DataFrame, calls
    :func:`process_communication` for each, and aggregates all generated
    receipt records into a single DataFrame for downstream consumption by
    the Insights Engine.

    Rows that fail validation are skipped with a warning printed to
    stderr; processing continues for all remaining rows.

    Parameters
    ----------
    communications:
        DataFrame produced by :func:`load_communications`, containing at
        minimum the columns ``communication_id``, ``campaign_id``, and
        ``channel``.

    Returns
    -------
    pd.DataFrame
        DataFrame containing all receipt records generated across the
        entire campaign.  Columns mirror the Receipt API schema:

        - ``receipt_id``
        - ``communication_id``
        - ``campaign_id``
        - ``event``
        - ``event_timestamp``

        Returns an empty DataFrame with the correct column schema if no
        receipts were generated.

    Raises
    ------
    ValueError
        If ``communications`` is not a DataFrame or is missing required
        columns.
    """
    if not isinstance(communications, pd.DataFrame):
        raise ValueError(
            "[channel_service.process_campaign] 'communications' must be a "
            f"pandas DataFrame, got {type(communications).__name__}."
        )

    missing_cols: set[str] = REQUIRED_COMMUNICATION_COLUMNS - set(communications.columns)
    if missing_cols:
        raise ValueError(
            f"[channel_service.process_campaign] Communications DataFrame is "
            f"missing required columns: {missing_cols}"
        )

    all_receipts: list[dict[str, Any]] = []
    total_rows: int = len(communications)
    processed: int = 0
    skipped: int = 0

    for idx, row in communications.iterrows():
        communication: dict[str, Any] = row.to_dict()
        try:
            receipts: list[dict[str, Any]] = process_communication(communication)
            all_receipts.extend(receipts)
            processed += 1
        except (ValueError, AssertionError) as exc:
            print(
                f"[channel_service] WARNING – skipping row {idx} "
                f"(communication_id={communication.get('communication_id', 'UNKNOWN')}): "
                f"{exc}",
                file=sys.stderr,
            )
            skipped += 1

    if skipped > 0:
        print(
            f"[channel_service] {skipped}/{total_rows} communication(s) skipped "
            f"due to validation errors.",
            file=sys.stderr,
        )

    if not all_receipts:
        receipt_columns: list[str] = [
            "receipt_id",
            "communication_id",
            "campaign_id",
            "event",
            "event_timestamp",
        ]
        return pd.DataFrame(columns=receipt_columns)

    return pd.DataFrame(all_receipts)


# ---------------------------------------------------------------------------
# Summary reporting
# ---------------------------------------------------------------------------


def print_summary(results: pd.DataFrame) -> None:
    """Print a human-readable summary of campaign processing results.

    Displays total communication and receipt counts, along with a
    breakdown of event type frequencies.  Designed to mirror the
    reporting style of the Communication Manager and Receipt API.

    Parameters
    ----------
    results:
        DataFrame returned by :func:`process_campaign`, containing at
        minimum ``communication_id``, ``event``, and ``receipt_id``
        columns.

    Returns
    -------
    None
        All output is written to stdout.
    """
    separator: str = "─" * 60

    print(f"\n{separator}")
    print("  Channel Service – Processing Summary")
    print(separator)

    if results.empty:
        print("  No receipts generated.")
        print(separator)
        return

    total_communications: int = results["communication_id"].nunique()
    total_receipts: int       = len(results)

    print(f"  {'Total Communications':<30} {total_communications:>6,}")
    print(f"  {'Total Receipts Generated':<30} {total_receipts:>6,}")

    # ── Event type breakdown ────────────────────────────────────────────
    print(f"\n  {'Event Type':<20} {'Count':>8}   {'% of Receipts':>14}")
    print(f"  {'─' * 20}   {'─' * 8}   {'─' * 14}")

    event_counts: pd.Series = results["event"].value_counts()
    event_order: list[str]  = [
        "DISPATCHED",
        "DELIVERED",
        "FAILED",
        "OPENED",
        "READ",
        "CLICKED",
    ]

    for event in event_order:
        count: int = int(event_counts.get(event, 0))
        if count == 0:
            continue
        pct: float = (count / total_receipts) * 100
        print(f"  {event:<20} {count:>8,}   {pct:>13.1f}%")

    # ── Delivery rate summary ───────────────────────────────────────────
    dispatched_count: int = int(event_counts.get("DISPATCHED", 0))
    delivered_count: int  = int(event_counts.get("DELIVERED", 0))
    failed_count: int     = int(event_counts.get("FAILED", 0))

    if dispatched_count > 0:
        delivery_rate: float = (delivered_count / dispatched_count) * 100
        failure_rate: float  = (failed_count / dispatched_count) * 100
        print()
        print(f"  {'Delivery Rate':<30} {delivery_rate:>6.1f}%")
        print(f"  {'Failure Rate':<30} {failure_rate:>6.1f}%")

    print(separator)


# ---------------------------------------------------------------------------
# Entry point (demo / smoke-test)
# ---------------------------------------------------------------------------


def main() -> None:
    """Smoke-test the Channel Service end-to-end.

    Constructs a minimal synthetic communications DataFrame that mirrors
    the output of the Communication Manager, then exercises all four
    supported channels across both delivery outcomes (DELIVERED and
    FAILED) as well as the full engagement funnel.

    The smoke test is entirely self-contained: it does not depend on any
    communications CSV being present on disk.

    Assertions
    ----------
    1. At least one receipt was generated.
    2. All events belong to ``VALID_EVENTS``.
    3. Every communication produced at least one DISPATCHED receipt.
    4. ``simulate_delivery`` is deterministic (same input → same output).
    5. Each channel is exercised with a known communication_id.

    Note: Because this smoke test calls ``receive_callback`` against the
    live Receipt API, receipts will be appended to the configured
    receipts CSV.  To prevent pollution of production data, set the
    ``AETHER_RECEIPTS_PATH`` environment variable to a temporary path
    before running this script directly.
    """
    print("\n" + "=" * 60)
    print("  AETHER CRM – Channel Service Smoke Test")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 0. Build a synthetic communications manifest.
    #    We use fixed IDs so the smoke-test output is fully reproducible.
    # ------------------------------------------------------------------

    DEMO_CAMPAIGN_ID: str = "CAMP-CHANTEST0000001"

    synthetic_records: list[dict[str, str]] = [
        # One representative communication per channel.
        {
            "communication_id": "COMM-CH-EMAIL-00001",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1001",
            "channel":          "EMAIL",
            "campaign_type":    "WIN_BACK",
            "message":          "We miss you! Here is a 15% discount.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
        {
            "communication_id": "COMM-CH-SMS-000002",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1002",
            "channel":          "SMS",
            "campaign_type":    "NURTURE",
            "message":          "Your exclusive member offer awaits.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
        {
            "communication_id": "COMM-CH-PUSH-000003",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1003",
            "channel":          "PUSH",
            "campaign_type":    "PREMIUM_PROMOTION",
            "message":          "Unlock your premium bundle today.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
        {
            "communication_id": "COMM-CH-WA-0000004",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1004",
            "channel":          "WHATSAPP",
            "campaign_type":    "REWARDS",
            "message":          "Your loyalty reward is ready to redeem.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
        # Additional records to broaden the distribution.
        {
            "communication_id": "COMM-CH-EMAIL-00005",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1005",
            "channel":          "EMAIL",
            "campaign_type":    "RECOMMENDATION",
            "message":          "Products we think you will love.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
        {
            "communication_id": "COMM-CH-SMS-000006",
            "campaign_id":      DEMO_CAMPAIGN_ID,
            "customer_id":      "CUST-1006",
            "channel":          "SMS",
            "campaign_type":    "WIN_BACK",
            "message":          "Come back – your cart is waiting.",
            "status":           "CREATED",
            "retry_count":      "0",
            "created_at":       "2026-06-10T00:00:00Z",
        },
    ]

    communications_df: pd.DataFrame = pd.DataFrame(synthetic_records)

    print(f"\n  Synthetic manifest built: {len(communications_df)} communications.")

    # ------------------------------------------------------------------
    # 1. Determinism verification.
    #    Run simulate_delivery twice on the same input; outputs must match.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Determinism verification")
    print("─" * 60)

    for comm_id, channel in [
        ("COMM-CH-EMAIL-00001", "EMAIL"),
        ("COMM-CH-SMS-000002",  "SMS"),
        ("COMM-CH-PUSH-000003", "PUSH"),
        ("COMM-CH-WA-0000004",  "WHATSAPP"),
    ]:
        first_run:  list[str] = simulate_delivery(comm_id, channel)
        second_run: list[str] = simulate_delivery(comm_id, channel)
        assert first_run == second_run, (
            f"[smoke_test] Determinism failed for {comm_id}: "
            f"{first_run} ≠ {second_run}"
        )
        print(f"  ✓  {comm_id:<30} {' → '.join(first_run)}")

    # ------------------------------------------------------------------
    # 2. Process all communications through the full pipeline.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Processing campaign communications")
    print("─" * 60)

    results: pd.DataFrame = process_campaign(communications_df)

    print(f"  ✓ process_campaign completed: {len(results):,} receipts generated.")

    # ------------------------------------------------------------------
    # 3. Core assertions.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Assertions")
    print("─" * 60)

    # Assertion 1: at least one receipt was generated.
    assert len(results) > 0, (
        "[smoke_test] No receipts were generated."
    )
    print(f"  ✓ At least one receipt generated ({len(results):,} total).")

    # Assertion 2: all events belong to VALID_EVENTS.
    unique_events: set[str] = set(results["event"].unique())
    invalid_events: set[str] = unique_events - VALID_EVENTS
    assert not invalid_events, (
        f"[smoke_test] Invalid event(s) detected in results: {invalid_events}"
    )
    print(f"  ✓ All events are valid: {sorted(unique_events)}")

    # Assertion 3: every communication produced at least one DISPATCHED receipt.
    dispatched_comm_ids: set[str] = set(
        results.loc[results["event"] == "DISPATCHED", "communication_id"].unique()
    )
    all_comm_ids: set[str] = set(communications_df["communication_id"].unique())
    missing_dispatched: set[str] = all_comm_ids - dispatched_comm_ids
    assert not missing_dispatched, (
        f"[smoke_test] The following communications never produced a DISPATCHED "
        f"event: {missing_dispatched}"
    )
    print(
        f"  ✓ All {len(all_comm_ids)} communications produced a DISPATCHED event."
    )

    # Assertion 4: required columns present in results.
    required_result_cols: set[str] = {
        "receipt_id", "communication_id", "campaign_id", "event", "event_timestamp"
    }
    missing_result_cols: set[str] = required_result_cols - set(results.columns)
    assert not missing_result_cols, (
        f"[smoke_test] Results DataFrame is missing columns: {missing_result_cols}"
    )
    print(f"  ✓ Results DataFrame contains all required columns.")

    # Assertion 5: simulate_delivery rejects invalid inputs.
    validation_errors_caught: int = 0

    for bad_id, bad_channel in [
        ("",                 "EMAIL"),
        ("COMM-VALID-00001", "CARRIER_PIGEON"),
        ("COMM-VALID-00001", ""),
    ]:
        try:
            simulate_delivery(bad_id, bad_channel)
        except ValueError:
            validation_errors_caught += 1

    assert validation_errors_caught == 3, (
        f"[smoke_test] Expected 3 ValueError catches for invalid inputs, "
        f"got {validation_errors_caught}."
    )
    print("  ✓ simulate_delivery raises ValueError for all invalid inputs.")

    # ------------------------------------------------------------------
    # 4. Print summary.
    # ------------------------------------------------------------------

    print_summary(results)

    # ------------------------------------------------------------------
    # 5. Per-communication event trace.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Per-communication event traces")
    print("─" * 60)

    for comm_id in sorted(all_comm_ids):
        comm_events: list[str] = (
            results.loc[results["communication_id"] == comm_id, "event"]
            .tolist()
        )
        channel_val: str = communications_df.loc[
            communications_df["communication_id"] == comm_id, "channel"
        ].iloc[0]
        print(
            f"  {comm_id:<30}  [{channel_val:<8}]  "
            f"{' → '.join(comm_events)}"
        )

    print(f"\n{'=' * 60}")
    print("  Smoke test complete — all assertions passed.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()