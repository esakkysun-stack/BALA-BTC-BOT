"""
BALA V2 paper-trading integration contract.

Call build_decision() immediately before the existing paper-order function.
The existing bot should NOT place an order unless approved=True.

This module deliberately has no broker/API calls.
"""
from .strategy_engine import BALAConfig, MarketFeatures, RiskState, evaluate_signal

def build_decision(features: dict, risk: dict, side: str, config: dict | None = None):
    cfg = BALAConfig(**(config or {}))
    f = MarketFeatures(**features)
    r = RiskState(**risk)
    return evaluate_signal(f, r, cfg, side=side)

def should_place_paper_order(decision: dict) -> bool:
    return bool(decision.get("approved") is True and decision.get("action") in {"LONG", "SHORT"})

def order_payload(decision: dict) -> dict:
    if not should_place_paper_order(decision):
        return {"action": "NO_TRADE", "score": decision.get("score"), "rr": decision.get("rr"), "reasons": decision.get("reasons", [])}
    return {
        "action": decision["action"],
        "score": decision["score"],
        "rr": decision["rr"],
        "features": decision["features"],
        "risk": decision["risk"],
    }
