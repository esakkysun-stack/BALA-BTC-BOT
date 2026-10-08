"""XAUUSD live market-data adapter for the BALA paper-trading dashboard.

Primary source: Twelve Data XAU/USD quote endpoint.
The API key is read only from the TWELVE_DATA_API_KEY environment variable.
No credentials are stored in the repository.

This is a market-data feed only. BALA execution remains PAPER_ONLY.
"""

import os
import requests

TWELVE_QUOTE_URL = "https://api.twelvedata.com/quote"


def get_xauusd_snapshot():
    """Return the latest available XAU/USD spot quote."""
    key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not key:
        return {
            "connected": False,
            "symbol": "XAUUSD",
            "price": None,
            "source": "Twelve Data XAU/USD",
            "error": "TWELVE_DATA_API_KEY is not configured",
        }

    try:
        r = requests.get(
            TWELVE_QUOTE_URL,
            params={"symbol": "XAU/USD", "apikey": key, "dp": 5},
            headers={"User-Agent": "BALA-Trading-Control-Center/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("status") == "error" or "code" in data:
            raise RuntimeError(
                data.get("message")
                or data.get("error")
                or str(data)
            )

        price = data.get("close")
        if price is None:
            price = data.get("price")
        if price is None:
            raise RuntimeError(f"XAU/USD price unavailable: {data}")

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
            "timestamp": data.get("timestamp"),
            "datetime": data.get("datetime"),
            "source": "Twelve Data XAU/USD",
            "source_type": "spot",
        }
    except Exception as exc:
        return {
            "connected": False,
            "symbol": "XAUUSD",
            "price": None,
            "source": "Twelve Data XAU/USD",
            "error": str(exc),
        }


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
