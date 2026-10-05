"""Run BALA analysis, update paper ledger, and publish dashboard status.

Execution is PAPER_ONLY. No broker/exchange order is submitted.
"""
import os, json, time
import requests
from bala_engine import analyze
from binance_market import get_json
from kotak_market import get_kotak_snapshot
from kotak_bala import get_kotak_bala_signals
from fyers_market import get_fyers_snapshot
from mcx_market import get_mcx_snapshot
from paper_trader import load as load_paper, process as process_paper

SYMBOL=os.getenv("BALA_SYMBOL","BTCUSDT")
FYERS_SYMBOL=os.getenv("FYERS_SYMBOL","NSE:NIFTY50-INDEX")
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","")
STATUS_PATH=os.path.join(os.path.dirname(__file__),"..","dashboard","status.json")
SIGNAL_THRESHOLD=7
RAW_SCORE_MAX=17

def score10(raw):
    try:return max(0,min(10,round(float(raw)/RAW_SCORE_MAX*10)))
    except Exception:return 0

def telegram(text):
    if not TOKEN or not CHAT_ID:return False
    r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",json={"chat_id":CHAT_ID,"text":text},timeout=10); r.raise_for_status(); return True

def market_price(symbol):return float(get_json("/api/v3/ticker/price",{"symbol":symbol})["price"])

def safe_btc_analysis():
    try:return analyze(SYMBOL),None
    except Exception as exc:print(f"BTC analysis unavailable: {exc}");return None,str(exc)

def normalize_signal(s):
    if not s:return {"side":"WAIT","score":0,"entry":None,"stop":None,"t1":None,"t2":None,"status":"DATA WAIT","reason":"Backend data unavailable"}
    side=s.get("side","WAIT");score=max(0,min(10,int(s.get("score",0))));eligible=side in ("BUY","SELL") and score>=SIGNAL_THRESHOLD
    return {"side":side if eligible else "WAIT","score":score,"entry":s.get("entry") if eligible else None,"stop":s.get("stop") if eligible else None,"t1":s.get("t1") if eligible else None,"t2":s.get("t2") if eligible else None,"status":"OPEN" if eligible else s.get("status","NO TRADE"),"reason":s.get("reason","BALA confirmation below 7/10")}

def write_status(s,kotak,fyers,mcx,paper,indian_signals=None,btc_error=None,btc_price=None,kotak_error=None):
    raw=getattr(s,"score",0) if s is not None else 0;btc_score=score10(raw);eligible=s is not None and s.side in ("BUY","SELL") and btc_score>=SIGNAL_THRESHOLD
    btc={"side":s.side if eligible else "WAIT","score":btc_score,"entry":s.entry if eligible else None,"stop":s.stop if eligible else None,"t1":s.t1 if eligible else None,"t2":s.t2 if eligible else None,"status":"OPEN" if eligible else "NO TRADE","reason":s.reason if eligible else ("BTC backend unavailable" if s is None else "BALA score below 7/10 entry threshold")}
    source=indian_signals or {}
    signals={"NIFTY":normalize_signal(source.get("NIFTY")),"SENSEX":normalize_signal(source.get("SENSEX")),"GOLD MINI":normalize_signal(source.get("GOLD MINI")),"CRUDE OIL MINI":normalize_signal(source.get("CRUDE OIL MINI")),"BTC / USDT":btc}
    payload={"timestamp":int(time.time()),"market":{"symbol":SYMBOL,"price":btc_price,"source":"Binance public market-data feed","error":btc_error},"kotak":kotak,"fyers":fyers,"mcx":mcx,"signal":btc,"signals":signals,"paper":paper,"execution":"PAPER_ONLY","live_execution":False,"kotak_bala_error":kotak_error}
    os.makedirs(os.path.dirname(STATUS_PATH),exist_ok=True)
    with open(STATUS_PATH,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2)
    return payload

def main():
    s,btc_error=safe_btc_analysis();kotak=get_kotak_snapshot();fyers=get_fyers_snapshot(FYERS_SYMBOL);mcx=get_mcx_snapshot()
    consumer=(os.getenv("KOTAK_CONSUMER_KEY") or os.getenv("KOTAK_API_KEY") or os.getenv("KOTAK_ACCESS_TOKEN") or "").strip()
    try:indian_signals,kotak_error=get_kotak_bala_signals(consumer)
    except Exception as exc:indian_signals,kotak_error={},str(exc)
    try:price=market_price(SYMBOL)
    except Exception as exc:price=None;btc_error=btc_error or str(exc)
    paper=load_paper();btc_score=score10(getattr(s,"score",0) if s else 0);btc_eligible=s is not None and s.side in ("BUY","SELL") and btc_score>=SIGNAL_THRESHOLD
    btc_signal={"side":s.side if btc_eligible else "WAIT","score":btc_score,"entry":s.entry if btc_eligible else None,"stop":s.stop if btc_eligible else None,"t1":s.t1 if btc_eligible else None,"t2":s.t2 if btc_eligible else None,"reason":s.reason if btc_eligible else "BALA score below 7/10 or BTC backend unavailable"}
    if price is not None:paper=process_paper(paper,btc_signal,price)
    payload=write_status(s,kotak,fyers,mcx,paper,indian_signals,btc_error,price,kotak_error);print(json.dumps(payload,indent=2))
    if btc_eligible:
        msg=(f"BALA BTC PAPER ALERT\n{SYMBOL} · {s.side}\nScore: {btc_score}/10\nEntry: {s.entry:.2f}\nSL: {s.stop:.2f}\nT1: {s.t1:.2f}\nT2: {s.t2:.2f}\nReason: {s.reason}\nExecution: PAPER ONLY")
        print("Telegram alert:","SENT" if telegram(msg) else "NOT CONFIGURED")
    else:print("NO TRADE — BTC BALA score below 7/10 or backend unavailable")
    for name,sig in (indian_signals or {}).items():print(f"{name}: {sig.get('side')} {sig.get('score')}/10 — {sig.get('reason')}")
    for name,item in (mcx.get("instruments",{}) or {}).items():print(f"{name}: {item.get('symbol')} LTP={item.get('price')} connected={item.get('connected')}")

if __name__=="__main__":main()
