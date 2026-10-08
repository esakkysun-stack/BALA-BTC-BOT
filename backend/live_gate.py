"""Safety gate for optional live Kotak execution.

Live execution is OFF by default. The dashboard/strategy may be live, but no
order is submitted unless BOTH environment flags are explicitly enabled:
LIVE_TRADING_ENABLED=true and LIVE_CONFIRMATION=I_UNDERSTAND_LIVE_RISK.
"""
from __future__ import annotations
import os

CONFIRMATION = "I_UNDERSTAND_LIVE_RISK"

def live_enabled() -> bool:
    return (
        os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower() == "true"
        and os.getenv("LIVE_CONFIRMATION", "").strip() == CONFIRMATION
    )

def status() -> dict:
    return {
        "enabled": live_enabled(),
        "execution": "LIVE" if live_enabled() else "PAPER_ONLY",
        "requires": ["LIVE_TRADING_ENABLED=true", f"LIVE_CONFIRMATION={CONFIRMATION}"],
        "note": "Do not enable live execution until signal/data/order tests pass.",
    }
