"""XAUUSD live/near-live market-data adapter.

Primary source: Yahoo Finance chart endpoint for XAUUSD=X.
Optional higher-quality source: Twelve Data when TWELVE_DATA_API_KEY is set.
No API credentials are stored in the repository.
"""

import os
import requests

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TWELVE_URL = "https://api.twelvedata.com/price"


def _twelve_price():
    key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not key:
        return None

    r = requests.get(
        TWELVE_URL,
        params={"symbol": "XAU/USD", "apikey": key},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if "price" not in data:
        raise RuntimeError(str(data))
    return {
        "connected": True,
        "symbol": "XAU/USD",
        "price": float(data["price"]),
        "source": "Twelve Data",
        "source_type": "spot",
    }


def get_xauusd_snapshot():
    """Return the latest available XAUUSD spot quote and recent range."""
    try:
        twelve = _twelve_price()
        if twelve:
            return twelve
    except Exception as exc:
        twelve_error = str(exc)
    else:
        twelve_error = None

    symbol = os.getenv("XAUUSD_SYMBOL", "XAUUSD=X").strip() or "XAUUSD=X"
    try:
        r = requests.get(
            YAHOO_URL.format(symbol=symbol),
            params={"range": "1d", "interval": "1m", "includePrePost": "true"},
            headers={"User-Agent": "BALA-Trading-Control-Center/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            raise RuntimeError("Yahoo Finance returned no XAUUSD data")

        meta = result[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        if price is None:
            closes = ((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            price = next((x for x in reversed(closes) if x is not None), None)

        if price is None:
            raise RuntimeError("XAUUSD price unavailable")

        return {
            "connected": True,
            "symbol": "XAUUSD",
            "price": float(price),
            "bid": meta.get("bid"),
            "ask": meta.get("ask"),
            "previous_close": meta.get("previousClose"),
            "day_high": meta.get("regularMarketDayHigh"),
            "day_low": meta.get("regularMarketDayLow"),
            "timestamp": meta.get("regularMarketTime"),
            "source": "Yahoo Finance XAUUSD=X",
            "source_type": "spot",
            "note": "Quote freshness depends on Yahoo Finance; broker MT5 price may differ.",
            "fallback_error": twelve_error,
        }
    except Exception as exc:
        return {
            "connected": False,
            "symbol": "XAUUSD",
            "price": None,
            "source": "XAUUSD",
            "error": str(exc),
            "fallback_error": twelve_error,
        }
