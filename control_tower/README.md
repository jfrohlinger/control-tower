# Smart Ordering Control Tower

A non-technical-friendly chat interface for trade marketers to manage retail account data and calculate POS item orders by state.

## Features

- **Chat interface** — Ask natural-language questions about your data
- **File upload** — CSV or Excel with flexible column-name mapping
- **Segment filtering** — Filter by Premise Type, Trade Channel, Sub-Channel, Chain/Independent, State, License Type, Food Type
- **Order calculation** — Set a coverage threshold → get units to order per state (ROUNDUP formula)
- **Results views** — Plain-English summary, data table, bar chart
- **Exports** — Excel (3 sheets) and CSV download
- **Sample data mode** — Works out of the box with 20 synthetic accounts

## Quick Start

```bash
cd control_tower
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
streamlit run app.py
```

Open the URL printed in the terminal (default: http://localhost:8501).

## File Structure

```
control_tower/
├── app.py               # Main Streamlit UI
├── config.py            # Items, dimensions, thresholds, labels
├── data_loader.py       # File parsing, column mapping, sample data
├── data_connector.py    # Live DB/API stubs (Snowflake, REST, BigQuery)
├── query_engine.py      # Pandas filtering and aggregation
├── ai_agent.py          # Claude API integration — interprets questions
├── order_calculator.py  # Coverage threshold → units per state
├── output_generator.py  # Excel / CSV generation
├── requirements.txt
└── README.md
```

## Usage

### 1. Upload Data
Upload a CSV or Excel file in the sidebar. Column names are mapped automatically (see `config.COLUMN_ALIASES`).

### 2. Chat
Type questions like:
- *"Which states have the most accounts?"*
- *"Show me Off-Premise chains in California and Texas"*
- *"Calculate Pole Toppers at 60% coverage for beer-licensed accounts"*

### 3. Filter
Use the sidebar filter panel to narrow down accounts by any segment dimension.

### 4. Calculate Order
Choose an item and coverage threshold, then click **Calculate Order** (sidebar) or ask via chat.

### 5. Download
Go to the **Download** tab and export as Excel or CSV.

## Data Schema

The application expects (and auto-maps) these columns:

| Column | Description |
|--------|-------------|
| RETAILER_CD | Unique account identifier |
| RETAILER_NM | Account / store name |
| ADDRESS_DESC | Street address |
| CITY_DESC | City |
| STATE_CD | 2-letter state code |
| PREMISE_TYP_DESC | Off-Premise / On-Premise |
| TRADE_CHANNEL_DESC | e.g. Mass Merchandiser, Grocery |
| SUB_CHANNEL_ALT_DESC | e.g. Dollar Store, Supermarket |
| CHAIN_IND_CD | C = Chain, I = Independent |
| LIQUOR_FG | Y / N |
| WINE_FG | Y / N |
| BEER_FG | Y / N |
| FOOD_TYPE_DESC | e.g. Full Service, None |
| STORE_VOLUME_DESC | Low / Medium / High / Very High |
| WEEKLY_VOLUME_DOLLARS | Numeric |
| SELLING_SPACE_SQR_FEET | Numeric |

Column names are matched case-insensitively. Common synonyms (e.g. `state` → `STATE_CD`) are handled automatically via `config.COLUMN_ALIASES`.

## Order Calculation Formula

```
units_per_state = ROUNDUP(account_count × coverage_threshold)
total_units     = SUM(units_per_state across all states)
```

## Configuration

Edit `config.py` to:
- Add or rename POS items (`DEFAULT_ITEMS`)
- Change default threshold (`DEFAULT_THRESHOLD`)
- Add column aliases (`COLUMN_ALIASES`)
- Swap Claude model (`CLAUDE_MODEL`)

## Wiring Live Data (Phase 2)

See `data_connector.py`. Implement the stub functions:
- `connect_snowflake(config)` → Snowflake
- `connect_rest_api(endpoint, headers)` → REST API
- `connect_bigquery(project_id, query)` → BigQuery

Then call the connector in `app.py` instead of using `st.file_uploader`.

## AI Fallback

If `ANTHROPIC_API_KEY` is missing or the API call fails, the app falls back to rule-based keyword filtering. Results will be less precise but the application remains usable.

## Requirements

- Python 3.9+
- Streamlit ≥ 1.32
- Pandas ≥ 2.0
- Anthropic Python SDK ≥ 0.40
- Plotly ≥ 5.18
- openpyxl ≥ 3.1
