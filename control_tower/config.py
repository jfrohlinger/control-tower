"""
config.py — Default items, segment attributes, thresholds, and app-wide settings.
Edit this file to customize the application without touching logic modules.
"""

# ── Model ──────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Default POS / display items available for ordering ────────────────────────
DEFAULT_ITEMS: list[str] = [
    "Pole Toppers",
    "Shelf Talkers",
    "Case Cards",
    "Display Units",
    "Cooler Decals",
]

# ── Coverage threshold defaults ────────────────────────────────────────────────
DEFAULT_THRESHOLD: float = 0.5          # 50 %
MIN_THRESHOLD: float = 0.05            # 5 %
MAX_THRESHOLD: float = 1.0             # 100 %
THRESHOLD_STEP: float = 0.05

# ── Segment filter dimensions ─────────────────────────────────────────────────
SEGMENT_DIMENSIONS: list[str] = [
    "PREMISE_TYP_DESC",
    "TRADE_CHANNEL_DESC",
    "SUB_CHANNEL_ALT_DESC",
    "CHAIN_IND_CD",
    "STATE_CD",
    "LIQUOR_FG",
    "WINE_FG",
    "BEER_FG",
    "FOOD_TYPE_DESC",
]

# Human-readable labels for filter dimensions
DIMENSION_LABELS: dict[str, str] = {
    "PREMISE_TYP_DESC":    "Premise Type",
    "TRADE_CHANNEL_DESC":  "Trade Channel",
    "SUB_CHANNEL_ALT_DESC": "Sub-Channel",
    "CHAIN_IND_CD":        "Chain / Independent",
    "STATE_CD":            "State(s)",
    "LIQUOR_FG":           "Liquor License",
    "WINE_FG":             "Wine License",
    "BEER_FG":             "Beer License",
    "FOOD_TYPE_DESC":      "Food Type",
}

# ── Canonical column schema ────────────────────────────────────────────────────
# Maps normalised column names → list of plausible raw header variants.
# data_loader.py uses this to remap columns from user-uploaded files.
COLUMN_ALIASES: dict[str, list[str]] = {
    "RETAILER_CD":          ["retailer_cd", "retailer_code", "store_code", "account_code", "acct_cd"],
    "RETAILER_NM":          ["retailer_nm", "retailer_name", "store_name", "account_name", "acct_nm"],
    "ADDRESS_DESC":         ["address_desc", "address", "addr", "street"],
    "CITY_DESC":            ["city_desc", "city"],
    "STATE_CD":             ["state_cd", "state_code", "state"],
    "PREMISE_TYP_DESC":     ["premise_typ_desc", "premise_type", "premise"],
    "TRADE_CHANNEL_DESC":   ["trade_channel_desc", "trade_channel", "channel"],
    "SUB_CHANNEL_ALT_DESC": ["sub_channel_alt_desc", "sub_channel", "subchannel"],
    "CHAIN_IND_CD":         ["chain_ind_cd", "chain_indicator", "chain_ind", "chain"],
    "LIQUOR_FG":            ["liquor_fg", "liquor_flag", "liquor"],
    "WINE_FG":              ["wine_fg", "wine_flag", "wine"],
    "BEER_FG":              ["beer_fg", "beer_flag", "beer"],
    "FOOD_TYPE_DESC":       ["food_type_desc", "food_type", "food"],
    "STORE_VOLUME_DESC":    ["store_volume_desc", "store_volume", "volume"],
    "WEEKLY_VOLUME_DOLLARS":["weekly_volume_dollars", "weekly_volume", "weekly_sales"],
    "SELLING_SPACE_SQR_FEET": ["selling_space_sqr_feet", "selling_space", "sq_feet", "sqft"],
}

# ── Sample data (used when no file is uploaded) ────────────────────────────────
SAMPLE_DATA_ROWS: int = 20

# ── UI strings ─────────────────────────────────────────────────────────────────
APP_TITLE = "Smart Ordering Control Tower"
APP_ICON  = "🏪"
WELCOME_MESSAGE = (
    "Welcome to the **Smart Ordering Control Tower**! 👋\n\n"
    "Upload your retail account dataset in the sidebar, then ask me anything — "
    "for example:\n"
    "- *\"Which states need the most Pole Toppers?\"*\n"
    "- *\"Show me Off-Premise chains in Texas with a beer license\"*\n"
    "- *\"Calculate units to order for Shelf Talkers at 60% coverage\"*\n\n"
    "I can filter accounts, calculate order quantities, show charts, and export results."
)
