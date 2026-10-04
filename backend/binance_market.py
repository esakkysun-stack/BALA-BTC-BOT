"""Binance public market-data requests with official endpoint failover."""
import os

import requests


def _base_urls():
    configured = os.getenv("BINANCE_MARKET_DATA_URL", "").strip().rstrip("/")
    candidates = [
        configured,
        "https://data-api.binance.vision",
        "https://api-gcp.binance.com",
        "https://api.binance.com",
    ]
    return list(dict.fromkeys(url for url in candidates if url))


def get_json(path, params):
    """Fetch public Binance market data, trying official hosts in order."""
    errors = []
    for base_url in _base_urls():
        try:
            response = requests.get(
                f"{base_url}{path}",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            errors.append(f"{base_url}: {exc}")

    raise requests.RequestException(
        "All Binance public market-data endpoints failed: " + " | ".join(errors)
    )
