"""
app.py
Smart Ordering Control Tower — main Streamlit entry point.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os
import sys

# Ensure the control_tower directory is on the path when running from parent
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_agent import interpret_question
from config import (
    DEFAULT_COVERAGE_THRESHOLD,
    DEFAULT_ITEMS,
    FILTER_DIMENSIONS,
    MAX_COVERAGE_THRESHOLD,
    MIN_COVERAGE_THRESHOLD,
    THRESHOLD_STEP,
)
from data_loader import get_filter_options, load_sample_data, load_uploaded_file
from order_calculator import OrderResult, calculate_order
from output_generator import generate_csv, generate_excel
from query_engine import apply_filters, count_by_state, summarise_by_dimension

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Ordering Control Tower",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS (light, clean)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Chat bubbles */
    .user-bubble {
        background: #e8f0fe;
        border-radius: 12px 12px 2px 12px;
        padding: 10px 14px;
        margin: 6px 0 6px 20%;
        text-align: right;
    }
    .assistant-bubble {
        background: #f1f3f4;
        border-radius: 12px 12px 12px 2px;
        padding: 10px 14px;
        margin: 6px 20% 6px 0;
    }
    /* Metric cards */
    .metric-card {
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    /* Sidebar section headers */
    .sidebar-section {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #5f6368;
        margin: 12px 0 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults: dict = {
        "chat_history": [],       # list of {"role": "user"|"assistant", "content": str}
        "df_raw": None,           # raw uploaded DataFrame
        "df_filtered": None,      # after sidebar filters applied
        "data_source": "sample",  # "sample" | "upload"
        "active_filters": {col: [] for col in FILTER_DIMENSIONS},
        "selected_item": DEFAULT_ITEMS[0],
        "coverage_threshold": DEFAULT_COVERAGE_THRESHOLD,
        "last_order_result": None,
        "api_key": "",
        "warnings": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_base_df() -> pd.DataFrame:
    """Return the active base dataset (uploaded or sample)."""
    if st.session_state.data_source == "upload" and st.session_state.df_raw is not None:
        return st.session_state.df_raw
    return load_sample_data()


def _apply_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    return apply_filters(df, st.session_state.active_filters)


def _execute_plan(plan: dict, base_df: pd.DataFrame) -> None:
    """Apply AI plan: update filters, item, threshold, and re-calculate if needed."""
    intent = plan.get("intent", "question")
    new_filters = plan.get("filters", {})
    new_item = plan.get("item")
    new_threshold = plan.get("threshold")

    # Merge plan filters into sidebar state
    for col, vals in new_filters.items():
        if isinstance(vals, list) and vals:
            st.session_state.active_filters[col] = vals

    if new_item and new_item in DEFAULT_ITEMS:
        st.session_state.selected_item = new_item

    if new_threshold is not None:
        clamped = max(MIN_COVERAGE_THRESHOLD, min(MAX_COVERAGE_THRESHOLD, float(new_threshold)))
        st.session_state.coverage_threshold = clamped

    # Auto-calculate when intent is calculate
    if intent == "calculate":
        filtered = _apply_sidebar_filters(base_df)
        result = calculate_order(
            filtered,
            st.session_state.selected_item,
            st.session_state.coverage_threshold,
        )
        st.session_state.last_order_result = result
        st.session_state.df_filtered = filtered


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.title("🏗️ Control Tower")
        st.markdown("---")

        # ── API Key ──────────────────────────────────────────────────────────
        st.markdown('<p class="sidebar-section">🔑 Claude API Key</p>', unsafe_allow_html=True)
        api_key = st.text_input(
            "API Key",
            value=st.session_state.api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
            type="password",
            placeholder="sk-ant-...",
            label_visibility="collapsed",
        )
        st.session_state.api_key = api_key
        if api_key:
            st.caption("✅ Key set")
        else:
            st.caption("⚠️ No key — rule-based mode")

        st.markdown("---")

        # ── Data Source ───────────────────────────────────────────────────────
        st.markdown('<p class="sidebar-section">📂 Data Source</p>', unsafe_allow_html=True)
        source = st.radio(
            "Source",
            options=["Sample Data (20 rows)", "Upload File"],
            index=0 if st.session_state.data_source == "sample" else 1,
            label_visibility="collapsed",
        )
        st.session_state.data_source = "upload" if source == "Upload File" else "sample"

        if st.session_state.data_source == "upload":
            uploaded = st.file_uploader(
                "Upload CSV or Excel",
                type=["csv", "xlsx", "xls"],
                label_visibility="collapsed",
            )
            if uploaded:
                with st.spinner("Loading file…"):
                    try:
                        df, warnings = load_uploaded_file(uploaded)
                        st.session_state.df_raw = df
                        st.session_state.warnings = warnings
                        st.session_state.active_filters = {col: [] for col in FILTER_DIMENSIONS}
                        st.success(f"Loaded {len(df):,} rows")
                    except RuntimeError as exc:
                        st.error(str(exc))

            if st.session_state.warnings:
                with st.expander("⚠️ Load warnings"):
                    for w in st.session_state.warnings:
                        st.warning(w)

        st.markdown("---")

        # ── Filters ──────────────────────────────────────────────────────────
        st.markdown('<p class="sidebar-section">🔍 Filters</p>', unsafe_allow_html=True)
        base_df = _get_base_df()
        filter_options = get_filter_options(base_df)

        for col, label in FILTER_DIMENSIONS.items():
            options = filter_options.get(col, [])
            if not options:
                continue
            current = st.session_state.active_filters.get(col, [])
            selected = st.multiselect(
                label,
                options=options,
                default=[v for v in current if v in options],
                key=f"filter_{col}",
            )
            st.session_state.active_filters[col] = selected

        if st.button("Clear All Filters", use_container_width=True):
            st.session_state.active_filters = {col: [] for col in FILTER_DIMENSIONS}
            st.rerun()

        st.markdown("---")

        # ── Item + Threshold ─────────────────────────────────────────────────
        st.markdown('<p class="sidebar-section">📦 Order Settings</p>', unsafe_allow_html=True)
        selected_item = st.selectbox(
            "POS Item",
            options=DEFAULT_ITEMS,
            index=DEFAULT_ITEMS.index(st.session_state.selected_item)
            if st.session_state.selected_item in DEFAULT_ITEMS
            else 0,
        )
        st.session_state.selected_item = selected_item

        threshold_pct = st.slider(
            "Coverage Threshold",
            min_value=int(MIN_COVERAGE_THRESHOLD * 100),
            max_value=int(MAX_COVERAGE_THRESHOLD * 100),
            value=int(st.session_state.coverage_threshold * 100),
            step=int(THRESHOLD_STEP * 100),
            format="%d%%",
        )
        st.session_state.coverage_threshold = threshold_pct / 100.0

        if st.button("▶ Calculate Order", type="primary", use_container_width=True):
            filtered = _apply_sidebar_filters(base_df)
            result = calculate_order(
                filtered,
                st.session_state.selected_item,
                st.session_state.coverage_threshold,
            )
            st.session_state.last_order_result = result
            st.session_state.df_filtered = filtered
            st.rerun()


# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

def render_chat(base_df: pd.DataFrame) -> None:
    st.subheader("💬 Ask a Question")

    # Display chat history
    for msg in st.session_state.chat_history:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.markdown(
                f'<div class="user-bubble">🧑‍💼 {content}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="assistant-bubble">🤖 {content}</div>',
                unsafe_allow_html=True,
            )

    # Input row
    col_input, col_send = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Your question",
            placeholder="e.g. Which states need the most Pole Toppers?",
            label_visibility="collapsed",
            key="chat_input",
        )
    with col_send:
        send = st.button("Send", type="primary", use_container_width=True)

    if send and user_input.strip():
        question = user_input.strip()
        st.session_state.chat_history.append({"role": "user", "content": question})

        with st.spinner("Thinking…"):
            plan = interpret_question(
                question=question,
                df=base_df,
                current_filters=st.session_state.active_filters,
                current_item=st.session_state.selected_item,
                current_threshold=st.session_state.coverage_threshold,
                api_key=st.session_state.api_key,
            )

        _execute_plan(plan, base_df)

        answer = plan.get("answer", "I couldn't generate a response.")
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

    if st.session_state.chat_history and st.button("Clear Chat", use_container_width=False):
        st.session_state.chat_history = []
        st.rerun()


# ---------------------------------------------------------------------------
# Results panel
# ---------------------------------------------------------------------------

def render_results(base_df: pd.DataFrame) -> None:
    filtered_df = _apply_sidebar_filters(base_df)
    st.session_state.df_filtered = filtered_df

    order_result: OrderResult | None = st.session_state.last_order_result

    st.markdown("---")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Accounts", f"{len(base_df):,}")
    col2.metric("Filtered Accounts", f"{len(filtered_df):,}")
    col3.metric(
        "States",
        f"{filtered_df['state_cd'].nunique():,}" if "state_cd" in filtered_df.columns else "—",
    )
    col4.metric(
        "Total Units",
        f"{order_result.total_units:,}" if order_result else "—",
    )

    st.markdown("---")

    # Tabs
    tab_summary, tab_table, tab_chart, tab_download = st.tabs(
        ["📋 Summary", "📊 Table", "📈 Chart", "⬇️ Download"]
    )

    # ── Summary tab ──────────────────────────────────────────────────────────
    with tab_summary:
        if order_result:
            st.markdown(order_result.summary_text())
        else:
            # Show quick stats when no order has been calculated
            st.info("Use the sidebar controls and click **▶ Calculate Order** to see order quantities, or ask a question in the chat above.")
            if not filtered_df.empty and "state_cd" in filtered_df.columns:
                st.subheader("Accounts by State")
                state_counts = count_by_state(filtered_df)
                st.dataframe(state_counts, use_container_width=True, hide_index=True)

            if not filtered_df.empty and "trade_channel_desc" in filtered_df.columns:
                st.subheader("Accounts by Trade Channel")
                channel_counts = summarise_by_dimension(filtered_df, "trade_channel_desc")
                st.dataframe(channel_counts, use_container_width=True, hide_index=True)

    # ── Table tab ─────────────────────────────────────────────────────────────
    with tab_table:
        st.subheader("Order Quantities by State")
        if order_result and not order_result.per_state.empty:
            display = order_result.per_state.rename(
                columns={
                    "state_cd": "State",
                    "account_count": "Qualifying Accounts",
                    "units_to_order": "Units to Order",
                }
            )
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.caption("No order calculated yet.")

        st.subheader("Filtered Account Detail")
        if not filtered_df.empty:
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No accounts match the current filters.")

    # ── Chart tab ─────────────────────────────────────────────────────────────
    with tab_chart:
        if order_result and not order_result.per_state.empty:
            fig = px.bar(
                order_result.per_state,
                x="state_cd",
                y="units_to_order",
                color="units_to_order",
                color_continuous_scale="Blues",
                labels={
                    "state_cd": "State",
                    "units_to_order": "Units to Order",
                },
                title=f"{order_result.item} — Units to Order by State ({order_result.threshold:.0%} coverage)",
                text="units_to_order",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                xaxis_tickangle=-45,
                margin=dict(t=60, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Secondary: account count
            fig2 = px.bar(
                order_result.per_state,
                x="state_cd",
                y="account_count",
                color="account_count",
                color_continuous_scale="Greens",
                labels={
                    "state_cd": "State",
                    "account_count": "Qualifying Accounts",
                },
                title="Qualifying Accounts by State",
                text="account_count",
            )
            fig2.update_traces(textposition="outside")
            fig2.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                xaxis_tickangle=-45,
                margin=dict(t=60, b=80),
            )
            st.plotly_chart(fig2, use_container_width=True)

        elif not filtered_df.empty and "state_cd" in filtered_df.columns:
            state_counts = count_by_state(filtered_df)
            fig = px.bar(
                state_counts,
                x="state_cd",
                y="account_count",
                color="account_count",
                color_continuous_scale="Blues",
                labels={"state_cd": "State", "account_count": "Accounts"},
                title="Accounts by State (no order calculated yet)",
                text="account_count",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Calculate an order or filter data to see charts.")

    # ── Download tab ─────────────────────────────────────────────────────────
    with tab_download:
        st.subheader("Download Results")

        if order_result is None:
            st.info("Calculate an order first to enable downloads.")
        else:
            col_dl1, col_dl2 = st.columns(2)

            with col_dl1:
                excel_bytes = generate_excel(
                    order_result,
                    filtered_df,
                    st.session_state.active_filters,
                )
                st.download_button(
                    label="⬇️ Download Excel (3 sheets)",
                    data=excel_bytes,
                    file_name=f"order_{order_result.item.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with col_dl2:
                csv_bytes = generate_csv(order_result)
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_bytes,
                    file_name=f"order_{order_result.item.replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            # Preview
            with st.expander("Preview — Order Summary"):
                preview = order_result.per_state.rename(
                    columns={
                        "state_cd": "State",
                        "account_count": "Accounts",
                        "units_to_order": "Units",
                    }
                )
                st.dataframe(preview, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def main() -> None:
    render_sidebar()

    base_df = _get_base_df()

    # Header
    st.title("🏗️ Smart Ordering Control Tower")
    st.caption(
        f"Data: **{'Uploaded file' if st.session_state.data_source == 'upload' and st.session_state.df_raw is not None else 'Sample data (20 rows)'}** "
        f"— {len(base_df):,} accounts loaded"
    )

    render_chat(base_df)
    render_results(base_df)


if __name__ == "__main__":
    main()
