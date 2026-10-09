"""15-Minute Breaker Entry Strategy — paper-only signal engine.

Input candles must be CLOSED, sorted oldest-to-newest, with open/high/low/close/volume.
This engine never submits broker or exchange orders.
"""
from __future__ import annotations
from typing import Any

TARGET_POINTS = 22.0
STOP_POINTS = 20.0


def _valid(candles: list[dict[str, Any]], minimum: int, name: str) -> None:
    if len(candles) < minimum:
        raise ValueError(f"{name} needs at least {minimum} closed candles")
    for candle in candles:
        for key in ("open", "high", "low", "close"):
            if key not in candle or not isinstance(candle[key], (int, float)):
                raise ValueError(f"{name} candle missing numeric {key}")


def evaluate(c15: list[dict[str, Any]], c5: list[dict[str, Any]],
             c1: list[dict[str, Any]]) -> dict[str, Any]:
    """Return CALL, PUT, or NEUTRAL plus an underlying-price paper entry.

    Reference levels are the previous completed 15m candle's high/low.
    A 5m close outside the level confirms direction. Entry additionally requires:
    (1) a 1m three-candle range breakout within the last 4 closed candles;
    (2) a retracement into the last opposite-colour candle (OB proxy);
    (3) a reversal candle closing beyond that opposite candle's extreme.
    """
    _valid(c15, 2, "15m")
    _valid(c5, 2, "5m")
    _valid(c1, 5, "1m")
    ref = c15[-2]
    level_high, level_low = float(ref["high"]), float(ref["low"])
    last5 = c5[-1]
    current15 = c15[-1]
    touched_up = float(current15["high"]) > level_high
    touched_dn = float(current15["low"]) < level_low
    bull_confirm = float(last5["close"]) > level_high
    bear_confirm = float(last5["close"]) < level_low

    if touched_up and not bull_confirm:
        return {"state":"NEUTRAL","side":"WAIT","entry":None,"stop":None,"target":None,
                "reason":"15m high touched/broken but 5m body did not close above it"}
    if touched_dn and not bear_confirm:
        return {"state":"NEUTRAL","side":"WAIT","entry":None,"stop":None,"target":None,
                "reason":"15m low touched/broken but 5m body did not close below it"}
    if not bull_confirm and not bear_confirm:
        return {"state":"NEUTRAL","side":"WAIT","entry":None,"stop":None,"target":None,
                "reason":"No confirmed 5m body close beyond previous 15m range"}

    trigger = c1[-1]
    previous = c1[-2]
    recent_charge_break_up = any(
        float(c1[i]["close"]) > max(float(z["high"]) for z in c1[i-3:i])
        for i in range(max(3, len(c1)-4), len(c1)-1)
    )
    recent_charge_break_dn = any(
        float(c1[i]["close"]) < min(float(z["low"]) for z in c1[i-3:i])
        for i in range(max(3, len(c1)-4), len(c1)-1)
    )

    if bull_confirm:
        ob_retest_break = (float(previous["close"]) < float(previous["open"])
                           and float(trigger["close"]) > float(trigger["open"])
                           and float(trigger["low"]) <= float(previous["high"])
                           and float(trigger["close"]) > float(previous["high"]))
        if ob_retest_break and recent_charge_break_up:
            entry = float(trigger["close"])
            return {"state":"CALL","side":"BUY","entry":entry,
                    "stop":entry-STOP_POINTS,"target":entry+TARGET_POINTS,
                    "reason":"15m high breakout + 5m body-close confirmation + 1m charge/OB-proxy trigger"}
        return {"state":"CALL","side":"WAIT","entry":None,"stop":None,"target":None,
                "reason":"CALL bias confirmed; waiting for 1m charge break and OB retest trigger"}

    ob_retest_break = (float(previous["close"]) > float(previous["open"])
                       and float(trigger["close"]) < float(trigger["open"])
                       and float(trigger["high"]) >= float(previous["low"])
                       and float(trigger["close"]) < float(previous["low"]))
    if ob_retest_break and recent_charge_break_dn:
        entry = float(trigger["close"])
        return {"state":"PUT","side":"SELL","entry":entry,
                "stop":entry+STOP_POINTS,"target":entry-TARGET_POINTS,
                "reason":"15m low breakdown + 5m body-close confirmation + 1m charge/OB-proxy trigger"}
    return {"state":"PUT","side":"WAIT","entry":None,"stop":None,"target":None,
            "reason":"PUT bias confirmed; waiting for 1m charge break and OB retest trigger"}


def paper_step(state: dict[str, Any], signal: dict[str, Any], price: float) -> dict[str, Any]:
    """Minimal single-position paper ledger. Never places orders."""
    state.setdefault("mode", "PAPER_ONLY")
    state.setdefault("open_trade", None)
    state.setdefault("trades", [])
    trade = state["open_trade"]
    if trade:
        side = trade["side"]
        exit_price = None
        reason = None
        if side == "BUY":
            if price <= trade["stop"]:
                exit_price, reason = trade["stop"], "STOP"
            elif price >= trade["target"]:
                exit_price, reason = trade["target"], "TARGET"
        else:
            if price >= trade["stop"]:
                exit_price, reason = trade["stop"], "STOP"
            elif price <= trade["target"]:
                exit_price, reason = trade["target"], "TARGET"
        if exit_price is not None:
            pnl = (exit_price-trade["entry"]) if side == "BUY" else (trade["entry"]-exit_price)
            trade.update({"exit": exit_price, "exit_reason": reason, "pnl_points": pnl})
            state["trades"].append(trade)
            state["open_trade"] = None
    if state["open_trade"] is None and signal.get("side") in ("BUY", "SELL") and signal.get("entry") is not None:
        state["open_trade"] = {
            "side": signal["side"], "entry": float(signal["entry"]),
            "stop": float(signal["stop"]), "target": float(signal["target"]),
            "opened_at": signal.get("timestamp"), "reason": signal.get("reason", "")
        }
    return state
