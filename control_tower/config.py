"""
Configuration for Smart Ordering Control Tower.
Edit this file to adjust default items, segment attributes, and thresholds.
"""

# ---------------------------------------------------------------------------
# Default point-of-sale items available for ordering
# ---------------------------------------------------------------------------
DEFAULT_ITEMS = [
    "Pole Toppers",
    "Shelf Talkers",
    "Case Cards",
    "Display Units",
    "Cooler Decals",
]

# ---------------------------------------------------------------------------
# Coverage threshold defaults
# ---------------------------------------------------------------------------
DEFAULT_COVERAGE_THRESHOLD = 0.5   # 50%
MIN_COVERAGE_THRESHOLD = 0.05      # 5%
MAX_COVERAGE_THRESHOLD = 1.0       # 100%
THRESHOLD_STEP = 0.05

# ---------------------------------------------------------------------------
# Canonical column names the app expects internally.
# data_loader.py maps raw upload columns to these names.
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS = {
    "retailer_cd": ["RETAILER_CD", "retailer_cd", "RetailerCode", "Retailer_Code"],
    "retailer_nm": ["RETAILER_NM", "retailer_nm", "RetailerName", "Retailer_Name", "Store_Name"],
    "address_desc": ["ADDRESS_DESC", "address_desc", "Address", "ADDRESS"],
    "city_desc": ["CITY_DESC", "city_desc", "City", "CITY"],
    "state_cd": ["STATE_CD", "state_cd", "State", "STATE", "ST"],
    "premise_typ_desc": [
        "PREMISE_TYP_DESC", "premise_typ_desc", "Premise_Type",
        "PremiseType", "Premise Type",
    ],
    "trade_channel_desc": [
        "TRADE_CHANNEL_DESC", "trade_channel_desc", "Trade_Channel",
        "TradeChannel", "Trade Channel",
    ],
    "sub_channel_alt_desc": [
        "SUB_CHANNEL_ALT_DESC", "sub_channel_alt_desc", "Sub_Channel",
        "SubChannel", "Sub Channel",
    ],
    "chain_ind_cd": [
        "CHAIN_IND_CD", "chain_ind_cd", "Chain_Ind", "ChainInd",
        "Chain Indicator",
    ],
    "liquor_fg": ["LIQUOR_FG", "liquor_fg", "Liquor", "LIQUOR"],
    "wine_fg": ["WINE_FG", "wine_fg", "Wine", "WINE"],
    "beer_fg": ["BEER_FG", "beer_fg", "Beer", "BEER"],
    "food_type_desc": [
        "FOOD_TYPE_DESC", "food_type_desc", "Food_Type", "FoodType", "Food Type",
    ],
    "store_volume_desc": [
        "STORE_VOLUME_DESC", "store_volume_desc", "Store_Volume",
        "StoreVolume", "Store Volume",
    ],
    "weekly_volume_dollars": [
        "WEEKLY_VOLUME_DOLLARS", "weekly_volume_dollars",
        "Weekly_Volume", "WeeklyVolume",
    ],
    "selling_space_sqr_feet": [
        "SELLING_SPACE_SQR_FEET", "selling_space_sqr_feet",
        "Selling_Space", "SellingSpace",
    ],
}

# ---------------------------------------------------------------------------
# Filter dimension configuration
# Key  = internal canonical column name
# Label = human-readable label shown in UI
# ---------------------------------------------------------------------------
FILTER_DIMENSIONS = {
    "premise_typ_desc": "Premise Type",
    "trade_channel_desc": "Trade Channel",
    "sub_channel_alt_desc": "Sub-Channel",
    "chain_ind_cd": "Chain / Independent",
    "state_cd": "State(s)",
    "liquor_fg": "Liquor License",
    "wine_fg": "Wine License",
    "beer_fg": "Beer License",
    "food_type_desc": "Food Type",
}

# Chain indicator human-readable mapping
CHAIN_IND_LABELS = {
    "C": "Chain",
    "I": "Independent",
}

# ---------------------------------------------------------------------------
# Claude model settings
# ---------------------------------------------------------------------------
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 1024

# System prompt used by the AI agent
AI_SYSTEM_PROMPT = """You are an expert trade marketing analyst assistant embedded in a Smart Ordering Control Tower.
Your job is to help trade marketers understand their retail account data and calculate POS (point-of-sale) material ordering quantities.

When given a user question and data context, respond with a valid JSON object (no markdown, no code fences) with this exact schema:
{
  "intent": "<filter|calculate|question|export>",
  "filters": {
    "premise_typ_desc": [],
    "trade_channel_desc": [],
    "sub_channel_alt_desc": [],
    "chain_ind_cd": [],
    "state_cd": [],
    "liquor_fg": [],
    "wine_fg": [],
    "beer_fg": [],
    "food_type_desc": []
  },
  "item": "<item name or null>",
  "threshold": <float 0.0-1.0 or null>,
  "answer": "<plain English response to the user>"
}

Rules:
- intent=filter: user wants to see a filtered subset of accounts
- intent=calculate: user wants to calculate units to order
- intent=question: user is asking a data question (counts, breakdowns, etc.)
- intent=export: user wants to download data
- Populate filters only when the user explicitly mentions filter criteria. Leave arrays empty [] when no filter applies.
- threshold: only set if user mentions a percentage or coverage level; otherwise null
- item: only set if user mentions a specific POS item; otherwise null
- answer: always provide a helpful plain English response

Data context will be provided in the user message."""

# ---------------------------------------------------------------------------
# Sample data generation settings (used when no file is uploaded)
# ---------------------------------------------------------------------------
SAMPLE_ROW_COUNT = 20

SAMPLE_STATES = ["CA", "TX", "FL", "NY", "IL", "OH", "PA", "GA", "NC", "MI"]
SAMPLE_PREMISE_TYPES = ["Off-Premise", "On-Premise"]
SAMPLE_TRADE_CHANNELS = [
    "Mass Merchandiser",
    "Cigarette Outlet",
    "Category Killer",
    "Grocery",
    "Convenience",
    "Drug",
    "Club",
    "Liquor Store",
]
SAMPLE_SUB_CHANNELS = [
    "Department Store",
    "Dollar Store",
    "Conventional Cigarette Outlet",
    "Superstore",
    "Traditional Grocery",
    "Specialty Drug",
    "Warehouse Club",
]
SAMPLE_FOOD_TYPES = ["Full Menu", "Limited Menu", "Bar Only", "No Food", "Snacks Only"]
SAMPLE_STORE_VOLUMES = ["High", "Medium", "Low"]
