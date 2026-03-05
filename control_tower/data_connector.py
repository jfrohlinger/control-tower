"""
data_connector.py — Phase 2 placeholder for live data source connections.

These stub functions document the interface a developer needs to implement
to wire up Snowflake, REST APIs, or other live data sources.
The application falls back to file upload / sample data until these are wired.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ── Snowflake connector ────────────────────────────────────────────────────────

def connect_snowflake(config: dict[str, Any]) -> pd.DataFrame:
    """
    Connect to Snowflake and return the retailer account dataset as a DataFrame.

    Parameters
    ----------
    config : dict with keys:
        - account   : str   — Snowflake account identifier (e.g. "xy12345.us-east-1")
        - user      : str   — Snowflake username
        - password  : str   — Snowflake password (prefer env-var / secrets manager)
        - warehouse : str   — Virtual warehouse name
        - database  : str   — Database name
        - schema    : str   — Schema name
        - table     : str   — Fully-qualified table or view to query
        - query     : str   — (Optional) Override with a custom SQL SELECT statement

    Returns
    -------
    pd.DataFrame  — Dataset with canonical column names expected by the app.

    Implementation notes
    --------------------
    1. Install the Snowflake connector:
           pip install snowflake-connector-python[pandas]

    2. Wire up like this:

        import snowflake.connector

        conn = snowflake.connector.connect(
            account=config["account"],
            user=config["user"],
            password=config["password"],
            warehouse=config["warehouse"],
            database=config["database"],
            schema=config["schema"],
        )

        query = config.get(
            "query",
            f'SELECT * FROM {config["table"]}'
        )

        cursor = conn.cursor()
        cursor.execute(query)
        df = cursor.fetch_pandas_all()
        cursor.close()
        conn.close()
        return df

    3. Pass the returned DataFrame through data_loader._remap_columns()
       and data_loader._coerce_types() to normalise column names.
    """
    raise NotImplementedError(
        "Snowflake connector is not yet implemented. "
        "See the docstring in data_connector.connect_snowflake() for instructions."
    )


# ── REST API connector ─────────────────────────────────────────────────────────

def connect_rest_api(endpoint: str, headers: dict[str, str]) -> pd.DataFrame:
    """
    Fetch the retailer account dataset from a REST API endpoint.

    Parameters
    ----------
    endpoint : str   — Full URL, e.g. "https://api.example.com/v1/retailer-accounts"
    headers  : dict  — HTTP headers, e.g. {"Authorization": "Bearer <token>",
                                            "Accept": "application/json"}

    Returns
    -------
    pd.DataFrame  — Dataset with canonical column names expected by the app.

    Implementation notes
    --------------------
    1. Install requests if not already present:
           pip install requests

    2. Wire up like this:

        import requests

        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Adapt to your API's response shape:
        #   - Flat list of records → pd.DataFrame(data)
        #   - Nested             → pd.DataFrame(data["results"])
        df = pd.DataFrame(data)
        return df

    3. For paginated APIs, loop over pages and pd.concat() the results.

    4. Pass the returned DataFrame through data_loader._remap_columns()
       and data_loader._coerce_types() to normalise column names.
    """
    raise NotImplementedError(
        "REST API connector is not yet implemented. "
        "See the docstring in data_connector.connect_rest_api() for instructions."
    )


# ── Google BigQuery connector (bonus stub) ─────────────────────────────────────

def connect_bigquery(project_id: str, query: str) -> pd.DataFrame:
    """
    Execute a BigQuery SQL query and return results as a DataFrame.

    Parameters
    ----------
    project_id : str — GCP project ID
    query      : str — Standard SQL SELECT statement

    Implementation notes
    --------------------
    pip install google-cloud-bigquery[pandas]

    from google.cloud import bigquery
    client = bigquery.Client(project=project_id)
    df = client.query(query).to_dataframe()
    return df
    """
    raise NotImplementedError(
        "BigQuery connector is not yet implemented. "
        "See the docstring in data_connector.connect_bigquery() for instructions."
    )
