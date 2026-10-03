"""FYERS v3 market-data adapter.

Requires FYERS_APP_ID and FYERS_ACCESS_TOKEN in the runtime environment.
The access token is intentionally not stored in the repository.
"""
import os


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
        from fyers_apiv3 import fyersModel

        fyers = fyersModel.FyersModel(
            client_id=app_id,
            token=token,
            is_async=False,
            log_path="",
        )
        response = fyers.quotes({"symbols": symbol})
        if response.get("s") != "ok":
            return {
                "connected": False,
                "symbol": symbol,
                "price": None,
                "source": "FYERS",
                "error": str(response),
            }

        d = response.get("d") or []
        v = d[0].get("v", {}) if d else {}
        price = v.get("lp")
        return {
            "connected": True,
            "symbol": symbol,
            "price": price,
            "source": "FYERS v3",
            "response": response,
        }
    except Exception as exc:
        return {
            "connected": False,
            "symbol": symbol,
            "price": None,
            "source": "FYERS",
            "error": str(exc),
        }
