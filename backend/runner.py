"""Run BALA BTC analysis, publish dashboard status, and optionally send Telegram alert.

Kotak Neo is used for Indian-market live quote snapshots when configured.
FYERS v3 is an optional Indian-market quote source. Binance remains optional
for BTC dashboard analysis. Live order execution stays disabled.
"""
import os, json, time
import requests
from bala_engine import analyze
from kotak_market import get_kotak_snapshot
from fyers_market import get_fyers_snapshot

SYMBOL=os.getenv("BALA_SYMBOL","BTCUSDT")
FYERS_SYMBOL=os.getenv("FYERS_SYMBOL","NSE:NIFTY50-INDEX")
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","")
STATUS_PATH=os.path.join(os.path.dirname(__file__),"..","dashboard","status.json")


def telegram(text):
    if not TOKEN or not CHAT_ID:
        return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r=requests.post(url,json={"chat_id":CHAT_ID,"text":text},timeout=10)
    r.raise_for_status()
    return True


def market_price(symbol):
    r=requests.get("https://api.binance.com/api/v3/ticker/price",params={"symbol":symbol},timeout=10)
    r.raise_for_status()
    return float(r.json()["price"])


def safe_btc_analysis():
    try:
        return analyze(SYMBOL), None
    except Exception as exc:
        print(f"BTC analysis unavailable: {exc}")
        return None, str(exc)


def write_status(s, kotak, fyers, btc_error=None):
    try:
        btc_price=market_price(SYMBOL)
        btc_market={"symbol":SYMBOL,"price":btc_price,"source":"Binance public feed"}
    except Exception as exc:
        print(f"BTC price unavailable: {exc}")
        btc_market={"symbol":SYMBOL,"price":None,"source":"Browser Binance public feed","error":str(exc)}

    if s is None:
        signal={
            "side":"WAIT",
            "score":0,
            "entry":None,
            "stop":None,
            "t1":None,
            "t2":None,
            "reason":"BTC backend unavailable; Indian-market snapshots can still update"
        }
    else:
        signal={
            "side":s.side,
            "score":s.score,
            "entry":s.entry,
            "stop":s.stop,
            "t1":s.t1,
            "t2":s.t2,
            "reason":s.reason
        }

    payload={
        "timestamp":int(time.time()),
        "market":btc_market,
        "kotak":kotak,
        "fyers":fyers,
        "signal":signal,
        "execution":"PAPER_ONLY",
        "live_execution":False
    }
    if btc_error:
        payload["btc_backend_error"]=btc_error
    os.makedirs(os.path.dirname(STATUS_PATH),exist_ok=True)
    with open(STATUS_PATH,"w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2)
    return payload


def main():
    s, btc_error=safe_btc_analysis()
    kotak=get_kotak_snapshot()
    fyers=get_fyers_snapshot(FYERS_SYMBOL)
    payload=write_status(s, kotak, fyers, btc_error)
    print(json.dumps(payload,indent=2))

    if s is not None and s.side in ("BUY","SELL") and s.score>=6:
        msg=(f"BALA BTC ALERT\n{SYMBOL} · {s.side}\nScore: {s.score}/7\n"
             f"Entry: {s.entry:.2f}\nSL: {s.stop:.2f}\nT1: {s.t1:.2f}\nT2: {s.t2:.2f}\n"
             f"Reason: {s.reason}\nExecution: PAPER ONLY")
        sent=telegram(msg)
        print("Telegram alert:","SENT" if sent else "NOT CONFIGURED")
    else:
        print("NO TRADE — confirmation threshold not met or BTC backend unavailable")

if __name__ == "__main__": main()
