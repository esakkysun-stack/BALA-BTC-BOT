"""BALA candle analysis for Kotak Neo NSE/BSE instruments.

Uses Kotak Neo historical OHLCV candles for 15m/5m/1m analysis.
Paper/alert only: this module never places orders.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

from neo_api_client import NeoAPI

IST = timezone(timedelta(hours=5, minutes=30))


def _float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _resolve_token(client: NeoAPI, segment: str, names: tuple[str, ...]):
    for name in names:
        try:
            rows = client.search_scrip(
                exchange_segment=segment,
                symbol=name,
                expiry="",
                option_type="",
                strike_price="",
                ignore_50multiple=True,
            )
            if isinstance(rows, dict):
                rows = rows.get("data", rows.get("scrips", []))
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    token = row.get("pSymbol") or row.get("instrument_token")
                    if token:
                        return str(token), row.get("pTrdSymbol") or row.get("trading_symbol") or name
        except Exception:
            continue
    return None, None


def _candles(client: NeoAPI, segment: str, token: str, interval: str, days: int = 30):
    now = datetime.now(IST)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    response = client.historical_data(
        neosymbol=f"{segment}|{token}",
        interval=interval,
        from_date=start,
        to_date=end,
    )
    rows = []
    if isinstance(response, dict):
        data = response.get("data", {})
        rows = data.get("candles", []) if isinstance(data, dict) else []
    out = []
    for r in rows:
        if len(r) < 6:
            continue
        out.append({
            "open": _float(r[1]), "high": _float(r[2]), "low": _float(r[3]),
            "close": _float(r[4]), "volume": _float(r[5]),
        })
    return out


def _ema(vals, n):
    if not vals:
        return 0.0
    a = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = a * v + (1 - a) * e
    return e


def _atr(c, n=14):
    if len(c) < n + 1:
        return 0.0
    tr = []
    for i in range(1, len(c)):
        tr.append(max(c[i]["high"] - c[i]["low"], abs(c[i]["high"] - c[i-1]["close"]), abs(c[i]["low"] - c[i-1]["close"])))
    return sum(tr[-n:]) / n


def _rsi(c, n=14):
    if len(c) < n + 1:
        return 50.0
    ch = [c[i]["close"] - c[i-1]["close"] for i in range(1, len(c))][-n:]
    g = sum(max(x, 0) for x in ch) / n
    l = sum(max(-x, 0) for x in ch) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def _rvol(c, n=20):
    if len(c) < n + 1:
        return 1.0
    avg = sum(x["volume"] for x in c[-n-1:-1]) / n
    return c[-1]["volume"] / avg if avg else 1.0


def _vwap(c, n=40):
    rows = c[-n:]
    vv = sum(x["volume"] for x in rows)
    return sum(((x["high"] + x["low"] + x["close"]) / 3) * x["volume"] for x in rows) / vv if vv else rows[-1]["close"]


def _fvg(c):
    if len(c) < 3:
        return 0
    a, _, d = c[-3], c[-2], c[-1]
    if d["low"] > a["high"]:
        return 1
    if d["high"] < a["low"]:
        return -1
    return 0


def analyze_kotak(client: NeoAPI, segment: str, token: str, name: str):
    """Return dashboard-compatible signal dict."""
    try:
        c15 = _candles(client, segment, token, "15min", 30)
        c5 = _candles(client, segment, token, "5min", 30)
        c1 = _candles(client, segment, token, "1min", 7)
        if len(c15) < 25 or len(c5) < 25 or len(c1) < 30:
            return {"side":"WAIT","score":0,"entry":None,"stop":None,"t1":None,"t2":None,"status":"NO TRADE","reason":"Waiting for sufficient 15M/5M/1M candles"}

        p = c1[-1]["close"]
        a = _atr(c1)
        e9 = _ema([x["close"] for x in c1[-50:]], 9)
        e21 = _ema([x["close"] for x in c1[-70:]], 21)
        h15 = max(x["high"] for x in c15[-17:-1]); l15 = min(x["low"] for x in c15[-17:-1])
        h5 = max(x["high"] for x in c5[-13:-1]); l5 = min(x["low"] for x in c5[-13:-1])
        last, prev = c1[-1], c1[-2]
        rng = max(last["high"] - last["low"], 1e-9)
        body = abs(last["close"] - last["open"])
        displacement = body / rng >= 0.65 and body >= max(a * 0.45, 1e-9)
        bull_break = p > h5 or p > h15; bear_break = p < l5 or p < l15
        bull_mom = e9 > e21 and p > e9; bear_mom = e9 < e21 and p < e9
        bull_sweep = prev["low"] < l5 and p > prev["high"]
        bear_sweep = prev["high"] > h5 and p < prev["low"]
        vol = _rvol(c1); vw = _vwap(c5); rs = _rsi(c5); imbalance = _fvg(c1)

        bull = bear = 0; wb=[]; ws=[]
        if bull_break: bull += 2; wb.append("15M/5M BOS")
        if bear_break: bear += 2; ws.append("15M/5M BOS")
        if bull_mom: bull += 1; wb.append("1M momentum")
        if bear_mom: bear += 1; ws.append("1M momentum")
        if bull_sweep: bull += 2; wb.append("sell-side sweep")
        if bear_sweep: bear += 2; ws.append("buy-side sweep")
        if displacement and last["close"] > last["open"]: bull += 1; wb.append("displacement")
        if displacement and last["close"] < last["open"]: bear += 1; ws.append("displacement")
        if vol >= 1.5 and last["close"] > last["open"]: bull += 1; wb.append("RVOL")
        if vol >= 1.5 and last["close"] < last["open"]: bear += 1; ws.append("RVOL")
        if p > vw: bull += 1; wb.append("VWAP")
        if p < vw: bear += 1; ws.append("VWAP")
        if 52 < rs < 72: bull += 1; wb.append("RSI")
        if 28 < rs < 48: bear += 1; ws.append("RSI")
        if imbalance == 1: bull += 1; wb.append("FVG")
        if imbalance == -1: bear += 1; ws.append("FVG")

        raw = max(bull, bear)
        score = min(10, round(raw / 14 * 10))
        if bull >= 8 and bull > bear:
            stop = min(l5, p - a * 1.2); risk = max(p - stop, a * 0.8)
            return {"side":"BUY","score":score,"entry":p,"stop":stop,"t1":p+risk*1.5,"t2":p+risk*2.5,"status":"OPEN","reason":" + ".join(wb)}
        if bear >= 8 and bear > bull:
            stop = max(h5, p + a * 1.2); risk = max(stop - p, a * 0.8)
            return {"side":"SELL","score":score,"entry":p,"stop":stop,"t1":p-risk*1.5,"t2":p-risk*2.5,"status":"OPEN","reason":" + ".join(ws)}
        return {"side":"WAIT","score":score,"entry":None,"stop":None,"t1":None,"t2":None,"status":"NO TRADE","reason":"BALA confirmation below 7/10"}
    except Exception as exc:
        return {"side":"WAIT","score":0,"entry":None,"stop":None,"t1":None,"t2":None,"status":"DATA WAIT","reason":f"Candle data unavailable: {exc}"}


def get_kotak_bala_signals(consumer_key: str):
    if not consumer_key:
        return {}, "KOTAK_CONSUMER_KEY is missing"
    client = NeoAPI(consumer_key=consumer_key, environment="prod")
    configs = {
        "NIFTY": ("nse_cm", ("Nifty 50", "NIFTY 50", "NIFTY")),
        "SENSEX": ("bse_cm", ("SENSEX", "BSE SENSEX")),
    }
    out = {}
    errors = []
    for label, (segment, names) in configs.items():
        token, trading_symbol = _resolve_token(client, segment, names)
        if not token:
            out[label] = {"side":"WAIT","score":0,"entry":None,"stop":None,"t1":None,"t2":None,"status":"DATA WAIT","reason":"Index instrument token not resolved"}
            errors.append(f"{label}: token not resolved")
            continue
        sig = analyze_kotak(client, segment, token, label)
        sig["instrument_token"] = token
        sig["trading_symbol"] = trading_symbol
        out[label] = sig
    return out, "; ".join(errors) if errors else None
