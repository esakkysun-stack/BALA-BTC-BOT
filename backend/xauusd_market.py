"""XAUUSD live market-data adapter for the BALA paper-trading dashboard.

Primary source: XAUS public XAU/USD spot API (no key required).
Fallback: Twelve Data when TWELVE_DATA_API_KEY is configured.
No credentials are stored in the repository.

This is market-data only. BALA execution remains PAPER_ONLY.
"""

import os
import requests

XAUS_URL = "https://xaus.com/api/v1/spot"
TWELVE_URL = "https://api.twelvedata.com/quote"


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _xaus_price():
    r = requests.get(
        XAUS_URL,
        params={"currency": "USD", "unit": "oz", "compact": "1"},
        headers={"User-Agent": "BALA-Trading-Control-Center/1.0"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    state = data.get("data_state") or {}
    price = data.get("spot_usd_oz")
    if price is None:
        price = (data.get("xau") or {}).get("price")
    if price is None:
        raise RuntimeError(f"XAUS returned no XAU/USD price: {data}")
    return {
        "connected": True,
        "symbol": "XAUUSD",
        "price": float(price),
        "open": None,
        "high": None,
        "low": None,
        "previous_close": None,
        "change": None,
        "percent_change": None,
        "timestamp": data.get("price_as_of") or data.get("updated_at"),
        "source": "XAUS XAU/USD spot",
        "source_type": "spot",
        "data_state": state,
        "stale": bool(data.get("stale", False)),
    }


def _twelve_price():
    key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not key:
        return None
    r = requests.get(
        TWELVE_URL,
        params={"symbol": "XAU/USD", "apikey": key, "dp": 5},
        headers={"User-Agent": "BALA-Trading-Control-Center/1.0"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") == "error" or "code" in data:
        raise RuntimeError(data.get("message") or str(data))
    price = data.get("close") or data.get("price")
    if price is None:
        raise RuntimeError(f"Twelve Data returned no XAU/USD price: {data}")
    return {
        "connected": True,
        "symbol": "XAUUSD",
        "price": float(price),
        "open": _num(data.get("open")),
        "high": _num(data.get("high")),
        "low": _num(data.get("low")),
        "previous_close": _num(data.get("previous_close")),
        "change": _num(data.get("change")),
        "percent_change": _num(data.get("percent_change")),
        "timestamp": data.get("timestamp") or data.get("datetime"),
        "source": "Twelve Data XAU/USD",
        "source_type": "spot",
    }


def get_xauusd_snapshot():
    errors = []
    try:
        return _xaus_price()
    except Exception as exc:
        errors.append(f"XAUS: {exc}")

    try:
        twelve = _twelve_price()
        if twelve:
            twelve["fallback_error"] = errors
            return twelve
    except Exception as exc:
        errors.append(f"Twelve Data: {exc}")

    return {
        "connected": False,
        "symbol": "XAUUSD",
        "price": None,
        "source": "XAUUSD",
        "error": " | ".join(errors),
    }
