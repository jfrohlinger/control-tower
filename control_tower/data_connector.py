"""
data_connector.py
Phase 2 placeholder — stub functions for live database / API connections.

A developer wiring these up should:
1. Install the required driver (snowflake-connector-python, requests, etc.)
2. Replace the NotImplementedError bodies with real connection logic.
3. Return a pandas DataFrame with the same canonical column schema used by the app.
   See config.CANONICAL_COLUMNS for the expected column names.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Snowflake connector stub
# ---------------------------------------------------------------------------

def connect_snowflake(config: dict[str, Any]) -> pd.DataFrame:
    """
    Connect to Snowflake and return retail account data as a DataFrame.

    Parameters
    ----------
    config : dict
        Expected keys:
            account   : str  — Snowflake account identifier (e.g. "xy12345.us-east-1")
            user      : str  — Snowflake username
            password  : str  — Snowflake password (or use private_key / SSO)
            warehouse : str  — Compute warehouse name
            database  : str  — Database name
            schema    : str  — Schema name
            table     : str  — Table or view name to SELECT from
            limit     : int  — Optional row limit (default: no limit)

    Returns
    -------
    pd.DataFrame
        Data with canonical column names (see config.CANONICAL_COLUMNS).

    Example implementation (requires snowflake-connector-python)::

        import snowflake.connector
        from snowflake.connector.pandas_tools import pd_read_pandas

        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            password=config["password"],
            warehouse=config["warehouse"],
            database=config["database"],
            schema=config["schema"],
        )
        limit_clause = f"LIMIT {config['limit']}" if config.get("limit") else ""
        query = f"SELECT * FROM {config['table']} {limit_clause}"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    """
    raise NotImplementedError(
        "Snowflake connector is not yet configured. "
        "See data_connector.py for implementation instructions."
    )


# ---------------------------------------------------------------------------
# REST API connector stub
# ---------------------------------------------------------------------------

def connect_rest_api(endpoint: str, headers: dict[str, str] | None = None) -> pd.DataFrame:
    """
    Fetch retail account data from a REST API and return as a DataFrame.

    Parameters
    ----------
    endpoint : str
        Full URL of the API endpoint that returns JSON data.
        The response should be a JSON array of objects or a dict with a
        ``data`` key containing such an array.
    headers : dict, optional
        HTTP headers to include (e.g. Authorization, Content-Type).

    Returns
    -------
    pd.DataFrame
        Data with canonical column names (see config.CANONICAL_COLUMNS).

    Example implementation (requires requests)::

        import requests

        response = requests.get(endpoint, headers=headers or {}, timeout=30)
        response.raise_for_status()
        payload = response.json()

        # Handle both list and {"data": [...]} response shapes
        records = payload if isinstance(payload, list) else payload.get("data", payload)
        df = pd.DataFrame(records)
        return df
    """
    raise NotImplementedError(
        "REST API connector is not yet configured. "
        "See data_connector.py for implementation instructions."
    )


# ---------------------------------------------------------------------------
# Connection health-check helper
# ---------------------------------------------------------------------------

def test_connection(source: str, config: dict[str, Any]) -> dict[str, Any]:
    """
    Attempt to connect to a data source and return a status dict.

    Parameters
    ----------
    source : str   — "snowflake" | "rest"
    config : dict  — source-specific config (see individual connect_* functions)

    Returns
    -------
    dict with keys:
        success : bool
        message : str
        row_count : int | None
    """
    try:
        if source == "snowflake":
            df = connect_snowflake(config)
        elif source == "rest":
            df = connect_rest_api(
                config.get("endpoint", ""),
                config.get("headers"),
            )
        else:
            return {"success": False, "message": f"Unknown source: {source}", "row_count": None}

        return {
            "success": True,
            "message": f"Connected successfully. {len(df):,} rows loaded.",
            "row_count": len(df),
        }
    except NotImplementedError as exc:
        return {"success": False, "message": str(exc), "row_count": None}
    except Exception as exc:
        return {"success": False, "message": f"Connection error: {exc}", "row_count": None}
