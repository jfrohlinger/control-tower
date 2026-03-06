"""
ai_agent.py
Claude API integration — interprets user questions and returns structured plans.
Falls back to rule-based logic if the API is unavailable.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic
import pandas as pd

from config import (
    AI_SYSTEM_PROMPT,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    DEFAULT_COVERAGE_THRESHOLD,
    FILTER_DIMENSIONS,
)
from query_engine import build_data_context, rule_based_answer


# ---------------------------------------------------------------------------
# Plan schema defaults (mirrors the JSON schema in AI_SYSTEM_PROMPT)
# ---------------------------------------------------------------------------

def _empty_plan() -> dict[str, Any]:
    return {
        "intent": "question",
        "filters": {col: [] for col in FILTER_DIMENSIONS},
        "item": None,
        "threshold": None,
        "answer": "",
    }


def _merge_plan(base: dict[str, Any], partial: dict[str, Any]) -> dict[str, Any]:
    """Merge a partial plan from Claude into a complete plan with defaults."""
    plan = _empty_plan()

    plan["intent"] = partial.get("intent", base["intent"])
    plan["item"] = partial.get("item", base["item"])
    plan["threshold"] = partial.get("threshold", base["threshold"])
    plan["answer"] = partial.get("answer", base["answer"])

    # Merge filters carefully
    raw_filters = partial.get("filters", {})
    if isinstance(raw_filters, dict):
        for col in FILTER_DIMENSIONS:
            val = raw_filters.get(col, [])
            if isinstance(val, list):
                plan["filters"][col] = val
            elif val:
                plan["filters"][col] = [str(val)]

    return plan


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret_question(
    question: str,
    df: pd.DataFrame,
    current_filters: dict[str, list[str]] | None = None,
    current_item: str | None = None,
    current_threshold: float | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Send the user's question to Claude and return a structured plan.

    Parameters
    ----------
    question : str          — raw user input
    df : pd.DataFrame       — current (unfiltered) dataset
    current_filters : dict  — filters already active in the sidebar
    current_item : str      — POS item currently selected
    current_threshold : float — coverage threshold currently set
    api_key : str           — Anthropic API key (falls back to ANTHROPIC_API_KEY env var)

    Returns
    -------
    dict with keys: intent, filters, item, threshold, answer
    """
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    if not resolved_key:
        # No key — use rule-based fallback immediately
        plan = rule_based_answer(question, df)
        plan["answer"] = (
            "[No API key configured — using rule-based mode]\n\n" + plan["answer"]
        )
        return plan

    context = build_data_context(df)
    user_message = _build_user_message(
        question, context, current_filters, current_item, current_threshold
    )

    try:
        client = anthropic.Anthropic(api_key=resolved_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=AI_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = message.content[0].text.strip()
        return _parse_claude_response(raw_text)

    except anthropic.AuthenticationError:
        plan = rule_based_answer(question, df)
        plan["answer"] = (
            "[API key is invalid — using rule-based mode]\n\n" + plan["answer"]
        )
        return plan

    except anthropic.RateLimitError:
        plan = rule_based_answer(question, df)
        plan["answer"] = (
            "[Rate limit reached — using rule-based mode]\n\n" + plan["answer"]
        )
        return plan

    except Exception as exc:
        plan = rule_based_answer(question, df)
        plan["answer"] = (
            f"[Claude API error ({type(exc).__name__}) — using rule-based mode]\n\n"
            + plan["answer"]
        )
        return plan


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_user_message(
    question: str,
    context: dict[str, Any],
    current_filters: dict[str, list[str]] | None,
    current_item: str | None,
    current_threshold: float | None,
) -> str:
    parts = [f"User question: {question}", ""]

    parts.append(f"Dataset: {context['total_rows']:,} total rows")
    parts.append(f"Columns: {', '.join(context['columns'])}")
    parts.append("")

    parts.append("Available filter values:")
    for col, vals in context.get("filter_options", {}).items():
        label = FILTER_DIMENSIONS.get(col, col)
        if isinstance(vals, list):
            parts.append(f"  {label}: {', '.join(vals[:30])}")
        else:
            parts.append(f"  {label}: {vals}")

    parts.append("")
    if current_filters:
        active = {k: v for k, v in current_filters.items() if v}
        if active:
            parts.append(f"Currently active filters: {json.dumps(active)}")
    if current_item:
        parts.append(f"Currently selected item: {current_item}")
    if current_threshold is not None:
        parts.append(f"Currently set threshold: {current_threshold:.0%}")

    return "\n".join(parts)


def _parse_claude_response(raw: str) -> dict[str, Any]:
    """
    Extract JSON from Claude's response.
    Claude is instructed to return raw JSON, but we handle code-fence wrapping too.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Try to find a JSON object
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)

    try:
        partial = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            **_empty_plan(),
            "answer": (
                f"I understood your question but had trouble formatting the response. "
                f"Raw response: {raw[:300]}"
            ),
        }

    return _merge_plan(_empty_plan(), partial)
