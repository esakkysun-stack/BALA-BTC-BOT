"""Kotak Neo market-data adapter for the BALA control center.

Uses Kotak Neo's current Python SDK (v3.x) quote API for real-time snapshots.
No order-placement code lives in this module.
"""
import os
from typing import Any

from neo_api_client import NeoAPI


def _consumer_key() -> str:
    # Support the common secret names so the GitHub Action can be wired without
    # putting credentials into the dashboard/browser.
    return (
        os.getenv("KOTAK_CONSUMER_KEY")
        or os.getenv("KOTAK_API_KEY")
        or os.getenv("KOTAK_ACCESS_TOKEN")
        or ""
    ).strip()


def _as_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _quote(client: NeoAPI, name: str, segment: str = "nse_cm"):
    response = client.quotes(
        instrument_tokens=[
            {"instrument_token": name, "exchange_segment": segment}
        ],
        quote_type="all",
    )
    if isinstance(response, dict) and response.get("stat") == "Not_Ok":
        return {"name": name, "error": str(response)}
    rows = response.get("data", response) if isinstance(response, dict) else response
    if not rows:
        return {"name": name, "error": "No quote returned"}
    row = rows[0] if isinstance(rows, list) else rows
    return {
        "name": name,
        "segment": segment,
        "price": _as_float(row.get("ltp") or row.get("last_traded_price")),
        "change": _as_float(row.get("change")),
        "percent_change": _as_float(row.get("per_change") or row.get("percent_change")),
        "volume": row.get("last_volume") or row.get("volume"),
        "raw": row,
    }


def get_kotak_snapshot() -> dict:
    key = _consumer_key()
    if not key:
        return {"connected": False, "source": "Kotak Neo", "error": "KOTAK_CONSUMER_KEY secret is missing"}

    client = NeoAPI(consumer_key=key, environment="prod")
    markets = {}
    errors = []

    # Kotak's current API accepts index names for index quotes.
    for label, symbol, segment in [
        ("NIFTY", "Nifty 50", "nse_cm"),
        ("SENSEX", "SENSEX", "bse_cm"),
    ]:
        try:
            markets[label] = _quote(client, symbol, segment)
            if markets[label].get("error"):
                errors.append(f"{label}: {markets[label]['error']}")
        except Exception as exc:
            markets[label] = {"name": symbol, "error": str(exc)}
            errors.append(f"{label}: {exc}")

    # Optional MCX contracts can be supplied as pSymbol/instrument tokens in
    # GitHub Secrets once the exact current contract is selected.
    optional = {
        "GOLD MINI": (os.getenv("KOTAK_GOLD_MINI_TOKEN", ""), "mcx_fo"),
        "CRUDE OIL": (os.getenv("KOTAK_CRUDE_OIL_TOKEN", ""), "mcx_fo"),
    }
    for label, (token, segment) in optional.items():
        if not token:
            markets[label] = {"name": label, "status": "token_not_configured"}
            continue
        try:
            markets[label] = _quote(client, token, segment)
            if markets[label].get("error"):
                errors.append(f"{label}: {markets[label]['error']}")
        except Exception as exc:
            markets[label] = {"name": label, "error": str(exc)}
            errors.append(f"{label}: {exc}")

    return {
        "connected": not errors or any(m.get("price") is not None for m in markets.values()),
        "source": "Kotak Neo Trade API",
        "markets": markets,
        "errors": errors,
    }
