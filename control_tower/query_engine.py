"""
query_engine.py — Pandas-based filtering and aggregation logic.

All data manipulation lives here so the UI and AI layers stay clean.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ── Filtering ──────────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """
    Apply a dict of column→value(s) filters to df and return the subset.

    Supported filter value types
    ----------------------------
    - str or int/float   : exact match (case-insensitive for strings)
    - list[str]          : membership test  (df[col].isin(values))
    - dict with keys
        "min" / "max"    : numeric range filter

    Parameters
    ----------
    df      : The full dataset.
    filters : Dict produced by the AI plan or the sidebar widget.
              Keys must be column names present in df.
              Unknown keys are silently ignored.

    Returns
    -------
    Filtered DataFrame (copy).
    """
    result = df.copy()

    for col, value in filters.items():
        if col not in result.columns:
            continue  # skip unknown columns gracefully

        if isinstance(value, list):
            if not value:
                continue
            str_vals = [str(v).strip().upper() for v in value]
            result = result[
                result[col].astype(str).str.strip().str.upper().isin(str_vals)
            ]

        elif isinstance(value, dict):
            if "min" in value:
                result = result[pd.to_numeric(result[col], errors="coerce") >= value["min"]]
            if "max" in value:
                result = result[pd.to_numeric(result[col], errors="coerce") <= value["max"]]

        else:
            # Single value — exact match (case-insensitive)
            result = result[
                result[col].astype(str).str.strip().str.upper()
                == str(value).strip().upper()
            ]

    return result


# ── Aggregation ────────────────────────────────────────────────────────────────

def count_by_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame with columns [STATE_CD, account_count]
    sorted descending by account_count.
    """
    if "STATE_CD" not in df.columns:
        return pd.DataFrame(columns=["STATE_CD", "account_count"])

    result = (
        df.groupby("STATE_CD", as_index=False)
        .size()
        .rename(columns={"size": "account_count"})
        .sort_values("account_count", ascending=False)
        .reset_index(drop=True)
    )
    return result


def count_by_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Generic count aggregation: returns [col, account_count] sorted descending.
    """
    if col not in df.columns:
        return pd.DataFrame(columns=[col, "account_count"])

    result = (
        df.groupby(col, as_index=False)
        .size()
        .rename(columns={"size": "account_count"})
        .sort_values("account_count", ascending=False)
        .reset_index(drop=True)
    )
    return result


def get_unique_values(df: pd.DataFrame, col: str) -> list[str]:
    """Return sorted unique non-null string values for a column."""
    if col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).str.strip().unique().tolist())


# ── Summary statistics ─────────────────────────────────────────────────────────

def summarise_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """
    Return a dict with high-level statistics about the current (filtered) dataset.
    """
    summary: dict[str, Any] = {
        "total_accounts": len(df),
        "states":         df["STATE_CD"].nunique() if "STATE_CD" in df.columns else None,
        "channels":       df["TRADE_CHANNEL_DESC"].nunique() if "TRADE_CHANNEL_DESC" in df.columns else None,
    }

    if "PREMISE_TYP_DESC" in df.columns:
        summary["premise_breakdown"] = (
            df["PREMISE_TYP_DESC"].value_counts().to_dict()
        )
    if "CHAIN_IND_CD" in df.columns:
        summary["chain_breakdown"] = (
            df["CHAIN_IND_CD"]
            .map({"C": "Chain", "I": "Independent"})
            .value_counts()
            .to_dict()
        )
    return summary


# ── Top-N helpers ──────────────────────────────────────────────────────────────

def top_n_states(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Return the top-N states by account count."""
    return count_by_state(df).head(n)


def top_n_by_column(df: pd.DataFrame, col: str, n: int = 10) -> pd.DataFrame:
    """Return the top-N values for an arbitrary column by account count."""
    return count_by_column(df, col).head(n)
