"""Local paper-trading ledger for BALA BTC. Never sends exchange orders."""
from __future__ import annotations
import json
import os
import time
from typing import Any

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "dashboard", "paper_trades.json")
INITIAL_BALANCE = float(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
RISK_PCT = float(os.getenv("PAPER_RISK_PCT", "1.0"))
MAX_NOTIONAL_PCT = float(os.getenv("PAPER_MAX_NOTIONAL_PCT", "25"))


def _default() -> dict[str, Any]:
    return {"mode": "PAPER_ONLY", "initial_balance": INITIAL_BALANCE, "balance": INITIAL_BALANCE,
            "realized_pnl": 0.0, "open_trade": None, "trades": [], "updated_at": int(time.time())}


def load() -> dict[str, Any]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _default()
    # Repair older ledgers that were created before realized_pnl was initialized.
    state.setdefault("mode", "PAPER_ONLY")
    state.setdefault("initial_balance", INITIAL_BALANCE)
    state.setdefault("balance", INITIAL_BALANCE)
    state["realized_pnl"] = float(state.get("realized_pnl") or 0.0)
    state.setdefault("trades", [])
    state.setdefault("open_trade", None)
    return state


def save(state: dict[str, Any]) -> None:
    state["updated_at"] = int(time.time())
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _close(state: dict[str, Any], price: float, reason: str, fraction: float = 1.0) -> None:
    t = state["open_trade"]
    if not t:
        return
    qty = t["qty"] * fraction
    pnl = (price - t["entry"]) * qty if t["side"] == "BUY" else (t["entry"] - price) * qty
    state["balance"] += pnl
    state["realized_pnl"] += pnl
    t["qty"] -= qty
    t.setdefault("exits", []).append({"price": price, "qty": qty, "pnl": pnl, "reason": reason, "time": int(time.time())})
    if t["qty"] <= 1e-12:
        state["trades"].append(t)
        state["open_trade"] = None


def process(state: dict[str, Any], signal: dict[str, Any], price: float) -> dict[str, Any]:
    t = state.get("open_trade")
    if t:
        # Stop has priority. If price has passed both T1/T2 in one polling interval,
        # take T1 first and then T2 at the observed price.
        if t["side"] == "BUY" and price <= t["stop"]:
            _close(state, t["stop"], "STOP")
        elif t["side"] == "SELL" and price >= t["stop"]:
            _close(state, t["stop"], "STOP")
        elif not t.get("t1_hit") and ((t["side"] == "BUY" and price >= t["t1"]) or (t["side"] == "SELL" and price <= t["t1"])):
            _close(state, t["t1"], "T1", 0.5)
            if state.get("open_trade"):
                state["open_trade"]["t1_hit"] = True
        if state.get("open_trade"):
            t = state["open_trade"]
            if (t["side"] == "BUY" and price >= t["t2"]) or (t["side"] == "SELL" and price <= t["t2"]):
                _close(state, t["t2"], "T2")

    if state.get("open_trade") is None and signal.get("side") in ("BUY", "SELL") and signal.get("score", 0) >= 7:
        entry = float(signal["entry"]); stop = float(signal["stop"])
        risk_per_unit = abs(entry - stop)
        if risk_per_unit > 0:
            risk_cash = state["balance"] * RISK_PCT / 100.0
            qty = risk_cash / risk_per_unit
            max_qty = (state["balance"] * MAX_NOTIONAL_PCT / 100.0) / entry
            qty = min(qty, max_qty)
            state["open_trade"] = {"side": signal["side"], "entry": entry, "stop": stop,
                                    "t1": float(signal["t1"]), "t2": float(signal["t2"]),
                                    "qty": qty, "initial_qty": qty, "t1_hit": False,
                                    "opened_at": int(time.time()), "reason": signal.get("reason", "")}
    save(state)
    return state
