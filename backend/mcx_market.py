"""FYERS MCX live-market adapter.

Resolves the current near-expiry MCX Gold Mini and Crude Oil Mini futures
from FYERS' daily symbol master, then reads live quotes through FYERS v3.
No credentials are stored in this repository.
"""
import csv
import io
import os
import time
from datetime import datetime, timezone

import requests

SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/MCX_COM.csv"


def _fy_token():
    return os.getenv("FYERS_APP_ID", "").strip(), os.getenv("FYERS_ACCESS_TOKEN", "").strip()


def _master_rows():
    r = requests.get(SYMBOL_MASTER_URL, timeout=15)
    r.raise_for_status()
    return list(csv.reader(io.StringIO(r.text)))


def _pick(rows, root):
    now = int(time.time())
    candidates = []
    for row in rows:
        if len(row) < 10:
            continue
        symbol = row[9].strip()
        # FYERS MCX futures are exposed in the symbol field, e.g. MCX:GOLDM...FUT.
        if not symbol.startswith("MCX:") or not symbol.endswith("FUT"):
            continue
        if not symbol.startswith(f"MCX:{root}"):
            continue
        try:
            expiry = int(float(row[8])) if row[8] else 0
        except Exception:
            expiry = 0
        if expiry and expiry < now:
            continue
        candidates.append((expiry or 2**31, symbol, row))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    expiry, symbol, row = candidates[0]
    return {
        "symbol": symbol,
        "expiry": datetime.fromtimestamp(expiry, tz=timezone.utc).isoformat() if expiry < 2**31 else None,
        "lot_size": row[3] if len(row) > 3 else None,
        "tick_size": row[4] if len(row) > 4 else None,
    }


def get_mcx_snapshot():
    app_id, token = _fy_token()
    base = {"source": "FYERS v3 / MCX", "connected": False}
    if not app_id or not token:
        return {**base, "error": "FYERS_APP_ID or FYERS_ACCESS_TOKEN is not configured", "instruments": {}}

    try:
        rows = _master_rows()
        gold = _pick(rows, "GOLDM")
        crude = _pick(rows, "CRUDEOILM")
        selected = [x["symbol"] for x in (gold, crude) if x]
        if not selected:
            return {**base, "error": "No current Gold Mini / Crude Oil Mini futures found in FYERS MCX symbol master", "instruments": {}}

        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=app_id, token=token, is_async=False, log_path="")
        response = fyers.quotes({"symbols": ",".join(selected)})
        if response.get("s") != "ok":
            return {**base, "error": str(response), "instruments": {}}

        by_symbol = {}
        for item in response.get("d") or []:
            sym = item.get("n") or item.get("symbol") or item.get("v", {}).get("symbol")
            v = item.get("v", {}) or {}
            if sym:
                by_symbol[sym] = v

        instruments = {}
        for key, meta in (("GOLD MINI", gold), ("CRUDE OIL MINI", crude)):
            if not meta:
                instruments[key] = {"connected": False, "error": "Contract not found"}
                continue
            v = by_symbol.get(meta["symbol"], {})
            instruments[key] = {
                **meta,
                "connected": bool(v),
                "price": v.get("lp"),
                "change": v.get("ch"),
                "change_pct": v.get("chp"),
                "volume": v.get("volume"),
                "bid": v.get("bid"),
                "ask": v.get("ask"),
            }

        return {**base, "connected": any(x.get("connected") for x in instruments.values()), "instruments": instruments}
    except Exception as exc:
        return {**base, "error": str(exc), "instruments": {}}
