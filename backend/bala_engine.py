"""BALA BTC multi-factor signal engine (PAPER/ALERT ONLY).

Aggressive paper mode: signals are eligible from 7/10 while still requiring
multiple BALA confirmations. Uses Binance public klines only. No trading
credentials and no exchange order execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict

from binance_market import get_json

AGGRESSIVE_MODE = True
ENTRY_THRESHOLD = 7 if AGGRESSIVE_MODE else 8

@dataclass
class Signal:
    side: str
    score: int
    entry: float | None
    stop: float | None
    t1: float | None
    t2: float | None
    reason: str


def klines(symbol: str, interval: str, limit: int = 120) -> List[Dict[str, float]]:
    rows = get_json("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    out=[]
    for x in rows:
        out.append({"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"closed":True})
    return out


def atr(c, n=14):
    if len(c) < n + 1: return 0.0
    trs=[]
    for i in range(1,len(c)):
        trs.append(max(c[i]["high"]-c[i]["low"], abs(c[i]["high"]-c[i-1]["close"]), abs(c[i]["low"]-c[i-1]["close"])))
    return sum(trs[-n:])/n


def ema(vals, n):
    if not vals: return 0
    a=2/(n+1); e=vals[0]
    for v in vals[1:]: e=a*v+(1-a)*e
    return e


def rsi(c, n=14):
    if len(c) < n + 1: return 50.0
    changes=[c[i]["close"]-c[i-1]["close"] for i in range(1,len(c))][-n:]
    gains=sum(max(x,0) for x in changes)/n
    losses=sum(max(-x,0) for x in changes)/n
    if losses == 0: return 100.0
    rs=gains/losses
    return 100-(100/(1+rs))


def rvol(c, n=20):
    if len(c)<n+1:return 1.0
    avg=sum(x["volume"] for x in c[-n-1:-1])/n
    return c[-1]["volume"]/avg if avg else 1.0


def vwap(c, n=40):
    rows=c[-n:]
    pv=sum(((x["high"]+x["low"]+x["close"])/3)*x["volume"] for x in rows)
    vv=sum(x["volume"] for x in rows)
    return pv/vv if vv else rows[-1]["close"]


def heikin_ashi(c):
    ha=[]
    for i,x in enumerate(c):
        hc=(x["open"]+x["high"]+x["low"]+x["close"])/4
        if i==0: ho=(x["open"]+x["close"])/2
        else: ho=(ha[-1]["open"]+ha[-1]["close"])/2
        hh=max(x["high"],ho,hc); hl=min(x["low"],ho,hc)
        ha.append({"open":ho,"high":hh,"low":hl,"close":hc})
    return ha


def fvg(c):
    if len(c)<3:return 0
    a,b,d=c[-3],c[-2],c[-1]
    if d["low"] > a["high"]: return 1
    if d["high"] < a["low"]: return -1
    return 0


def orderflow_proxy(c):
    x=c[-1]
    rng=max(x["high"]-x["low"],1e-9)
    body=x["close"]-x["open"]
    return (body/rng) * (x["volume"] / max(sum(z["volume"] for z in c[-21:-1])/20,1e-9))


def analyze(symbol="BTCUSDT") -> Signal:
    c15=klines(symbol,"15m",160); c5=klines(symbol,"5m",160); c1=klines(symbol,"1m",160)
    p=c1[-1]["close"]; a=atr(c1)
    e9=ema([x["close"] for x in c1[-40:]],9); e21=ema([x["close"] for x in c1[-60:]],21)
    h15=max(x["high"] for x in c15[-16:-1]); l15=min(x["low"] for x in c15[-16:-1])
    h5=max(x["high"] for x in c5[-12:-1]); l5=min(x["low"] for x in c5[-12:-1])
    last=c1[-1]; prev=c1[-2]
    body=abs(last["close"]-last["open"]); rng=max(last["high"]-last["low"],1e-9)
    displacement=body/rng>=0.65 and body>=max(a*0.45,1e-9)
    bull_break=p>h5 or p>h15; bear_break=p<l5 or p<l15
    bull_mom=e9>e21 and p>e9; bear_mom=e9<e21 and p<e9
    vol=rvol(c1); vw=vwap(c5); rs=rsi(c5)
    bull_sweep=prev["low"]<l5 and p>prev["high"]
    bear_sweep=prev["high"]>h5 and p<prev["low"]
    ha=heikin_ashi(c15); ha_last=ha[-1]; ha_prev=ha[-2]
    ha_bull=ha_last["close"]>ha_last["open"] and ha_prev["close"]>ha_prev["open"] and ha_last["low"]>=ha_last["open"]*0.9995
    ha_bear=ha_last["close"]<ha_last["open"] and ha_prev["close"]<ha_prev["open"] and ha_last["high"]<=ha_last["open"]*1.0005
    imbalance=fvg(c1)
    flow=orderflow_proxy(c1)

    bull=bear=0; why_b=[]; why_s=[]
    if bull_break: bull+=2; why_b.append("15M/5M structure break")
    if bear_break: bear+=2; why_s.append("15M/5M structure break")
    if bull_mom: bull+=1; why_b.append("1M EMA momentum")
    if bear_mom: bear+=1; why_s.append("1M EMA momentum")
    if bull_sweep: bull+=2; why_b.append("sell-side liquidity sweep")
    if bear_sweep: bear+=2; why_s.append("buy-side liquidity sweep")
    if displacement and last["close"]>last["open"]: bull+=1; why_b.append("bullish displacement")
    if displacement and last["close"]<last["open"]: bear+=1; why_s.append("bearish displacement")
    if vol>=1.5 and last["close"]>last["open"]: bull+=1; why_b.append("RVOL participation")
    if vol>=1.5 and last["close"]<last["open"]: bear+=1; why_s.append("RVOL participation")
    if ha_bull: bull+=1; why_b.append("15M Heikin Ashi trend")
    if ha_bear: bear+=1; why_s.append("15M Heikin Ashi trend")
    if p>vw: bull+=1; why_b.append("VWAP acceptance")
    if p<vw: bear+=1; why_s.append("VWAP acceptance")
    if rs>52 and rs<72: bull+=1; why_b.append("RSI momentum")
    if rs<48 and rs>28: bear+=1; why_s.append("RSI momentum")
    if imbalance==1: bull+=1; why_b.append("bullish FVG")
    if imbalance==-1: bear+=1; why_s.append("bearish FVG")
    if flow>=0.75: bull+=1; why_b.append("OHLCV aggressive-buy proxy")
    if flow<=-0.75: bear+=1; why_s.append("OHLCV aggressive-sell proxy")

    if bull>=ENTRY_THRESHOLD and bull>bear:
        stop=min(l5, p-a*1.2); risk=max(p-stop,a*0.8)
        return Signal("BUY",bull,p,stop,p+risk*1.5,p+risk*2.5," + ".join(why_b))
    if bear>=ENTRY_THRESHOLD and bear>bull:
        stop=max(h5, p+a*1.2); risk=max(stop-p,a*0.8)
        return Signal("SELL",bear,p,stop,p-risk*1.5,p-risk*2.5," + ".join(why_s))
    return Signal("WAIT",max(bull,bear),None,None,None,None,f"Aggressive mode ON; score below {ENTRY_THRESHOLD}/10 threshold")


if __name__ == "__main__":
    print(analyze())
