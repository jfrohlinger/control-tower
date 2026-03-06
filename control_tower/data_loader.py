"""
data_loader.py
Handles CSV/Excel file uploads, validates schema, and maps columns to canonical names.
Falls back to synthetic sample data when no file is provided.
"""

from __future__ import annotations

import io
import random
import string
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    CANONICAL_COLUMNS,
    SAMPLE_FOOD_TYPES,
    SAMPLE_PREMISE_TYPES,
    SAMPLE_ROW_COUNT,
    SAMPLE_STATES,
    SAMPLE_STORE_VOLUMES,
    SAMPLE_SUB_CHANNELS,
    SAMPLE_TRADE_CHANNELS,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame, list[str]]:
    """
    Accept a Streamlit UploadedFile object (CSV or Excel).

    Returns
    -------
    df : pd.DataFrame  — data with canonical column names
    warnings : list[str] — non-fatal issues found during load
    """
    warnings: list[str] = []

    filename: str = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()

    try:
        if filename.endswith(".csv"):
            df = _read_csv(raw_bytes)
        elif filename.endswith((".xlsx", ".xls")):
            df = _read_excel(raw_bytes)
        else:
            raise ValueError(
                f"Unsupported file type: {uploaded_file.name}. "
                "Please upload a .csv, .xlsx, or .xls file."
            )
    except Exception as exc:
        raise RuntimeError(f"Could not read file: {exc}") from exc

    df, mapping_warnings = _map_columns(df)
    warnings.extend(mapping_warnings)

    df, clean_warnings = _clean_data(df)
    warnings.extend(clean_warnings)

    return df, warnings


def load_sample_data() -> pd.DataFrame:
    """Generate a synthetic dataset of SAMPLE_ROW_COUNT rows."""
    rng = random.Random(42)
    np.random.seed(42)

    rows = []
    for i in range(1, SAMPLE_ROW_COUNT + 1):
        state = rng.choice(SAMPLE_STATES)
        premise = rng.choice(SAMPLE_PREMISE_TYPES)
        channel = rng.choice(SAMPLE_TRADE_CHANNELS)
        sub_channel = rng.choice(SAMPLE_SUB_CHANNELS)
        chain = rng.choice(["C", "I"])

        rows.append(
            {
                "retailer_cd": f"R{i:04d}",
                "retailer_nm": f"Store {''.join(rng.choices(string.ascii_uppercase, k=4))} {i}",
                "address_desc": f"{rng.randint(100, 9999)} Main St",
                "city_desc": f"City{rng.randint(1, 50)}",
                "state_cd": state,
                "premise_typ_desc": premise,
                "trade_channel_desc": channel,
                "sub_channel_alt_desc": sub_channel,
                "chain_ind_cd": chain,
                "liquor_fg": rng.choice(["Y", "N"]),
                "wine_fg": rng.choice(["Y", "N"]),
                "beer_fg": rng.choice(["Y", "N"]),
                "food_type_desc": rng.choice(SAMPLE_FOOD_TYPES),
                "store_volume_desc": rng.choice(SAMPLE_STORE_VOLUMES),
                "weekly_volume_dollars": round(rng.uniform(5_000, 150_000), 2),
                "selling_space_sqr_feet": rng.randint(500, 50_000),
            }
        )

    return pd.DataFrame(rows)


def get_filter_options(df: pd.DataFrame) -> dict[str, list]:
    """
    Return sorted unique values for each filterable column that exists in df.
    Values are always strings; empty / NaN are excluded.
    """
    from config import FILTER_DIMENSIONS

    options: dict[str, list] = {}
    for col in FILTER_DIMENSIONS:
        if col in df.columns:
            vals = (
                df[col]
                .dropna()
                .astype(str)
                .str.strip()
                .replace("", np.nan)
                .dropna()
                .unique()
                .tolist()
            )
            options[col] = sorted(vals)
        else:
            options[col] = []
    return options


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Try multiple encodings for robustness."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV with any supported encoding.")


def _read_excel(raw_bytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(raw_bytes))
    # Use first sheet
    return pd.read_excel(xls, sheet_name=xls.sheet_names[0])


def _map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Rename raw columns to canonical names based on CANONICAL_COLUMNS mapping.
    Returns the modified DataFrame and a list of warnings for unmapped columns.
    """
    warnings: list[str] = []
    rename_map: dict[str, str] = {}

    # Build reverse lookup: raw_name → canonical
    raw_to_canonical: dict[str, str] = {}
    for canonical, aliases in CANONICAL_COLUMNS.items():
        for alias in aliases:
            raw_to_canonical[alias.lower().strip()] = canonical

    for col in df.columns:
        normalized = col.lower().strip()
        if normalized in raw_to_canonical:
            canonical = raw_to_canonical[normalized]
            if col != canonical:
                rename_map[col] = canonical
        # If column already has canonical name, keep it

    df = df.rename(columns=rename_map)

    # Warn about important missing columns
    important = ["state_cd", "retailer_cd"]
    for col in important:
        if col not in df.columns:
            warnings.append(
                f"Column '{col}' not found in uploaded file. "
                "Some features may not work correctly."
            )

    return df, warnings


def _clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Normalise string columns: strip whitespace, uppercase flag columns.
    Returns cleaned DataFrame and any warnings.
    """
    warnings: list[str] = []
    original_len = len(df)

    # Drop fully empty rows
    df = df.dropna(how="all")
    dropped = original_len - len(df)
    if dropped > 0:
        warnings.append(f"Removed {dropped} completely empty row(s).")

    # Normalise string columns
    str_cols = df.select_dtypes(include="object").columns.tolist()
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", np.nan)

    # Uppercase flag columns
    for flag_col in ["liquor_fg", "wine_fg", "beer_fg", "chain_ind_cd"]:
        if flag_col in df.columns:
            df[flag_col] = df[flag_col].str.upper()

    return df, warnings
