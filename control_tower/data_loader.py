"""
data_loader.py — CSV/Excel upload, data validation, schema mapping,
                 and synthetic sample-data generation.
"""

from __future__ import annotations

import io
import random
import string
from typing import Optional

import pandas as pd

from config import COLUMN_ALIASES, SAMPLE_DATA_ROWS


# ── Public API ─────────────────────────────────────────────────────────────────

def load_file(uploaded_file) -> tuple[pd.DataFrame, list[str]]:
    """
    Load a CSV or Excel file uploaded via st.file_uploader.

    Returns
    -------
    df      : DataFrame with canonical column names where mappable.
    warnings: List of human-readable messages about missing / unmapped columns.
    """
    name = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()

    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw_bytes))
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw_bytes))
    else:
        raise ValueError(f"Unsupported file type: {uploaded_file.name!r}. Upload CSV or Excel.")

    df, warnings = _remap_columns(df)
    df = _coerce_types(df)
    return df, warnings


def generate_sample_data(n: int = SAMPLE_DATA_ROWS) -> pd.DataFrame:
    """Return a synthetic DataFrame that mirrors the canonical schema."""
    rng = random.Random(42)

    states        = ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI"]
    premises      = ["Off-Premise", "On-Premise"]
    channels      = ["Mass Merchandiser", "Cigarette Outlet", "Category Killer",
                     "Grocery", "Convenience", "Drug Store", "Club"]
    sub_channels  = ["Department Store", "Dollar Store",
                     "Conventional Cigarette Outlet", "Supermarket",
                     "C-Store", "Drug Chain", "Warehouse Club"]
    food_types    = ["Full Service", "Limited Service", "Specialty", "None"]
    volumes       = ["Low", "Medium", "High", "Very High"]

    rows = []
    for i in range(1, n + 1):
        code = "".join(rng.choices(string.digits, k=6))
        state = rng.choice(states)
        premise = rng.choice(premises)
        channel = rng.choice(channels)
        chain = rng.choice(["C", "I"])
        rows.append({
            "RETAILER_CD":           f"R{code}",
            "RETAILER_NM":           f"Store #{i} ({state})",
            "ADDRESS_DESC":          f"{rng.randint(100,9999)} Main St",
            "CITY_DESC":             f"City{rng.randint(1,50)}",
            "STATE_CD":              state,
            "PREMISE_TYP_DESC":      premise,
            "TRADE_CHANNEL_DESC":    channel,
            "SUB_CHANNEL_ALT_DESC":  rng.choice(sub_channels),
            "CHAIN_IND_CD":          chain,
            "LIQUOR_FG":             rng.choice(["Y", "N"]),
            "WINE_FG":               rng.choice(["Y", "N"]),
            "BEER_FG":               rng.choice(["Y", "N"]),
            "FOOD_TYPE_DESC":        rng.choice(food_types),
            "STORE_VOLUME_DESC":     rng.choice(volumes),
            "WEEKLY_VOLUME_DOLLARS": round(rng.uniform(5_000, 250_000), 2),
            "SELLING_SPACE_SQR_FEET": rng.randint(500, 50_000),
        })

    return pd.DataFrame(rows)


def get_data_context(df: pd.DataFrame) -> dict:
    """
    Return a lightweight summary dict the AI agent can use to understand
    what is in the dataset without sending the full frame.
    """
    from config import SEGMENT_DIMENSIONS
    context: dict = {
        "row_count":    len(df),
        "columns":      list(df.columns),
        "unique_values": {},
    }
    for col in SEGMENT_DIMENSIONS:
        if col in df.columns:
            unique_vals = df[col].dropna().unique().tolist()
            # Cap at 50 distinct values to keep prompt manageable
            context["unique_values"][col] = sorted(str(v) for v in unique_vals[:50])
    return context


# ── Internal helpers ───────────────────────────────────────────────────────────

def _remap_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Attempt to map raw column names to canonical names using COLUMN_ALIASES.
    Returns the remapped DataFrame and a list of warning strings.
    """
    # Build reverse map: normalised_raw_name → canonical_name
    reverse: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            reverse[alias.lower().strip()] = canonical

    rename_map: dict[str, str] = {}
    for col in df.columns:
        key = col.lower().strip()
        if key in reverse and col != reverse[key]:
            rename_map[col] = reverse[key]

    df = df.rename(columns=rename_map)

    # Warn about canonical columns that are still missing
    warnings: list[str] = []
    for canonical in COLUMN_ALIASES:
        if canonical not in df.columns:
            warnings.append(f"Column '{canonical}' not found — some features may be limited.")

    return df, warnings


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise flag columns to uppercase Y/N strings."""
    flag_cols = ["LIQUOR_FG", "WINE_FG", "BEER_FG"]
    for col in flag_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace({"1": "Y", "TRUE": "Y", "YES": "Y",
                           "0": "N", "FALSE": "N", "NO": "N"})
            )

    if "CHAIN_IND_CD" in df.columns:
        df["CHAIN_IND_CD"] = (
            df["CHAIN_IND_CD"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"CHAIN": "C", "INDEPENDENT": "I", "IND": "I"})
        )

    # Numeric coercion
    for col in ["WEEKLY_VOLUME_DOLLARS", "SELLING_SPACE_SQR_FEET"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """
    Run basic validation checks and return a list of error strings.
    Empty list means the DataFrame looks OK.
    """
    errors: list[str] = []
    if df.empty:
        errors.append("The uploaded file contains no data rows.")
    if len(df.columns) < 3:
        errors.append("The file has fewer than 3 columns — it may not be the right dataset.")
    return errors
