"""
output_generator.py — Excel (3-sheet) and CSV download generation.

Sheets
------
1. Order Summary  — per-state units-to-order table
2. Account Detail — the filtered account rows
3. Filters Applied — what filters were active
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Optional

import pandas as pd


# ── Excel output ───────────────────────────────────────────────────────────────

def build_excel(
    order_result: Optional[dict],
    filtered_df: pd.DataFrame,
    filters: dict[str, Any],
    item: Optional[str] = None,
    threshold: Optional[float] = None,
) -> bytes:
    """
    Build a multi-sheet Excel workbook and return its raw bytes.

    Parameters
    ----------
    order_result : Output of order_calculator.calculate_order(), or None.
    filtered_df  : The currently filtered account DataFrame.
    filters      : Active filter dict for the "Filters Applied" sheet.
    item         : Selected POS item (for metadata).
    threshold    : Coverage threshold as a float (for metadata).
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # ── Sheet 1: Order Summary ─────────────────────────────────────────────
        if order_result and not order_result["by_state"].empty:
            summary_df = order_result["by_state"].copy()
            summary_df.columns = ["State", "Qualifying Accounts", "Units to Order"]
            # Add totals row
            totals = pd.DataFrame([{
                "State": "TOTAL",
                "Qualifying Accounts": summary_df["Qualifying Accounts"].sum(),
                "Units to Order": summary_df["Units to Order"].sum(),
            }])
            summary_df = pd.concat([summary_df, totals], ignore_index=True)
            summary_df.to_excel(writer, sheet_name="Order Summary", index=False)
            _style_sheet(writer, "Order Summary", summary_df)
        else:
            meta = _build_meta_df(item, threshold, filters)
            meta.to_excel(writer, sheet_name="Order Summary", index=False)

        # ── Sheet 2: Account Detail ────────────────────────────────────────────
        if not filtered_df.empty:
            filtered_df.to_excel(writer, sheet_name="Account Detail", index=False)
            _style_sheet(writer, "Account Detail", filtered_df)
        else:
            pd.DataFrame([{"message": "No accounts match the current filters."}]).to_excel(
                writer, sheet_name="Account Detail", index=False
            )

        # ── Sheet 3: Filters Applied ───────────────────────────────────────────
        filter_rows = []
        filter_rows.append({"Setting": "Export Date/Time", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        filter_rows.append({"Setting": "POS Item", "Value": item or "—"})
        filter_rows.append({"Setting": "Coverage Threshold", "Value": f"{round((threshold or 0) * 100):g}%" if threshold else "—"})
        filter_rows.append({"Setting": "Total Filtered Accounts", "Value": len(filtered_df)})

        for col, val in filters.items():
            if isinstance(val, list):
                val_str = ", ".join(str(v) for v in val)
            else:
                val_str = str(val)
            filter_rows.append({"Setting": f"Filter: {col}", "Value": val_str})

        filter_df = pd.DataFrame(filter_rows)
        filter_df.to_excel(writer, sheet_name="Filters Applied", index=False)
        _style_sheet(writer, "Filters Applied", filter_df)

    return buffer.getvalue()


# ── CSV output ─────────────────────────────────────────────────────────────────

def build_csv(
    order_result: Optional[dict],
    filtered_df: pd.DataFrame,
) -> bytes:
    """
    Build a flat CSV combining per-state order quantities with account detail.
    Returns raw UTF-8 bytes.
    """
    if order_result and not order_result["by_state"].empty:
        # Join order summary onto the filtered accounts
        summary = order_result["by_state"].rename(
            columns={"account_count": "qualifying_accounts", "units_to_order": "units_to_order"}
        )
        if "STATE_CD" in filtered_df.columns:
            merged = filtered_df.merge(summary, on="STATE_CD", how="left")
        else:
            merged = filtered_df
        return merged.to_csv(index=False).encode("utf-8")
    else:
        return filtered_df.to_csv(index=False).encode("utf-8")


# ── Internal helpers ───────────────────────────────────────────────────────────

def _style_sheet(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    """Apply basic column-width auto-fit to a worksheet."""
    try:
        worksheet = writer.sheets[sheet_name]
        for col_idx, col_name in enumerate(df.columns, start=1):
            max_len = max(
                len(str(col_name)),
                df[col_name].astype(str).str.len().max() if len(df) > 0 else 0,
            )
            # openpyxl column width is in characters; cap at 60
            worksheet.column_dimensions[
                _col_letter(col_idx)
            ].width = min(max_len + 4, 60)
    except Exception:
        pass  # Styling is best-effort; never block the download


def _col_letter(n: int) -> str:
    """Convert 1-based column index to Excel letter (A, B, …, Z, AA, …)."""
    result = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _build_meta_df(item, threshold, filters) -> pd.DataFrame:
    rows = [
        {"Key": "POS Item",    "Value": item or "—"},
        {"Key": "Threshold",   "Value": f"{round((threshold or 0)*100):g}%" if threshold else "—"},
        {"Key": "Filters",     "Value": str(filters) if filters else "None"},
        {"Key": "Note",        "Value": "Run a calculation first to populate this sheet."},
    ]
    return pd.DataFrame(rows)
