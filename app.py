import random
import streamlit as st
import pandas as pd
import numpy as np

# ── Seed data ──────────────────────────────────────────────────────────────────

STATES = ["CA", "TX", "FL", "NY", "IL", "OH", "PA", "GA", "NC", "AZ"]
CHANNELS = ["Mass Merchandiser", "Grocery", "Cigarette Outlet", "Drug Store"]
ACCOUNT_TYPES = ["Chain", "Independent"]
PREMISE_TYPES = ["Off-Premise", "On-Premise"]
VOLUME_TIERS = ["Low", "Medium", "High", "Very High"]

CHAINS = {
    "Mass Merchandiser": ["Walmart", "Target", "Costco"],
    "Grocery": ["Kroger", "Safeway", "Publix"],
    "Cigarette Outlet": ["Circle K", "7-Eleven", "BP"],
    "Drug Store": ["CVS", "Walgreens", "Rite Aid"],
}


@st.cache_data
def generate_accounts(n: int = 1000) -> pd.DataFrame:
    random.seed(42)
    np.random.seed(42)
    rows = []
    for i in range(1, n + 1):
        channel = random.choice(CHANNELS)
        acct_type = random.choice(ACCOUNT_TYPES)
        chain_name = random.choice(CHAINS[channel]) if acct_type == "Chain" else f"Local Store #{i}"
        rows.append(
            {
                "account_id": f"ACC-{i:04d}",
                "account_name": chain_name,
                "state": random.choice(STATES),
                "trade_channel": channel,
                "account_type": acct_type,
                "premise_type": random.choice(PREMISE_TYPES),
                # % of visits where display was present last period
                "current_coverage_pct": round(random.uniform(5, 100), 1),
                # how many display units that account typically needs
                "units_needed": random.randint(1, 6),
                "store_volume": random.choice(VOLUME_TIERS),
            }
        )
    return pd.DataFrame(rows)


# ── App ────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Smart Ordering Control Tower", page_icon="📊", layout="wide")
st.title("📊 Smart Ordering Control Tower")

df_all = generate_accounts(1000)

# ── Sidebar filters ────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    item_name = st.text_input("POS Item", value="Pole Toppers")

    st.divider()

    state_options = ["All"] + sorted(df_all["state"].unique().tolist())
    selected_state = st.selectbox("State", state_options)

    channel_options = ["All"] + CHANNELS
    selected_channel = st.selectbox("Trade Channel", channel_options)

    type_options = ["All"] + ACCOUNT_TYPES
    selected_type = st.selectbox("Chain vs Independent", type_options)

    premise_options = ["All"] + PREMISE_TYPES
    selected_premise = st.selectbox("Premise Type", premise_options)

    volume_options = ["All"] + VOLUME_TIERS
    selected_volume = st.selectbox("Store Volume", volume_options)

    st.divider()

    # ── Coverage threshold mode ────────────────────────────────────────────────
    st.subheader("Coverage Threshold (%)")
    threshold_mode = st.radio(
        "Apply threshold",
        ["Equally across all states", "Per state"],
        help="Choose whether to use one threshold for all states or set a custom threshold per state.",
    )

    available_states = sorted(df_all["state"].unique().tolist())

    if threshold_mode == "Equally across all states":
        global_threshold = st.slider(
            "Global threshold",
            min_value=10,
            max_value=100,
            value=80,
            step=5,
            help="Include accounts whose coverage is below this value.",
        )
        state_thresholds = {s: global_threshold for s in available_states}
        coverage_threshold = global_threshold  # for summary text
    else:
        st.caption("Set a threshold for each state:")
        state_thresholds = {}
        for s in available_states:
            state_thresholds[s] = st.slider(
                s,
                min_value=10,
                max_value=100,
                value=80,
                step=5,
                key=f"thresh_{s}",
            )
        coverage_threshold = None  # no single value; varies by state

# ── Filter logic ───────────────────────────────────────────────────────────────

df = df_all.copy()

if selected_state != "All":
    df = df[df["state"] == selected_state]
if selected_channel != "All":
    df = df[df["trade_channel"] == selected_channel]
if selected_type != "All":
    df = df[df["account_type"] == selected_type]
if selected_premise != "All":
    df = df[df["premise_type"] == selected_premise]
if selected_volume != "All":
    df = df[df["store_volume"] == selected_volume]

# Apply per-state (or global) coverage threshold
df["_threshold"] = df["state"].map(state_thresholds)
df = df[df["current_coverage_pct"] < df["_threshold"]]
df = df.drop(columns=["_threshold"])

# ── Aggregation ────────────────────────────────────────────────────────────────

total_units = int(df["units_needed"].sum())
total_accounts = len(df)
num_states = df["state"].nunique() if total_accounts > 0 else 0

by_state = (
    df.groupby("state")
    .agg(accounts=("account_id", "count"), units_to_order=("units_needed", "sum"))
    .reset_index()
    .rename(columns={"state": "State", "accounts": "Qualifying Accounts", "units_to_order": "Units to Order"})
    .sort_values("Units to Order", ascending=False)
)

# ── Plain-English Summary ──────────────────────────────────────────────────────

if total_accounts == 0:
    summary = (
        "No accounts match your current filters. "
        "Try widening the filters or raising the coverage threshold."
    )
else:
    state_phrase = f"{num_states} state" if num_states == 1 else f"{num_states} states"
    if coverage_threshold is not None:
        threshold_phrase = f"coverage below {coverage_threshold}%"
    else:
        threshold_phrase = "state-specific coverage thresholds"
    summary = (
        f"You need **{total_units} {item_name}** across **{state_phrase}** "
        f"based on your filters. "
        f"({total_accounts} qualifying account{'s' if total_accounts != 1 else ''} "
        f"with {threshold_phrase})"
    )

st.info(summary, icon="📊")

# ── KPI row ────────────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)
col1.metric("Total Qualifying Accounts", total_accounts)
col2.metric(f"Total {item_name} to Order", total_units)
col3.metric("States Affected", num_states)

st.divider()

# ── Main content ───────────────────────────────────────────────────────────────

if total_accounts == 0:
    st.warning("No data to display. Adjust your filters.")
else:
    col_table, col_chart = st.columns([1, 1], gap="large")

    with col_table:
        st.subheader("Units to Order per State")
        st.dataframe(
            by_state,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Units to Order": st.column_config.NumberColumn(format="%d"),
                "Qualifying Accounts": st.column_config.NumberColumn(format="%d"),
            },
        )

    with col_chart:
        st.subheader("Bar Chart — Units by State")
        chart_data = by_state.set_index("State")["Units to Order"]
        st.bar_chart(chart_data, use_container_width=True, color="#E8393C")

    st.divider()

    with st.expander("View Account-Level Detail"):
        detail_cols = [
            "account_id", "account_name", "state",
            "trade_channel", "account_type", "premise_type",
            "store_volume", "current_coverage_pct", "units_needed",
        ]
        st.dataframe(
            df[detail_cols].rename(columns={
                "account_id": "ID",
                "account_name": "Account",
                "state": "State",
                "trade_channel": "Channel",
                "account_type": "Type",
                "premise_type": "Premise",
                "store_volume": "Store Volume",
                "current_coverage_pct": "Coverage %",
                "units_needed": "Units Needed",
            }).sort_values(["State", "Account"]),
            use_container_width=True,
            hide_index=True,
        )
