"""
output_generator.py
Generates Excel (3-sheet) and CSV downloads from order results.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd

from order_calculator import OrderResult


# ---------------------------------------------------------------------------
# Excel (multi-sheet)
# ---------------------------------------------------------------------------

def generate_excel(
    order_result: OrderResult,
    filtered_df: pd.DataFrame,
    active_filters: dict[str, list[str]],
) -> bytes:
    """
    Build an Excel workbook with three sheets:
      1. Order Summary   — per-state units table + totals
      2. Account Detail  — the filtered account rows
      3. Filters Applied — what filters were active

    Returns raw bytes suitable for st.download_button.
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # ── Sheet 1: Order Summary ──────────────────────────────────────────
        summary_df = _build_summary_sheet(order_result)
        summary_df.to_excel(writer, sheet_name="Order Summary", index=False)
        _autofit_columns(writer, "Order Summary", summary_df)

        # ── Sheet 2: Account Detail ─────────────────────────────────────────
        detail_df = filtered_df.copy()
        # Rename canonical columns to friendly display names
        detail_df = detail_df.rename(columns=_display_column_names())
        detail_df.to_excel(writer, sheet_name="Account Detail", index=False)
        _autofit_columns(writer, "Account Detail", detail_df)

        # ── Sheet 3: Filters Applied ────────────────────────────────────────
        filters_df = _build_filters_sheet(
            active_filters, order_result.item, order_result.threshold
        )
        filters_df.to_excel(writer, sheet_name="Filters Applied", index=False)
        _autofit_columns(writer, "Filters Applied", filters_df)

    return buffer.getvalue()


# ---------------------------------------------------------------------------
# CSV (flat)
# ---------------------------------------------------------------------------

def generate_csv(order_result: OrderResult) -> bytes:
    """
    Return a flat CSV with one row per state containing order quantities.
    """
    df = order_result.per_state.copy()
    df.insert(0, "item", order_result.item)
    df.insert(1, "coverage_threshold", f"{order_result.threshold:.0%}")
    df["generated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_summary_sheet(result: OrderResult) -> pd.DataFrame:
    """Build the Order Summary DataFrame."""
    rows = result.per_state.copy()
    rows = rows.rename(
        columns={
            "state_cd": "State",
            "account_count": "Qualifying Accounts",
            "units_to_order": "Units to Order",
        }
    )

    # Totals row
    totals = pd.DataFrame(
        [
            {
                "State": "TOTAL",
                "Qualifying Accounts": result.total_accounts,
                "Units to Order": result.total_units,
            }
        ]
    )
    df = pd.concat([rows, totals], ignore_index=True)

    # Add metadata columns
    df.insert(0, "Item", result.item)
    df.insert(1, "Coverage Threshold", f"{result.threshold:.0%}")
    df["Generated At"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return df


def _build_filters_sheet(
    filters: dict[str, list[str]],
    item: str,
    threshold: float,
) -> pd.DataFrame:
    from config import FILTER_DIMENSIONS

    rows = [
        {"Setting": "Item", "Value": item or "(none)"},
        {"Setting": "Coverage Threshold", "Value": f"{threshold:.0%}"},
        {"Setting": "Generated At", "Value": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")},
    ]

    for col, vals in filters.items():
        label = FILTER_DIMENSIONS.get(col, col)
        rows.append(
            {
                "Setting": label,
                "Value": ", ".join(vals) if vals else "(all)",
            }
        )
    return pd.DataFrame(rows)


def _display_column_names() -> dict[str, str]:
    """Map canonical column names → friendly display names."""
    return {
        "retailer_cd": "Retailer Code",
        "retailer_nm": "Retailer Name",
        "address_desc": "Address",
        "city_desc": "City",
        "state_cd": "State",
        "premise_typ_desc": "Premise Type",
        "trade_channel_desc": "Trade Channel",
        "sub_channel_alt_desc": "Sub-Channel",
        "chain_ind_cd": "Chain/Ind",
        "liquor_fg": "Liquor",
        "wine_fg": "Wine",
        "beer_fg": "Beer",
        "food_type_desc": "Food Type",
        "store_volume_desc": "Store Volume",
        "weekly_volume_dollars": "Weekly Volume ($)",
        "selling_space_sqr_feet": "Selling Space (sqft)",
    }


def _autofit_columns(
    writer: pd.ExcelWriter,
    sheet_name: str,
    df: pd.DataFrame,
    max_width: int = 50,
) -> None:
    """Adjust column widths based on content length."""
    try:
        ws = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns, start=1):
            col_letter = ws.cell(row=1, column=idx).column_letter
            max_len = max(
                len(str(col)),
                df[col].astype(str).str.len().max() if not df.empty else 0,
            )
            ws.column_dimensions[col_letter].width = min(max_len + 4, max_width)
    except Exception:
        pass  # Non-critical — skip silently
