"""
BALA V2 signal gate.
Pure decision engine: no broker calls, no credentials, no order placement.

Entry is allowed only when:
- score >= 7/10
- direction has no hard conflict
- RR >= configured minimum
- daily risk / consecutive-loss gates are clear
- duplicate entry and chop/news gates are clear

The caller supplies already-computed market features.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, List


@dataclass
class BALAConfig:
    min_score: int = 7
    min_rr: float = 1.5
    max_daily_loss_r: float = 2.0
    max_consecutive_losses: int = 2
    max_open_positions: int = 1


@dataclass
class MarketFeatures:
    trend_15m: int = 0
    orb_15m: int = 0
    liquidity_sweep: int = 0
    bos_choch: int = 0
    displacement_5m: int = 0
    fvg_ob_retest: int = 0
    vwap: int = 0
    frvp: int = 0
    volume_rvol: int = 0
    premium_zone: int = 0

    hard_conflict: bool = False
    chop: bool = False
    high_impact_news: bool = False
    duplicate_signal: bool = False

    planned_entry: Optional[float] = None
    planned_sl: Optional[float] = None
    planned_tp: Optional[float] = None


@dataclass
class RiskState:
    daily_pnl_r: float = 0.0
    consecutive_losses: int = 0
    open_positions: int = 0


def score_market(f: MarketFeatures) -> int:
    parts = [
        f.trend_15m, f.orb_15m, f.liquidity_sweep, f.bos_choch,
        f.displacement_5m, f.fvg_ob_retest, f.vwap, f.frvp,
        f.volume_rvol, f.premium_zone
    ]
    return sum(1 for x in parts if x == 1)


def planned_rr(f: MarketFeatures, side: str) -> Optional[float]:
    if f.planned_entry is None or f.planned_sl is None or f.planned_tp is None:
        return None
    risk = abs(f.planned_entry - f.planned_sl)
    reward = abs(f.planned_tp - f.planned_entry)
    if risk <= 0:
        return None
    return reward / risk


def evaluate_signal(
    f: MarketFeatures,
    risk: RiskState,
    config: BALAConfig = BALAConfig(),
    side: str = "LONG",
) -> Dict:
    score = score_market(f)
    rr = planned_rr(f, side)

    hard_rejects: List[str] = []
    if score < config.min_score:
        hard_rejects.append("score_below_7")
    if f.hard_conflict:
        hard_rejects.append("15m_5m_structure_conflict")
    if f.chop:
        hard_rejects.append("market_chop")
    if f.high_impact_news:
        hard_rejects.append("high_impact_news")
    if f.duplicate_signal:
        hard_rejects.append("duplicate_signal")
    if risk.daily_pnl_r <= -abs(config.max_daily_loss_r):
        hard_rejects.append("daily_loss_limit")
    if risk.consecutive_losses >= config.max_consecutive_losses:
        hard_rejects.append("consecutive_loss_pause")
    if risk.open_positions >= config.max_open_positions:
        hard_rejects.append("position_limit")
    if rr is None:
        hard_rejects.append("invalid_rr_data")
    elif rr < config.min_rr:
        hard_rejects.append("rr_below_1_5")

    approved = len(hard_rejects) == 0
    return {
        "approved": approved,
        "action": side if approved else "NO_TRADE",
        "score": score,
        "rr": rr,
        "reasons": [] if approved else hard_rejects,
        "features": asdict(f),
        "risk": asdict(risk),
    }
