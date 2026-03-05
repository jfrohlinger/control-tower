"""
ai_agent.py — Claude API integration.

Sends the user's natural-language question + data context to Claude and
parses the returned structured JSON plan so the app can act on it.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import anthropic

from config import CLAUDE_MODEL, DEFAULT_ITEMS, SEGMENT_DIMENSIONS


# ── Client ──────────────────────────────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    """Return an Anthropic client. Reads ANTHROPIC_API_KEY from the environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Add it to your environment or a .env file."
        )
    return anthropic.Anthropic(api_key=api_key)


# ── System prompt ───────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an intelligent assistant embedded inside the Smart Ordering Control Tower,
a tool used by trade marketers to manage retail account data and calculate POS item orders.

When the user asks a question you MUST reply with ONLY a valid JSON object — no extra prose,
no markdown fences. The JSON must have this exact shape:

{
  "intent":    "<filter | calculate | question | export>",
  "filters":   { "<COLUMN_NAME>": "<value_or_list>" },
  "item":      "<POS item name or null>",
  "threshold": <float 0.0-1.0 or null>,
  "answer":    "<plain English response to show the user>"
}

Intent meanings
---------------
- "filter"    : The user wants to subset accounts by segment criteria.
- "calculate" : The user wants to compute units to order per state.
- "question"  : The user is asking a general data question (top states, breakdown, etc.).
- "export"    : The user wants to download results.

Filter rules
------------
- Only include filters the user explicitly requested.
- Use exact column names from the schema (STATE_CD, PREMISE_TYP_DESC, etc.).
- For list values, use a JSON array: ["CA", "TX"].
- Flag columns (LIQUOR_FG, WINE_FG, BEER_FG) use "Y" or "N".
- CHAIN_IND_CD uses "C" for Chain or "I" for Independent.

Item & threshold
----------------
- "item" must be one of the known POS items or null if not applicable.
- "threshold" is a decimal fraction (e.g. 0.5 for 50 %) or null.

Answer field
------------
- Write a short, friendly, plain-English explanation of what the system is about to do.
- Do not repeat raw JSON in the answer.
- If you cannot determine the intent, set intent to "question" and explain in "answer".
"""


# ── Main entry point ────────────────────────────────────────────────────────────

def interpret_question(
    question: str,
    data_context: dict[str, Any],
    chat_history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    Send the user question to Claude and return a parsed plan dict.

    Falls back to a rule-based plan if the API call fails.

    Parameters
    ----------
    question     : The user's raw natural-language input.
    data_context : Output of data_loader.get_data_context() — row count,
                   columns, and unique filter values.
    chat_history : Optional list of {"role": "user"|"assistant", "content": str}
                   to provide multi-turn context.

    Returns
    -------
    dict with keys: intent, filters, item, threshold, answer
    """
    context_summary = _build_context_block(data_context)
    user_message = f"{context_summary}\n\nUser question: {question}"

    messages: list[dict] = []
    if chat_history:
        # Include prior turns (capped to last 10 to keep prompt short)
        for turn in chat_history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        raw_text = response.content[0].text.strip()
        plan = _parse_json_response(raw_text)
        return plan

    except EnvironmentError as exc:
        return _fallback_plan(question, str(exc))
    except anthropic.APIError as exc:
        return _fallback_plan(question, f"Claude API error: {exc}")
    except Exception as exc:
        return _fallback_plan(question, f"Unexpected error: {exc}")


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _build_context_block(ctx: dict[str, Any]) -> str:
    """Serialise the data context into a concise text block."""
    lines = [
        f"Dataset: {ctx.get('row_count', '?')} accounts",
        f"Columns: {', '.join(ctx.get('columns', []))}",
        f"Available POS items: {', '.join(DEFAULT_ITEMS)}",
        "Filterable dimensions and their unique values:",
    ]
    for col in SEGMENT_DIMENSIONS:
        vals = ctx.get("unique_values", {}).get(col, [])
        if vals:
            display = vals if len(vals) <= 15 else vals[:15] + ["..."]
            lines.append(f"  {col}: {display}")
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract and parse the JSON object from Claude's response."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Find the outermost { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    plan = json.loads(text)

    # Normalise / fill in defaults
    plan.setdefault("intent", "question")
    plan.setdefault("filters", {})
    plan.setdefault("item", None)
    plan.setdefault("threshold", None)
    plan.setdefault("answer", "")

    # Clamp threshold to [0, 1]
    if plan["threshold"] is not None:
        plan["threshold"] = max(0.0, min(1.0, float(plan["threshold"])))

    return plan


def _fallback_plan(question: str, error_detail: str) -> dict[str, Any]:
    """
    Rule-based fallback plan used when Claude is unavailable.
    Performs simple keyword matching to guess intent.
    """
    q = question.lower()
    intent = "question"
    filters: dict[str, Any] = {}
    item: Optional[str] = None
    threshold: Optional[float] = None

    # Detect item
    for pos_item in DEFAULT_ITEMS:
        if pos_item.lower() in q:
            item = pos_item
            break

    # Detect intent
    if any(word in q for word in ["order", "calculat", "units", "coverage", "threshold"]):
        intent = "calculate"
    elif any(word in q for word in ["filter", "show", "find", "list", "which", "select"]):
        intent = "filter"
    elif any(word in q for word in ["download", "export", "excel", "csv"]):
        intent = "export"

    # Detect simple state filter
    import re as _re
    state_match = _re.findall(r'\b([A-Z]{2})\b', question)
    if state_match:
        from config import COLUMN_ALIASES
        # Only include if they look like US state codes (rough heuristic)
        known_states = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
                        "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
                        "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
                        "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"}
        matched_states = [s for s in state_match if s in known_states]
        if matched_states:
            filters["STATE_CD"] = matched_states if len(matched_states) > 1 else matched_states[0]

    # Detect threshold
    pct_match = _re.search(r'(\d+)\s*%', question)
    if pct_match:
        threshold = int(pct_match.group(1)) / 100.0

    answer = (
        f"*(Claude API unavailable — {error_detail})*\n\n"
        "I'll use rule-based filtering based on keywords in your question. "
        "Results may be less precise than when AI is available."
    )

    return {
        "intent":    intent,
        "filters":   filters,
        "item":      item,
        "threshold": threshold,
        "answer":    answer,
    }
