# Smart Ordering Control Tower

A conversational interface for trade marketers to calculate POS material order quantities from retail account data.

## Quick Start

```bash
cd control_tower
pip install -r requirements.txt
streamlit run app.py
```

Set your Anthropic API key in the sidebar, or via environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

## Features

| Feature | Description |
|---|---|
| **Chat Interface** | Ask natural-language questions about your data |
| **File Upload** | Upload CSV or Excel retail account datasets |
| **Smart Filters** | Filter by premise type, trade channel, state, license type, and more |
| **Order Calculator** | Set coverage threshold → auto-calculate units per state |
| **Charts** | Bar charts for units to order and account counts by state |
| **Export** | Download Excel (3-sheet) or CSV |

## File Structure

```
control_tower/
├── app.py               Main Streamlit UI
├── config.py            Items, thresholds, column mappings, AI prompt
├── data_loader.py       File upload, schema mapping, sample data
├── data_connector.py    Phase 2 stubs: Snowflake & REST API
├── query_engine.py      Pandas filtering, aggregation, data context
├── ai_agent.py          Claude API integration + rule-based fallback
├── order_calculator.py  Coverage threshold → units calculation
├── output_generator.py  Excel (3-sheet) and CSV generation
└── requirements.txt
```

## Expected Data Schema

| Column | Description |
|---|---|
| `RETAILER_CD` | Unique account identifier |
| `RETAILER_NM` | Store name |
| `STATE_CD` | 2-letter state code |
| `PREMISE_TYP_DESC` | Off-Premise / On-Premise |
| `TRADE_CHANNEL_DESC` | e.g. Mass Merchandiser, Grocery |
| `SUB_CHANNEL_ALT_DESC` | e.g. Dollar Store, Superstore |
| `CHAIN_IND_CD` | C = Chain, I = Independent |
| `LIQUOR_FG / WINE_FG / BEER_FG` | Y/N license flags |
| `FOOD_TYPE_DESC` | Full Menu, Bar Only, etc. |
| `STORE_VOLUME_DESC` | High / Medium / Low |

Column names are matched flexibly — variations like `State`, `ST`, `Store_Name` are all recognised automatically.

## Coverage Threshold Formula

```
units_per_state = ROUNDUP(account_count × coverage_threshold)
total_units     = SUM(units_per_state across all states)
```

Example: 120 accounts in Texas at 50% coverage → ROUNDUP(60) = 60 units.

## Phase 2: Live Data Connections

Edit `data_connector.py` to wire up:

- **Snowflake**: implement `connect_snowflake(config)` using `snowflake-connector-python`
- **REST API**: implement `connect_rest_api(endpoint, headers)` using `requests`

Both stubs return `pd.DataFrame` with the same canonical column schema used throughout the app.

## AI Fallback

If no API key is provided or the Claude API is unavailable, the app automatically falls back to a rule-based engine (`query_engine.rule_based_answer`) that handles common questions about state counts, channel breakdowns, and totals without any API calls.
