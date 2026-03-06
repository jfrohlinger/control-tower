"""
order_calculator.py
Coverage threshold → units-to-order calculation logic.

Formula:
    units_per_state = ROUNDUP(account_count × coverage_threshold)
    total_units     = sum of all per-state units
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from query_engine import count_by_state


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OrderResult:
    item: str
    threshold: float                          # e.g. 0.5
    total_accounts: int                       # accounts in the filtered dataset
    total_units: int                          # sum of all per-state units
    per_state: pd.DataFrame = field(default_factory=pd.DataFrame)
    # columns: state_cd | account_count | units_to_order

    def summary_text(self) -> str:
        pct = f"{self.threshold:.0%}"
        lines = [
            f"**{self.item}** — {pct} coverage across {len(self.per_state)} state(s)",
            f"Total accounts in scope: {self.total_accounts:,}",
            f"**Total units to order: {self.total_units:,}**",
            "",
            "Per-state breakdown:",
        ]
        for _, row in self.per_state.iterrows():
            lines.append(
                f"  • {row['state_cd']}: {row['account_count']:,} accounts "
                f"→ {row['units_to_order']:,} units"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item": self.item,
            "threshold": self.threshold,
            "total_accounts": self.total_accounts,
            "total_units": self.total_units,
            "per_state": self.per_state.to_dict(orient="records"),
        }


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_order(
    df: pd.DataFrame,
    item: str,
    coverage_threshold: float,
) -> OrderResult:
    """
    Calculate units to order per state given a filtered DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Already-filtered accounts (only qualifying rows).
    item : str
        Name of the POS item being ordered.
    coverage_threshold : float
        Fraction of accounts to cover (0.0 – 1.0).

    Returns
    -------
    OrderResult
    """
    if df.empty or "state_cd" not in df.columns:
        return OrderResult(
            item=item,
            threshold=coverage_threshold,
            total_accounts=0,
            total_units=0,
            per_state=pd.DataFrame(columns=["state_cd", "account_count", "units_to_order"]),
        )

    state_counts = count_by_state(df)

    # Apply formula: ROUNDUP(count × threshold)
    state_counts["units_to_order"] = state_counts["account_count"].apply(
        lambda n: math.ceil(n * coverage_threshold)
    )

    total_accounts = int(state_counts["account_count"].sum())
    total_units = int(state_counts["units_to_order"].sum())

    return OrderResult(
        item=item,
        threshold=coverage_threshold,
        total_accounts=total_accounts,
        total_units=total_units,
        per_state=state_counts.reset_index(drop=True),
    )


def calculate_multi_item_order(
    df: pd.DataFrame,
    items: list[str],
    coverage_threshold: float,
) -> list[OrderResult]:
    """
    Calculate orders for multiple items against the same filtered dataset.
    Each item gets identical account counts (same filter) but tracked separately.
    """
    return [calculate_order(df, item, coverage_threshold) for item in items]


# ---------------------------------------------------------------------------
# Threshold sensitivity table
# ---------------------------------------------------------------------------

def threshold_sensitivity(
    df: pd.DataFrame,
    item: str,
    thresholds: list[float] | None = None,
) -> pd.DataFrame:
    """
    Return a table showing total units at several coverage thresholds.
    Useful for 'what-if' analysis.

    Parameters
    ----------
    thresholds : list[float], optional
        Defaults to [0.25, 0.50, 0.75, 1.00].

    Returns
    -------
    pd.DataFrame with columns: threshold, total_accounts, total_units
    """
    if thresholds is None:
        thresholds = [0.25, 0.50, 0.75, 1.00]

    rows = []
    for t in thresholds:
        result = calculate_order(df, item, t)
        rows.append(
            {
                "threshold": f"{t:.0%}",
                "total_accounts": result.total_accounts,
                "total_units": result.total_units,
            }
        )
    return pd.DataFrame(rows)
