"""FYERS v3 REST market-data adapter.

Uses the FYERS Quotes REST API directly so the BALA runner does not
mix incompatible websocket-client dependency requirements with Kotak Neo.
Requires FYERS_APP_ID and FYERS_ACCESS_TOKEN in the runtime environment.
"""

import os
import requests


def get_fyers_snapshot(symbol=None):
    app_id = os.getenv("FYERS_APP_ID", "").strip()
    token = os.getenv("FYERS_ACCESS_TOKEN", "").strip()
    symbol = symbol or os.getenv("FYERS_SYMBOL", "NSE:NIFTY50-INDEX")

    if not app_id or not token:
        return {
            "connected": False,
            "symbol": symbol,
            "price": None,
            "source": "FYERS",
            "error": "FYERS_APP_ID or FYERS_ACCESS_TOKEN is not configured",
        }

    try:
        url = "https://api-t1.fyers.in/data/quotes"
        response = requests.get(
            url,
            params={"symbols": symbol},
            headers={"Authorization": f"{app_id}:{token}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("s") != "ok":
            return {
                "connected": False,
                "symbol": symbol,
                "price": None,
                "source": "FYERS REST",
                "error": str(payload),
            }

        data = payload.get("d") or []
        value = data[0].get("v", {}) if data else {}
        price = value.get("lp")

        return {
            "connected": price is not None,
            "symbol": symbol,
            "price": price,
            "source": "FYERS REST Quotes API",
            "response": payload,
        }
    except Exception as exc:
        return {
            "connected": False,
            "symbol": symbol,
            "price": None,
            "source": "FYERS REST",
            "error": str(exc),
        }
