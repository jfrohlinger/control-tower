"""
query_engine.py
Pandas-based filtering and aggregation logic.
All filtering uses the canonical column names defined in config.py.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import FILTER_DIMENSIONS


# ---------------------------------------------------------------------------
# Main filter function
# ---------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    """
    Apply a dict of filters to df and return the matching rows.

    Parameters
    ----------
    df : pd.DataFrame
    filters : dict
        Keys are canonical column names; values are lists of accepted values.
        Empty lists mean "no restriction on this dimension".

    Returns
    -------
    Filtered pd.DataFrame (never mutates the original).
    """
    result = df.copy()

    for col, values in filters.items():
        if not values:
            continue  # no restriction
        if col not in result.columns:
            continue  # column absent — skip silently

        # Normalise both sides to str for comparison
        col_series = result[col].astype(str).str.strip()
        str_values = [str(v).strip() for v in values]
        result = result[col_series.isin(str_values)]

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def count_by_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame with columns: state_cd, account_count
    sorted descending by account_count.
    """
    if "state_cd" not in df.columns:
        return pd.DataFrame(columns=["state_cd", "account_count"])

    counts = (
        df.groupby("state_cd", dropna=False)
        .size()
        .reset_index(name="account_count")
        .sort_values("account_count", ascending=False)
        .reset_index(drop=True)
    )
    return counts


def summarise_by_dimension(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """
    Group df by `dimension` and return count + % of total.

    Parameters
    ----------
    dimension : str — canonical column name

    Returns
    -------
    DataFrame with columns: <dimension>, count, pct
    """
    if dimension not in df.columns:
        return pd.DataFrame(columns=[dimension, "count", "pct"])

    total = len(df)
    grouped = (
        df.groupby(dimension, dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )
    grouped["pct"] = (grouped["count"] / total * 100).round(1) if total > 0 else 0.0
    return grouped


def top_states_for_item(
    df: pd.DataFrame,
    n: int = 10,
) -> pd.DataFrame:
    """
    Return the top-N states by account count (descending).
    Useful for answering "which states need the most X?" questions.
    """
    return count_by_state(df).head(n)


# ---------------------------------------------------------------------------
# Data context builder (fed to the AI agent)
# ---------------------------------------------------------------------------

def build_data_context(df: pd.DataFrame) -> dict[str, Any]:
    """
    Build a compact summary of the current DataFrame to pass to Claude.
    Keeps token usage low by only including unique-value lists for low-cardinality columns.
    """
    context: dict[str, Any] = {
        "total_rows": len(df),
        "columns": list(df.columns),
        "filter_options": {},
    }

    for col in FILTER_DIMENSIONS:
        if col in df.columns:
            unique_vals = (
                df[col]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
                .tolist()
            )
            # Only include if cardinality is manageable
            if len(unique_vals) <= 60:
                context["filter_options"][col] = sorted(unique_vals)
            else:
                context["filter_options"][col] = f"<{len(unique_vals)} unique values>"

    return context


# ---------------------------------------------------------------------------
# Quick-answer logic (used when Claude API is unavailable)
# ---------------------------------------------------------------------------

def rule_based_answer(question: str, df: pd.DataFrame) -> dict[str, Any]:
    """
    Minimal rule-based fallback that interprets very common questions without Claude.

    Returns a plan dict compatible with the AI agent output schema.
    """
    q = question.lower()

    # Default empty plan
    plan: dict[str, Any] = {
        "intent": "question",
        "filters": {col: [] for col in FILTER_DIMENSIONS},
        "item": None,
        "threshold": None,
        "answer": "",
    }

    # Detect state-based questions
    if "state" in q or "states" in q:
        state_counts = count_by_state(df)
        if len(state_counts) == 0:
            plan["answer"] = "No state data available in the current dataset."
        else:
            top = state_counts.head(5)
            lines = [f"  • {row.state_cd}: {row.account_count:,} accounts" for _, row in top.iterrows()]
            plan["answer"] = (
                f"Top states by account count:\n" + "\n".join(lines)
            )
        return plan

    # Detect count / total questions
    if any(w in q for w in ["how many", "count", "total"]):
        plan["answer"] = f"The current filtered dataset contains {len(df):,} accounts."
        return plan

    # Detect channel questions
    if "channel" in q:
        breakdown = summarise_by_dimension(df, "trade_channel_desc")
        if len(breakdown) == 0:
            plan["answer"] = "No trade channel data available."
        else:
            lines = [
                f"  • {row['trade_channel_desc']}: {row['count']:,} ({row['pct']}%)"
                for _, row in breakdown.head(8).iterrows()
            ]
            plan["answer"] = "Accounts by trade channel:\n" + "\n".join(lines)
        return plan

    # Generic fallback
    plan["answer"] = (
        f"Your dataset has {len(df):,} accounts across "
        f"{df['state_cd'].nunique() if 'state_cd' in df.columns else 'N/A'} states. "
        "Try asking about specific states, channels, or order quantities."
    )
    return plan
