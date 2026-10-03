"""Kotak Neo market-data adapter for the BALA control center.

Uses Kotak Neo's current Python SDK (v3.x) quote API for market snapshots.
MCX Gold Mini and Crude Oil contracts are resolved automatically from the
current scrip master, so the dashboard does not need hard-coded daily tokens.
No order-placement code lives in this module.
"""
import os
from datetime import datetime, timezone
from typing import Any

from neo_api_client import NeoAPI


def _consumer_key() -> str:
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


def _expiry_timestamp(row: dict) -> float:
    """Return a comparable expiry timestamp; unknown expiry sorts last."""
    for key in ("pExpiryDate", "pMaturityDate"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            for fmt in ("%d-%b-%Y", "%d%b%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    pass
    value = _as_float(row.get("lExpiryDate"))
    if value and value > 0:
        return value / 1000 if value > 10_000_000_000 else value
    return float("inf")


def _quote(client: NeoAPI, token: str, segment: str = "nse_cm"):
    response = client.quotes(
        instrument_tokens=[{"instrument_token": str(token), "exchange_segment": segment}],
        quote_type="all",
    )
    if isinstance(response, dict) and response.get("stat") == "Not_Ok":
        return {"name": str(token), "error": str(response)}
    rows = response.get("data", response) if isinstance(response, dict) else response
    if not rows:
        return {"name": str(token), "error": "No quote returned"}
    row = rows[0] if isinstance(rows, list) else rows
    return {
        "name": str(token),
        "segment": segment,
        "price": _as_float(row.get("ltp") or row.get("last_traded_price")),
        "change": _as_float(row.get("change")),
        "percent_change": _as_float(row.get("per_change") or row.get("percent_change")),
        "volume": row.get("last_volume") or row.get("volume"),
        "display_symbol": row.get("display_symbol"),
        "raw": row,
    }


def _resolve_mcx_futures(client: NeoAPI, aliases: tuple[str, ...]):
    """Resolve the nearest current MCX futures contract for an underlying."""
    candidates = []
    errors = []
    for symbol in aliases:
        try:
            rows = client.search_scrip(
                exchange_segment="mcx_fo",
                symbol=symbol,
                expiry="",
                option_type="FUT",
                strike_price="",
                ignore_50multiple=True,
            )
            if isinstance(rows, dict):
                rows = rows.get("data", rows.get("scrips", []))
            if isinstance(rows, list):
                candidates.extend(r for r in rows if isinstance(r, dict))
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    today = datetime.now(timezone.utc).timestamp()
    valid = []
    for row in candidates:
        expiry = _expiry_timestamp(row)
        if expiry == float("inf") or expiry >= today:
            token = row.get("pSymbol") or row.get("instrument_token")
            if token:
                valid.append((expiry, str(token), row))

    if not valid:
        return None, ("; ".join(errors) if errors else "MCX futures contract not found")

    valid.sort(key=lambda x: x[0])
    expiry, token, row = valid[0]
    return {
        "token": token,
        "trading_symbol": row.get("pTrdSymbol") or row.get("trading_symbol"),
        "underlying": row.get("pSymbolName"),
        "expiry": row.get("pExpiryDate"),
        "expiry_timestamp": None if expiry == float("inf") else expiry,
    }, None


def get_kotak_snapshot() -> dict:
    key = _consumer_key()
    if not key:
        return {
            "connected": False,
            "source": "Kotak Neo",
            "error": "KOTAK_CONSUMER_KEY secret is missing",
        }

    client = NeoAPI(consumer_key=key, environment="prod")
    markets = {}
    errors = []

    # Current Kotak quote API supports these index names directly.
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

    # Daily contract tokens can be supplied as secrets, but normally we resolve
    # the nearest active contract automatically from Kotak's MCX scrip master.
    mcx = {
        "GOLD MINI": ("KOTAK_GOLD_MINI_TOKEN", ("GOLDM", "GOLD MINI", "GOLDM-FUT")),
        "CRUDE OIL": ("KOTAK_CRUDE_OIL_TOKEN", ("CRUDEOIL", "CRUDE OIL", "CRUDEOIL-FUT")),
    }

    for label, (secret_name, aliases) in mcx.items():
        token = os.getenv(secret_name, "").strip()
        resolved = None
        if not token:
            resolved, resolve_error = _resolve_mcx_futures(client, aliases)
            if resolved:
                token = resolved["token"]
            else:
                markets[label] = {
                    "name": label,
                    "status": "contract_not_resolved",
                    "error": resolve_error,
                }
                errors.append(f"{label}: {resolve_error}")
                continue

        try:
            quote = _quote(client, token, "mcx_fo")
            if resolved:
                quote["contract"] = resolved
            markets[label] = quote
            if quote.get("error"):
                errors.append(f"{label}: {quote['error']}")
        except Exception as exc:
            markets[label] = {"name": label, "error": str(exc)}
            errors.append(f"{label}: {exc}")

    prices = [m.get("price") for m in markets.values() if isinstance(m, dict)]
    return {
        "connected": any(p is not None for p in prices),
        "source": "Kotak Neo Trade API",
        "markets": markets,
        "errors": errors,
    }
