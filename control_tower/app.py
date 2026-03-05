"""
app.py — Smart Ordering Control Tower
Main Streamlit entry point.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Local modules ──────────────────────────────────────────────────────────────
from config import (
    APP_ICON,
    APP_TITLE,
    DEFAULT_ITEMS,
    DEFAULT_THRESHOLD,
    DIMENSION_LABELS,
    MAX_THRESHOLD,
    MIN_THRESHOLD,
    SEGMENT_DIMENSIONS,
    THRESHOLD_STEP,
    WELCOME_MESSAGE,
)
from data_loader import (
    generate_sample_data,
    get_data_context,
    load_file,
    validate_dataframe,
)
from query_engine import apply_filters, get_unique_values, summarise_dataset, top_n_states
from ai_agent import interpret_question
from order_calculator import calculate_order
from output_generator import build_csv, build_excel


# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Session state initialisation ───────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "df":              None,     # Active DataFrame
        "is_sample":       True,     # Using sample data?
        "chat_history":    [],       # [{"role": "user"|"assistant", "content": str}]
        "active_filters":  {},       # Current filter dict
        "last_result":     None,     # Last order_calculator result
        "last_filtered_df": None,    # DataFrame after last filter op
        "selected_item":   DEFAULT_ITEMS[0],
        "threshold":       DEFAULT_THRESHOLD,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ── Sidebar ────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.title(f"{APP_ICON} {APP_TITLE}")
        st.divider()

        # ── Data source ────────────────────────────────────────────────────────
        st.subheader("📂 Data Source")
        uploaded = st.file_uploader(
            "Upload retail account dataset",
            type=["csv", "xlsx", "xls"],
            help="CSV or Excel file with account data. Column names are mapped automatically.",
        )

        if uploaded is not None:
            try:
                df, warnings = load_file(uploaded)
                errors = validate_dataframe(df)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state["df"] = df
                    st.session_state["is_sample"] = False
                    st.session_state["active_filters"] = {}
                    st.success(f"Loaded {len(df):,} accounts from **{uploaded.name}**")
                    for w in warnings[:3]:  # show at most 3 warnings
                        st.warning(w)
            except Exception as exc:
                st.error(f"Could not load file: {exc}")

        if st.session_state["df"] is None:
            st.session_state["df"] = generate_sample_data()
            st.session_state["is_sample"] = True

        if st.session_state["is_sample"]:
            st.info("Using **sample data** (20 synthetic accounts). Upload a file above to use real data.")

        st.divider()

        # ── Segment filters ────────────────────────────────────────────────────
        st.subheader("🔎 Segment Filters")
        df: pd.DataFrame = st.session_state["df"]
        new_filters: dict[str, Any] = {}

        for col in SEGMENT_DIMENSIONS:
            if col not in df.columns:
                continue
            label = DIMENSION_LABELS.get(col, col)
            options = get_unique_values(df, col)
            if not options:
                continue

            selected = st.multiselect(
                label,
                options=options,
                default=st.session_state["active_filters"].get(col, []),
                key=f"filter_{col}",
            )
            if selected:
                new_filters[col] = selected

        if st.button("Apply Filters", use_container_width=True):
            st.session_state["active_filters"] = new_filters
            st.rerun()

        if st.button("Clear Filters", use_container_width=True):
            st.session_state["active_filters"] = {}
            st.rerun()

        # Show active filter count
        n_active = len(st.session_state["active_filters"])
        if n_active:
            st.caption(f"✅ {n_active} filter(s) active")

        st.divider()

        # ── Item selector ──────────────────────────────────────────────────────
        st.subheader("🏷️ POS Item")
        st.session_state["selected_item"] = st.selectbox(
            "Select item",
            options=DEFAULT_ITEMS,
            index=DEFAULT_ITEMS.index(st.session_state["selected_item"])
            if st.session_state["selected_item"] in DEFAULT_ITEMS else 0,
        )

        # ── Coverage threshold ─────────────────────────────────────────────────
        st.subheader("📊 Coverage Threshold")
        st.session_state["threshold"] = st.slider(
            "Coverage target",
            min_value=MIN_THRESHOLD,
            max_value=MAX_THRESHOLD,
            value=st.session_state["threshold"],
            step=THRESHOLD_STEP,
            format="%.0f%%",
            help="Fraction of qualifying accounts to target per state.",
        )

        if st.button("🧮 Calculate Order", use_container_width=True, type="primary"):
            _run_calculation()


# ── Main content ───────────────────────────────────────────────────────────────

def render_main() -> None:
    st.title(f"{APP_ICON} {APP_TITLE}")

    if st.session_state["is_sample"]:
        st.caption("📋 Sample data mode — upload a real dataset via the sidebar")

    # ── Chat interface ─────────────────────────────────────────────────────────
    st.subheader("💬 Ask a question")

    # Display history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Welcome message on first load
    if not st.session_state["chat_history"]:
        with st.chat_message("assistant"):
            st.markdown(WELCOME_MESSAGE)

    # Chat input
    if prompt := st.chat_input("Ask anything about your data…"):
        _handle_chat(prompt)

    # ── Results panel ──────────────────────────────────────────────────────────
    _render_results_panel()


# ── Business logic ─────────────────────────────────────────────────────────────

def _handle_chat(question: str) -> None:
    """Process a user question through the AI agent and update state."""
    df = st.session_state["df"]
    data_ctx = get_data_context(df)

    # Display user message immediately
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.spinner("Thinking…"):
        plan = interpret_question(
            question=question,
            data_context=data_ctx,
            chat_history=st.session_state["chat_history"][:-1],  # exclude the just-added msg
        )

    intent    = plan.get("intent", "question")
    filters   = plan.get("filters", {})
    item      = plan.get("item") or st.session_state["selected_item"]
    threshold = plan.get("threshold") or st.session_state["threshold"]
    answer    = plan.get("answer", "")

    # ── Execute the plan ───────────────────────────────────────────────────────
    if intent in ("filter", "calculate"):
        if filters:
            st.session_state["active_filters"] = {**st.session_state["active_filters"], **filters}

    if item and item in DEFAULT_ITEMS:
        st.session_state["selected_item"] = item

    if threshold:
        st.session_state["threshold"] = threshold

    # Apply filters
    filtered = apply_filters(df, st.session_state["active_filters"])
    st.session_state["last_filtered_df"] = filtered

    if intent == "calculate":
        result = calculate_order(filtered, item, threshold)
        st.session_state["last_result"] = result
        # Append order summary to the answer
        answer = f"{answer}\n\n{result['summary_text']}"

    elif intent == "question" and not answer:
        summary = summarise_dataset(filtered)
        answer = _build_data_answer(question, summary, filtered)

    # Post assistant reply
    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)

    st.rerun()


def _run_calculation() -> None:
    """Triggered by the sidebar 'Calculate Order' button."""
    df       = st.session_state["df"]
    filtered = apply_filters(df, st.session_state["active_filters"])
    item     = st.session_state["selected_item"]
    threshold = st.session_state["threshold"]

    st.session_state["last_filtered_df"] = filtered
    result = calculate_order(filtered, item, threshold)
    st.session_state["last_result"] = result

    msg = (
        f"📦 **Order calculated** for **{item}** at **{result['threshold_pct']} coverage**.\n\n"
        f"{result['summary_text']}"
    )
    st.session_state["chat_history"].append({"role": "assistant", "content": msg})


def _build_data_answer(question: str, summary: dict, df: pd.DataFrame) -> str:
    """Build a fallback plain-text answer from dataset statistics."""
    top = top_n_states(df, n=5)
    top_states_str = ", ".join(
        f"{row['STATE_CD']} ({int(row['account_count'])} accounts)"
        for _, row in top.iterrows()
    ) if not top.empty else "none found"

    return (
        f"Based on the current filters, there are **{summary['total_accounts']:,} accounts** "
        f"across **{summary.get('states', '?')} state(s)**.\n\n"
        f"**Top states by account count:** {top_states_str}\n\n"
        f"Use the sidebar filters to narrow down accounts, then click **Calculate Order** "
        f"to see units to order per state."
    )


# ── Results panel ──────────────────────────────────────────────────────────────

def _render_results_panel() -> None:
    df       = st.session_state["df"]
    filters  = st.session_state["active_filters"]
    result   = st.session_state["last_result"]

    # Use last filtered df if available; otherwise apply active filters live
    if st.session_state["last_filtered_df"] is not None:
        filtered = st.session_state["last_filtered_df"]
    else:
        filtered = apply_filters(df, filters)

    # Always keep filtered df in sync
    fresh_filtered = apply_filters(df, filters)

    st.divider()
    st.subheader("📋 Results")

    # Metric row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Accounts (raw)",      f"{len(df):,}")
    col2.metric("Qualifying Accounts",        f"{len(fresh_filtered):,}")
    col3.metric("Active Filters",             str(len(filters)))
    col4.metric(
        "Units to Order",
        f"{result['total_units']:,}" if result else "—",
    )

    tab_summary, tab_table, tab_chart, tab_download = st.tabs(
        ["📝 Summary", "📊 Table", "📈 Chart", "⬇️ Download"]
    )

    # ── Summary tab ────────────────────────────────────────────────────────────
    with tab_summary:
        if result:
            st.markdown(result["summary_text"])
        else:
            summary = summarise_dataset(fresh_filtered)
            st.markdown(f"### Dataset at a Glance")
            st.markdown(
                f"- **Qualifying accounts:** {summary['total_accounts']:,}\n"
                f"- **States represented:** {summary.get('states', '?')}\n"
                f"- **Trade channels:** {summary.get('channels', '?')}\n"
            )
            if "premise_breakdown" in summary:
                st.markdown("**Premise type breakdown:**")
                for prem, cnt in summary["premise_breakdown"].items():
                    st.markdown(f"  - {prem}: {cnt:,}")
            if "chain_breakdown" in summary:
                st.markdown("**Chain / Independent breakdown:**")
                for typ, cnt in summary["chain_breakdown"].items():
                    st.markdown(f"  - {typ}: {cnt:,}")
            st.info("Set an item and threshold in the sidebar, then click **Calculate Order** to see units.")

    # ── Table tab ──────────────────────────────────────────────────────────────
    with tab_table:
        if result and not result["by_state"].empty:
            st.markdown(f"**Order quantities — {result['item']} @ {result['threshold_pct']} coverage**")
            display = result["by_state"].copy()
            display.columns = ["State", "Qualifying Accounts", "Units to Order"]
            st.dataframe(display, use_container_width=True, hide_index=True)
            st.divider()

        st.markdown("**Filtered account list**")
        if fresh_filtered.empty:
            st.warning("No accounts match the current filters.")
        else:
            # Show a sensible subset of columns first
            priority_cols = [
                "RETAILER_CD", "RETAILER_NM", "STATE_CD", "CITY_DESC",
                "PREMISE_TYP_DESC", "TRADE_CHANNEL_DESC", "CHAIN_IND_CD",
            ]
            show_cols = [c for c in priority_cols if c in fresh_filtered.columns]
            remaining = [c for c in fresh_filtered.columns if c not in show_cols]
            st.dataframe(
                fresh_filtered[show_cols + remaining],
                use_container_width=True,
                hide_index=True,
            )

    # ── Chart tab ──────────────────────────────────────────────────────────────
    with tab_chart:
        if result and not result["by_state"].empty:
            fig = px.bar(
                result["by_state"],
                x="STATE_CD",
                y="units_to_order",
                color="units_to_order",
                color_continuous_scale="Blues",
                labels={
                    "STATE_CD":       "State",
                    "units_to_order": "Units to Order",
                },
                title=f"{result['item']} — Units to Order by State ({result['threshold_pct']} coverage)",
            )
            fig.update_layout(
                coloraxis_showscale=False,
                xaxis_title="State",
                yaxis_title="Units to Order",
                margin=dict(t=60, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

            fig2 = px.bar(
                result["by_state"],
                x="STATE_CD",
                y="account_count",
                color="account_count",
                color_continuous_scale="Greens",
                labels={
                    "STATE_CD":      "State",
                    "account_count": "Qualifying Accounts",
                },
                title="Qualifying Accounts by State",
            )
            fig2.update_layout(
                coloraxis_showscale=False,
                xaxis_title="State",
                yaxis_title="Accounts",
                margin=dict(t=60, b=40),
            )
            st.plotly_chart(fig2, use_container_width=True)

        elif not fresh_filtered.empty and "STATE_CD" in fresh_filtered.columns:
            state_counts = (
                fresh_filtered.groupby("STATE_CD")
                .size()
                .reset_index(name="account_count")
                .sort_values("account_count", ascending=False)
            )
            fig = px.bar(
                state_counts,
                x="STATE_CD",
                y="account_count",
                color="account_count",
                color_continuous_scale="Blues",
                labels={"STATE_CD": "State", "account_count": "Accounts"},
                title="Qualifying Accounts by State",
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

            # Channel breakdown pie
            if "TRADE_CHANNEL_DESC" in fresh_filtered.columns:
                channel_counts = (
                    fresh_filtered["TRADE_CHANNEL_DESC"]
                    .value_counts()
                    .reset_index()
                    .rename(columns={"index": "channel", "TRADE_CHANNEL_DESC": "count"})
                )
                # handle pandas >= 2.0 value_counts column naming
                if "count" not in channel_counts.columns:
                    channel_counts.columns = ["channel", "count"]
                fig_pie = px.pie(
                    channel_counts,
                    names="channel",
                    values="count",
                    title="Accounts by Trade Channel",
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Apply filters or run a calculation to see charts.")

    # ── Download tab ───────────────────────────────────────────────────────────
    with tab_download:
        st.markdown("### Export Results")
        dl_col1, dl_col2 = st.columns(2)

        item_label = (result["item"] if result else st.session_state["selected_item"]).replace(" ", "_")
        ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"order_{item_label}_{ts}"

        with dl_col1:
            excel_bytes = build_excel(
                order_result=result,
                filtered_df=fresh_filtered,
                filters=filters,
                item=result["item"] if result else st.session_state["selected_item"],
                threshold=result["threshold"] if result else st.session_state["threshold"],
            )
            st.download_button(
                label="⬇️ Download Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"{filename_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.caption("3 sheets: Order Summary · Account Detail · Filters Applied")

        with dl_col2:
            csv_bytes = build_csv(result, fresh_filtered)
            st.download_button(
                label="⬇️ Download CSV (.csv)",
                data=csv_bytes,
                file_name=f"{filename_base}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.caption("Flat CSV with account detail + order quantities")

        if not result:
            st.info("Run a calculation first to include order quantities in your export.")


# ── Entry point ────────────────────────────────────────────────────────────────

render_sidebar()
render_main()
