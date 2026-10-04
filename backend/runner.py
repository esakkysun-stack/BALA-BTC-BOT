"""Run BALA BTC analysis, update paper-trading ledger, publish dashboard status, and optionally alert Telegram.

Live exchange order execution is deliberately disabled. This runner is PAPER_ONLY.
"""
import os, json, time
import requests
from bala_engine import analyze
from binance_market import get_json
from kotak_market import get_kotak_snapshot
from fyers_market import get_fyers_snapshot
from paper_trader import load as load_paper, process as process_paper

SYMBOL=os.getenv("BALA_SYMBOL","BTCUSDT")
FYERS_SYMBOL=os.getenv("FYERS_SYMBOL","NSE:NIFTY50-INDEX")
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","")
STATUS_PATH=os.path.join(os.path.dirname(__file__),"..","dashboard","status.json")
SIGNAL_THRESHOLD=8


def telegram(text):
    if not TOKEN or not CHAT_ID:
        return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r=requests.post(url,json={"chat_id":CHAT_ID,"text":text},timeout=10)
    r.raise_for_status()
    return True


def market_price(symbol):
    data=get_json("/api/v3/ticker/price", {"symbol":symbol})
    return float(data["price"])


def safe_btc_analysis():
    try:
        return analyze(SYMBOL), None
    except Exception as exc:
        print(f"BTC analysis unavailable: {exc}")
        return None, str(exc)


def write_status(s, kotak, fyers, paper, btc_error=None, btc_price=None):
    btc_market={"symbol":SYMBOL,"price":btc_price,"source":"Binance public market-data feed"}
    if btc_error:
        btc_market["error"]=btc_error
    signal={"side":"WAIT","score":0,"entry":None,"stop":None,"t1":None,"t2":None,
            "reason":"BTC backend unavailable; Indian-market snapshots can still update"} if s is None else {
            "side":s.side,"score":s.score,"entry":s.entry,"stop":s.stop,"t1":s.t1,"t2":s.t2,"reason":s.reason}
    payload={"timestamp":int(time.time()),"market":btc_market,"kotak":kotak,"fyers":fyers,
             "signal":signal,"paper":paper,"execution":"PAPER_ONLY","live_execution":False}
    os.makedirs(os.path.dirname(STATUS_PATH),exist_ok=True)
    with open(STATUS_PATH,"w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2)
    return payload


def main():
    s, btc_error=safe_btc_analysis()
    kotak=get_kotak_snapshot()
    fyers=get_fyers_snapshot(FYERS_SYMBOL)
    try:
        price=market_price(SYMBOL)
    except Exception as exc:
        price=None
        btc_error=btc_error or str(exc)

    paper=load_paper()
    signal={"side":s.side,"score":s.score,"entry":s.entry,"stop":s.stop,"t1":s.t1,"t2":s.t2,"reason":s.reason} if s else {"side":"WAIT","score":0}
    if price is not None:
        paper=process_paper(paper, signal, price)

    payload=write_status(s, kotak, fyers, paper, btc_error, price)
    print(json.dumps(payload,indent=2))

    if s is not None and s.side in ("BUY","SELL") and s.score>=SIGNAL_THRESHOLD:
        msg=(f"BALA BTC PAPER ALERT\n{SYMBOL} · {s.side}\nScore: {s.score}/11\n"
             f"Entry: {s.entry:.2f}\nSL: {s.stop:.2f}\nT1: {s.t1:.2f}\nT2: {s.t2:.2f}\n"
             f"Reason: {s.reason}\nExecution: PAPER ONLY — NO REAL ORDER")
        sent=telegram(msg)
        print("Telegram alert:","SENT" if sent else "NOT CONFIGURED")
    else:
        print("NO TRADE — confirmation threshold not met or BTC backend unavailable")


if __name__ == "__main__": main()
