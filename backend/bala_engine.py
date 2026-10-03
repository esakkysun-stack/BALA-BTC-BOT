"""BALA BTC signal engine (paper/alert only).
Uses Binance public klines. No trading credentials are used here.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Dict
import requests

BASE = "https://api.binance.com/api/v3/klines"

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
    r = requests.get(BASE, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
    r.raise_for_status()
    out=[]
    for x in r.json():
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


def rvol(c, n=20):
    if len(c)<n+1:return 1.0
    avg=sum(x["volume"] for x in c[-n-1:-1])/n
    return c[-1]["volume"]/avg if avg else 1.0


def analyze(symbol="BTCUSDT") -> Signal:
    c15=klines(symbol,"15m",120); c5=klines(symbol,"5m",120); c1=klines(symbol,"1m",120)
    p=c1[-1]["close"]; a=atr(c1)
    e9=ema([x["close"] for x in c1[-30:]],9); e21=ema([x["close"] for x in c1[-40:]],21)
    h15=max(x["high"] for x in c15[-16:-1]); l15=min(x["low"] for x in c15[-16:-1])
    h5=max(x["high"] for x in c5[-12:-1]); l5=min(x["low"] for x in c5[-12:-1])
    last=c1[-1]; prev=c1[-2]
    body=abs(last["close"]-last["open"]); rng=max(last["high"]-last["low"],1e-9)
    displacement=body/rng>=0.65 and body>=max(a*0.45,1e-9)
    bull_break=p>h5 or p>h15; bear_break=p<l5 or p<l15
    bull_mom=e9>e21 and p>e9; bear_mom=e9<e21 and p<e9
    vol=rvol(c1)
    bull_sweep=prev["low"]<l5 and p>prev["high"]
    bear_sweep=prev["high"]>h5 and p<prev["low"]
    bull=0; bear=0; reasons=[]
    bull += 2 if bull_break else 0; bear += 2 if bear_break else 0
    bull += 1 if bull_mom else 0; bear += 1 if bear_mom else 0
    bull += 2 if bull_sweep else 0; bear += 2 if bear_sweep else 0
    bull += 1 if displacement and last["close"]>last["open"] else 0
    bear += 1 if displacement and last["close"]<last["open"] else 0
    bull += 1 if vol>=1.5 else 0; bear += 1 if vol>=1.5 else 0
    if bull>=6 and bull>bear:
        stop=min(l5, p-a*1.2); risk=max(p-stop,a*0.8); return Signal("BUY",bull,p,stop,p+risk*1.5,p+risk*2.5,"15M/5M break + momentum/sweep confirmation")
    if bear>=6 and bear>bull:
        stop=max(h5, p+a*1.2); risk=max(stop-p,a*0.8); return Signal("SELL",bear,p,stop,p-risk*1.5,p-risk*2.5,"15M/5M break + momentum/sweep confirmation")
    return Signal("WAIT",max(bull,bear),None,None,None,None,"Confirmation threshold not met; NO TRADE")

if __name__ == "__main__":
    s=analyze(); print(s)
