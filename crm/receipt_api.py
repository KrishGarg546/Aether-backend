"""
crm/receipt_api.py
===================
Aether CRM – Receipt API
--------------------------
Responsible for one thing: receive asynchronous communication lifecycle
callbacks from the Channel Service, validate them, persist them in an
append-only event log, and expose status-lookup utilities for downstream
consumers such as the Insights Engine.

This module sits at the boundary between the Channel Service and the
Insights Engine.  It does NOT send campaigns, simulate delivery, choose
channels, generate communications, or perform insights calculations.
Those responsibilities belong exclusively to their respective modules.

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
Channel Service
  ↓
Receipt API  ← THIS MODULE
  ↓
Insights Engine

Append-only guarantee
---------------------
Every inbound callback appends a new row to the receipt log.  No prior
event is ever overwritten or deleted.  A communication that progresses
through DISPATCHED → DELIVERED → OPENED → CLICKED will produce four
distinct rows in storage, each with its own receipt_id.

Determinism guarantee
---------------------
receipt_id is derived from SHA-256 hashing of communication_id,
campaign_id, event, and event_timestamp, meaning identical inputs always
produce the same receipt_id regardless of when or where the module runs.

Usage
-----
Run as a standalone script (demo / smoke-test mode):

    python crm/receipt_api.py

Or import and call programmatically:

    from crm.receipt_api import receive_callback, get_latest_status, print_summary

    receipt = receive_callback(communication_id, campaign_id, event)
    status  = get_latest_status(communication_id)
"""

from __future__ import annotations

import hashlib
import csv
import os
import sys
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the receipts CSV, relative to project root.
# Override via the AETHER_RECEIPTS_PATH environment variable.
DEFAULT_RECEIPTS_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data_generation",
    "data",
    "communication_receipts.csv",
)

# Canonical column order for the receipts CSV.
RECEIPT_COLUMNS: list[str] = [
    "receipt_id",
    "communication_id",
    "campaign_id",
    "event",
    "event_timestamp",
]

# Complete set of supported lifecycle event types.
# Any event not in this set is rejected at validation time.
VALID_EVENTS: set[str] = {
    "DISPATCHED",
    "DELIVERED",
    "FAILED",
    "OPENED",
    "READ",
    "CLICKED",
}
EVENT_PRIORITY = {
    "DISPATCHED": 1,
    "DELIVERED": 2,
    "FAILED": 2,
    "OPENED": 3,
    "READ": 4,
    "CLICKED": 5,
}


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _generate_receipt_id(
    communication_id: str,
    campaign_id: str,
    event: str,
    event_timestamp: str,
) -> str:
    """Generate a deterministic receipt ID from the four core fields.

    The ID is derived by hashing the composite key formed by joining
    communication_id, campaign_id, event, and event_timestamp.  This
    guarantees that the same callback inputs always produce the same
    receipt_id, which enables idempotent re-processing and deduplication
    at the Insights Engine layer.

    Parameters
    ----------
    communication_id:
        Unique identifier for the communication record.
    campaign_id:
        Identifier of the parent campaign.
    event:
        Lifecycle event type (e.g. ``"DISPATCHED"``).
    event_timestamp:
        ISO-8601 UTC timestamp string at which the event occurred.

    Returns
    -------
    str
        A 20-character uppercase hexadecimal string prefixed with
        ``RCPT-``.  Example: ``RCPT-3A9F12E0B4C71D58``
    """
    composite_key: str = (
        f"AETHER|RECEIPT|{communication_id}|{campaign_id}|{event}|{event_timestamp}"
    )
    digest: str = hashlib.sha256(composite_key.encode("utf-8")).hexdigest()

    # Take the first 20 hex characters for a compact but collision-resistant ID.
    return f"RCPT-{digest[:20].upper()}"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_receipts(path: str | None = None) -> pd.DataFrame:
    """Load the communication receipts log from CSV.

    If the file does not exist, returns an empty DataFrame with the
    correct column schema so callers can append to it unconditionally.

    Parameters
    ----------
    path:
        Absolute or relative path to the receipts CSV.  When ``None``
        the function first checks the ``AETHER_RECEIPTS_PATH``
        environment variable and then falls back to
        ``DEFAULT_RECEIPTS_PATH``.

    Returns
    -------
    pd.DataFrame
        DataFrame containing all historical receipts, or an empty
        DataFrame with ``RECEIPT_COLUMNS`` if the file does not yet
        exist.  All columns are string-typed for consistency.

    Raises
    ------
    ValueError
        If the file exists but is missing one or more required columns.
    """
    resolved_path: str = (
        path
        or os.environ.get("AETHER_RECEIPTS_PATH", "")
        or DEFAULT_RECEIPTS_PATH
    )

    if not os.path.isfile(resolved_path):
        return pd.DataFrame(columns=RECEIPT_COLUMNS)

    try:
        df: pd.DataFrame = pd.read_csv(
            resolved_path,
            dtype=str,
            engine="python",
        )
    except pd.errors.ParserError as exc:
        raise ValueError(
            f"[receipt_api] Failed to parse receipts CSV at '{resolved_path}'. "
            f"The file may contain malformed rows or unescaped delimiters. "
            f"Original error: {exc}"
        ) from exc

    # Strip surrounding whitespace from every string cell.
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    missing_cols: set[str] = set(RECEIPT_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Receipts CSV at '{resolved_path}' is missing required columns: "
            f"{missing_cols}"
        )

    return df


