"""
order_calculator.py — Coverage threshold → units-to-order logic.

Formula
-------
  units_per_state = ROUNDUP(account_count × coverage_threshold)
  total_units     = sum(units_per_state)
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from query_engine import count_by_state


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_order(
    df: pd.DataFrame,
    item: str,
    threshold: float,
) -> dict:
    """
    Calculate units to order for `item` at the given `threshold`.

    Parameters
    ----------
    df        : Filtered DataFrame of qualifying accounts.
    item      : POS item name (for display only; ordering logic is item-agnostic).
    threshold : Coverage fraction, e.g. 0.5 = 50 %.

    Returns
    -------
    dict with keys:
        item          : str
        threshold     : float
        threshold_pct : str            (e.g. "50%")
        total_accounts: int
        total_units   : int
        by_state      : pd.DataFrame  — [STATE_CD, account_count, units_to_order]
        summary_text  : str           — plain-English result paragraph
    """
    threshold = _clamp(threshold, 0.0, 1.0)

    state_counts = count_by_state(df)

    state_counts["units_to_order"] = state_counts["account_count"].apply(
        lambda n: _roundup(n * threshold)
    )

    total_accounts = int(state_counts["account_count"].sum())
    total_units    = int(state_counts["units_to_order"].sum())

    summary_text = _build_summary(
        item=item,
        threshold=threshold,
        total_accounts=total_accounts,
        total_units=total_units,
        by_state=state_counts,
    )

    return {
        "item":           item,
        "threshold":      threshold,
        "threshold_pct":  f"{round(threshold * 100):g}%",
        "total_accounts": total_accounts,
        "total_units":    total_units,
        "by_state":       state_counts,
        "summary_text":   summary_text,
    }


def roundup_units(account_count: int, threshold: float) -> int:
    """
    Compute units for a single state/segment.

    >>> roundup_units(7, 0.5)
    4
    >>> roundup_units(10, 0.5)
    5
    """
    return _roundup(account_count * threshold)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _roundup(value: float) -> int:
    """Round a float up to the nearest integer (ceiling)."""
    return math.ceil(value)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _build_summary(
    item: str,
    threshold: float,
    total_accounts: int,
    total_units: int,
    by_state: pd.DataFrame,
) -> str:
    pct = f"{round(threshold * 100):g}%"
    lines = [
        f"**Item:** {item}  |  **Coverage target:** {pct}",
        f"**Qualifying accounts:** {total_accounts:,}  |  **Total units to order:** {total_units:,}",
        "",
        "**Per-state breakdown (top 10):**",
    ]

    top10 = by_state.head(10)
    for _, row in top10.iterrows():
        lines.append(
            f"- **{row['STATE_CD']}**: {int(row['account_count']):,} accounts "
            f"→ **{int(row['units_to_order']):,} units**"
        )

    remaining = len(by_state) - 10
    if remaining > 0:
        lines.append(f"- *(+ {remaining} more states — see the Table tab)*")

    return "\n".join(lines)