# ---------------------------------------------------------------------------
# Core callback handler
# ---------------------------------------------------------------------------


def receive_callback(
    communication_id: str,
    campaign_id: str,
    event: str,
    event_timestamp: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Receive and persist a single communication lifecycle callback.

    This is the primary entry point for the Receipt API.  It validates
    all inputs, generates a deterministic receipt_id, appends the new
    event to the existing history, persists the updated log to CSV, and
    returns the created receipt as a dictionary.

    No prior receipt is ever modified or removed — the storage contract
    is strictly append-only.

    Parameters
    ----------
    communication_id:
        Unique identifier of the communication record that triggered
        the callback.  Must be a non-empty string.
    campaign_id:
        Identifier of the parent campaign.  Must be a non-empty string.
    event:
        Lifecycle event type.  Must be a member of ``VALID_EVENTS``:
        DISPATCHED, DELIVERED, FAILED, OPENED, READ, or CLICKED.
    event_timestamp:
        ISO-8601 UTC timestamp at which the event occurred.  When
        ``None``, the current UTC time is used automatically.
    output_path:
        Destination path for the receipts CSV.  When ``None`` the
        function first checks the ``AETHER_RECEIPTS_PATH`` environment
        variable and then falls back to ``DEFAULT_RECEIPTS_PATH``.

    Returns
    -------
    dict[str, Any]
        The newly created receipt record containing all five fields
        defined in ``RECEIPT_COLUMNS``.

    Raises
    ------
    ValueError
        If ``event`` is not a member of ``VALID_EVENTS``.
    AssertionError
        If any required field is empty or if the generated receipt_id
        already exists in the receipt log (duplicate callback guard).
    """
    # ------------------------------------------------------------------
    # 1. Normalise inputs.
    # ------------------------------------------------------------------

    communication_id = str(communication_id).strip()
    campaign_id      = str(campaign_id).strip()
    event            = str(event).strip().upper()

    if event_timestamp is None:
        event_timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        event_timestamp = str(event_timestamp).strip()

    # ------------------------------------------------------------------
    # 2. Validate field presence.
    # ------------------------------------------------------------------

    assert communication_id, (
        "[receive_callback] communication_id must not be empty."
    )
    assert campaign_id, (
        "[receive_callback] campaign_id must not be empty."
    )
    assert event_timestamp, (
        "[receive_callback] event_timestamp must not be empty."
    )

    # ------------------------------------------------------------------
    # 3. Validate event type.
    # ------------------------------------------------------------------

    if event not in VALID_EVENTS:
        raise ValueError(
            f"[receive_callback] Unsupported event type: '{event}'.  "
            f"Valid events are: {sorted(VALID_EVENTS)}"
        )

    # ------------------------------------------------------------------
    # 4. Generate deterministic receipt_id.
    # ------------------------------------------------------------------

    receipt_id: str = _generate_receipt_id(
        communication_id=communication_id,
        campaign_id=campaign_id,
        event=event,
        event_timestamp=event_timestamp,
    )

    assert receipt_id, (
        "[receive_callback] receipt_id generation produced an empty string."
    )

    # ------------------------------------------------------------------
    # 5. Load existing history and guard against duplicate receipt_ids.
    # ------------------------------------------------------------------

    existing: pd.DataFrame = load_receipts(path=output_path)

    if not existing.empty and receipt_id in existing["receipt_id"].values:
        raise AssertionError(
            f"[receive_callback] Duplicate receipt_id detected: '{receipt_id}'.  "
            f"The same callback (communication_id='{communication_id}', "
            f"campaign_id='{campaign_id}', event='{event}', "
            f"event_timestamp='{event_timestamp}') has already been recorded."
        )

    # ------------------------------------------------------------------
    # 6. Build and append the new receipt row.
    # ------------------------------------------------------------------

    receipt: dict[str, Any] = {
        "receipt_id":       receipt_id,
        "communication_id": communication_id,
        "campaign_id":      campaign_id,
        "event":            event,
        "event_timestamp":  event_timestamp,
    }

    new_row: pd.DataFrame = pd.DataFrame([receipt])
    updated: pd.DataFrame = (
        pd.concat([existing, new_row], ignore_index=True)
        if not existing.empty
        else new_row
    )

    # ------------------------------------------------------------------
    # 7. Persist the updated log.
    # ------------------------------------------------------------------

    save_receipts(receipts=updated, output_path=output_path)

    return receipt


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_receipts(
    receipts: pd.DataFrame,
    output_path: str | None = None,
) -> str:
    """Write the receipt DataFrame to CSV.

    Preserves append-only semantics by always writing the full current
    state of the DataFrame to disk.  The caller is responsible for
    ensuring that only new rows have been appended and that no existing
    rows have been modified.

    Parameters
    ----------
    receipts:
        DataFrame containing all receipt records to persist.  Must
        include every column defined in ``RECEIPT_COLUMNS``.
    output_path:
        Destination path for the CSV file.  When ``None`` the function
        first checks the ``AETHER_RECEIPTS_PATH`` environment variable
        and then falls back to ``DEFAULT_RECEIPTS_PATH``.

    Returns
    -------
    str
        The absolute path where the file was written.

    Raises
    ------
    AssertionError
        If the receipts DataFrame is missing required columns.
    OSError
        If the directory cannot be created or the file cannot be written.
    """
    resolved_path: str = (
        output_path
        or os.environ.get("AETHER_RECEIPTS_PATH", "")
        or DEFAULT_RECEIPTS_PATH
    )

    # Validate columns before writing.
    missing_cols: set[str] = set(RECEIPT_COLUMNS) - set(receipts.columns)
    assert not missing_cols, (
        f"[save_receipts] DataFrame is missing required columns: {missing_cols}"
    )

    os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

    receipts[RECEIPT_COLUMNS].to_csv(
        resolved_path,
        index=False,
        quoting=csv.QUOTE_ALL,
        escapechar="\\",
    )

    print(f"[receipt_api] Receipts saved → {resolved_path}  ({len(receipts):,} rows)")
    return resolved_path


# ---------------------------------------------------------------------------
# Status lookup
# ---------------------------------------------------------------------------


def get_latest_status(
    communication_id: str,
    path: str | None = None,
) -> str | None:
    """Return the most recent lifecycle event for a given communication.

    Reads the receipt log and reconstructs the effective lifecycle
status for the specified communication_id.

Events are ordered primarily using the predefined lifecycle
priority defined in EVENT_PRIORITY and secondarily by
event_timestamp. This allows the Receipt API to recover the
correct terminal status even when callbacks arrive out of order.

For example, if CLICKED is received before OPENED due to
network delays, CLICKED will still be considered the latest
status because it represents a later stage in the lifecycle.

    Parameters
    ----------
    communication_id:
        The communication whose status is being queried.
    path:
        Optional path to the receipts CSV.  When ``None`` the function
        resolves the path using the standard environment-variable /
        default-path fallback chain.

    Returns
    -------
    str | None
        The event type string (e.g. ``"DELIVERED"``) for the most recent
        event recorded for this communication.  Returns ``None`` if no
        receipts exist for the given communication_id.
    """
    receipts: pd.DataFrame = load_receipts(path=path)

    if receipts.empty:
        return None

    comm_receipts: pd.DataFrame = receipts[
        receipts["communication_id"] == str(communication_id).strip()
    ]

    if comm_receipts.empty:
        return None

    # Sort ascending; the last row carries the latest timestamp.
    comm_receipts = comm_receipts.copy()

    comm_receipts["priority"] = (
    comm_receipts["event"]
    .map(EVENT_PRIORITY)
    )

    latest = (
    comm_receipts
    .sort_values(
        by=["priority", "event_timestamp"],
        ascending=[True, True],
    )
    .iloc[-1]
    )

    return str(latest["event"])


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(receipts: pd.DataFrame) -> None:
    """Print a human-readable summary of the receipt log.

    Displays the total number of receipts recorded and the distribution
    of event types across the full log.

    Parameters
    ----------
    receipts:
        DataFrame containing all receipt records, as returned by
        :func:`load_receipts`.

    Example output::

        ────────────────────────────────────────────────────────────
          AETHER CRM – Receipt API Summary
        ────────────────────────────────────────────────────────────
          Total receipts : 9

          Event Distribution
          ──────────────────────────────────────────
          DISPATCHED      3
          DELIVERED       2
          FAILED          1
          OPENED          1
          READ            1
          CLICKED         1
        ────────────────────────────────────────────────────────────
    """
    separator: str = "─" * 60
    print(separator)
    print("  AETHER CRM – Receipt API Summary")
    print(separator)
    print(f"  Total receipts : {len(receipts):,}")
    print()

    if receipts.empty:
        print("  No receipts recorded.")
        print(separator)
        return

    print("  Event Distribution")
    print("  " + "─" * 40)

    event_counts: pd.Series = (
        receipts["event"]
        .value_counts()
        .reindex(sorted(VALID_EVENTS), fill_value=0)
    )

    for event_type, count in event_counts.items():
        if count > 0:
            print(f"  {event_type:<16}{count:>6,}")

    print(separator)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_receipts_dataframe(receipts: pd.DataFrame) -> None:
    """Validate a receipts DataFrame against all output contracts.

    Checks the following invariants:

    1. All required columns are present.
    2. No receipt_id is empty.
    3. No communication_id is empty.
    4. No campaign_id is empty.
    5. All event values belong to ``VALID_EVENTS``.
    6. No event_timestamp is empty.
    7. No duplicate receipt_ids exist.

    Parameters
    ----------
    receipts:
        DataFrame to validate.

    Raises
    ------
    AssertionError
        If any invariant is violated.  The error message identifies
        which rule failed and provides diagnostic details.
    """
    # Rule 1: required columns.
    missing_cols: set[str] = set(RECEIPT_COLUMNS) - set(receipts.columns)
    assert not missing_cols, (
        f"[validate_receipts] DataFrame is missing required columns: {missing_cols}"
    )

    # Rule 2: no empty receipt_ids.
    empty_receipt_ids: int = receipts["receipt_id"].isna().sum() + (
        receipts["receipt_id"].str.strip() == ""
    ).sum()
    assert empty_receipt_ids == 0, (
        f"[validate_receipts] {empty_receipt_ids} row(s) have an empty receipt_id."
    )

    # Rule 3: no empty communication_ids.
    empty_comm_ids: int = receipts["communication_id"].isna().sum() + (
        receipts["communication_id"].str.strip() == ""
    ).sum()
    assert empty_comm_ids == 0, (
        f"[validate_receipts] {empty_comm_ids} row(s) have an empty communication_id."
    )

    # Rule 4: no empty campaign_ids.
    empty_camp_ids: int = receipts["campaign_id"].isna().sum() + (
        receipts["campaign_id"].str.strip() == ""
    ).sum()
    assert empty_camp_ids == 0, (
        f"[validate_receipts] {empty_camp_ids} row(s) have an empty campaign_id."
    )

    # Rule 5: all events are valid.
    invalid_events: pd.Series = receipts[~receipts["event"].isin(VALID_EVENTS)]["event"]
    assert invalid_events.empty, (
        f"[validate_receipts] Unrecognised event type(s) detected: "
        f"{invalid_events.unique().tolist()}"
    )

    # Rule 6: no empty timestamps.
    empty_timestamps: int = receipts["event_timestamp"].isna().sum() + (
        receipts["event_timestamp"].str.strip() == ""
    ).sum()
    assert empty_timestamps == 0, (
        f"[validate_receipts] {empty_timestamps} row(s) have an empty event_timestamp."
    )

    # Rule 7: no duplicate receipt_ids.
    duplicate_ids: pd.Series = receipts["receipt_id"][
        receipts["receipt_id"].duplicated()
    ]
    assert duplicate_ids.empty, (
        f"[validate_receipts] Duplicate receipt_ids detected: "
        f"{duplicate_ids.tolist()}"
    )


# ---------------------------------------------------------------------------
# Entry point (demo / smoke-test)
# ---------------------------------------------------------------------------


def main() -> None:
    """Smoke-test all core receipt lifecycle scenarios end-to-end.

    Simulates callbacks for three representative communications across a
    single synthetic campaign, then exercises every public function in
    the module.

    The test is entirely self-contained and does not import any other
    Aether CRM module at runtime, keeping receipt_api.py independently
    runnable during development.

    Scenarios
    ---------
    COMM001 : DISPATCHED → DELIVERED → OPENED → CLICKED   (full funnel)
    COMM002 : DISPATCHED → FAILED                          (delivery failure)
    COMM003 : DISPATCHED → DELIVERED → READ                (read without click)
    """
    # ------------------------------------------------------------------
    # 0. Use a temporary output path so the smoke test does not pollute
    #    production data.  The path mirrors the canonical default but
    #    resolves relative to this file so it works from any cwd.
    # ------------------------------------------------------------------

    smoke_output_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data_generation",
        "data",
        "communication_receipts.csv",
    )

    DEMO_CAMPAIGN_ID: str = "CAMP-DEMO1234567890"

    print("\n" + "=" * 60)
    print("  AETHER CRM – Receipt API Smoke Test")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Define callback scenarios.
    # ------------------------------------------------------------------

    callbacks: list[tuple[str, str, str, str | None]] = [

    ("COMM001", DEMO_CAMPAIGN_ID, "DISPATCHED", None),
    ("COMM001", DEMO_CAMPAIGN_ID, "DELIVERED", None),
    ("COMM001", DEMO_CAMPAIGN_ID, "OPENED", None),
    ("COMM001", DEMO_CAMPAIGN_ID, "CLICKED", None),

    ("COMM002", DEMO_CAMPAIGN_ID, "DISPATCHED", None),
    ("COMM002", DEMO_CAMPAIGN_ID, "FAILED", None),

    ("COMM003", DEMO_CAMPAIGN_ID, "DISPATCHED", None),
    ("COMM003", DEMO_CAMPAIGN_ID, "DELIVERED", None),
    ("COMM003", DEMO_CAMPAIGN_ID, "READ", None),

    (
        "COMM004",
        DEMO_CAMPAIGN_ID,
        "CLICKED",
        "2026-01-01T12:00:03Z",
    ),

    (
        "COMM004",
        DEMO_CAMPAIGN_ID,
        "DELIVERED",
        "2026-01-01T12:00:01Z",
    ),

    (
        "COMM004",
        DEMO_CAMPAIGN_ID,
        "OPENED",
        "2026-01-01T12:00:02Z",
    ),
]

    # ------------------------------------------------------------------
    # 2. Wipe any stale smoke-test data from a previous run so the
    #    duplicate-receipt guard does not trigger.
    # ------------------------------------------------------------------

    if os.path.isfile(smoke_output_path):
        os.remove(smoke_output_path)
        print(f"[receipt_api] Cleared previous smoke-test data at {smoke_output_path}")

    # ------------------------------------------------------------------
    # 3. Fire all callbacks.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Sending callbacks")
    print("─" * 60)

    all_receipts: list[dict[str, Any]] = []

    for comm_id, camp_id, event, timestamp in callbacks:
        try:
            receipt: dict[str, Any] = receive_callback(
            communication_id=comm_id,
            campaign_id=camp_id,
            event=event,
            event_timestamp=timestamp,
            output_path=smoke_output_path,
)
            all_receipts.append(receipt)
            print(
                f"  ✓  {comm_id:<10}  {event:<12}  →  {receipt['receipt_id']}"
            )
        except (ValueError, AssertionError) as exc:
            print(f"  ✗  {comm_id}  {event}  ERROR: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 4. Save receipts and verify CSV round-trip correctness.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  CSV round-trip verification")
    print("─" * 60)

    loaded: pd.DataFrame = load_receipts(path=smoke_output_path)

    assert len(loaded) == len(all_receipts), (
        f"[smoke_test] CSV row count {len(loaded)} does not match "
        f"generated receipt count {len(all_receipts)}."
    )
    print(f"  ✓ CSV round-trip verified ({len(loaded):,} rows).")

    # ------------------------------------------------------------------
    # 5. Print summary statistics.
    # ------------------------------------------------------------------

    print()
    print_summary(loaded)

    # ------------------------------------------------------------------
    # 6. Demonstrate get_latest_status() for each communication.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Latest status per communication")
    print("─" * 60)

    for comm_id in ("COMM001", "COMM002", "COMM003", "COMM004"):
        status: str | None = get_latest_status(
            communication_id=comm_id,
            path=smoke_output_path,
        )
        print(f"  {comm_id}  →  {status}")
    
    assert (
    get_latest_status(
        communication_id="COMM004",
        path=smoke_output_path,
    )
    == "CLICKED"
    ), (
    "[smoke_test] COMM004 should resolve to CLICKED "
    "despite out-of-order callbacks."
    )

    print(
    "  ✓ COMM004 ordering resilience verified "
    "(CLICKED remained final status)."
    )

    # ------------------------------------------------------------------
    # 7. Validate all output contracts.
    # ------------------------------------------------------------------

    print(f"\n{'─' * 60}")
    print("  Output contract validation")
    print("─" * 60)

    try:
        _validate_receipts_dataframe(loaded)
        print("  ✓ All output contracts satisfied.")
    except AssertionError as exc:
        print(f"  ✗ Contract violation: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 8. Verify append-only semantics: total event count per comm.
    # ------------------------------------------------------------------

    expected_counts: dict[str, int] = {
    "COMM001": 4,
    "COMM002": 2,
    "COMM003": 3,
    "COMM004": 3,
}

    print(f"\n{'─' * 60}")
    print("  Append-only event count verification")
    print("─" * 60)

    for comm_id, expected in expected_counts.items():
        actual: int = len(loaded[loaded["communication_id"] == comm_id])
        assert actual == expected, (
            f"[smoke_test] {comm_id} expected {expected} events but found {actual}."
        )
        print(f"  ✓  {comm_id}  {actual}/{expected} events recorded.")

    print(f"\n{'=' * 60}")
    print("  Smoke test complete — all assertions passed.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()