"""Run BALA BTC analysis, publish dashboard status, and optionally send Telegram alert.

Kotak Neo is used for Indian-market live quote snapshots when its API key is
configured in GitHub Actions secrets. No exchange order is placed by this runner.
"""
import os, json, time
import requests
from bala_engine import analyze
from kotak_market import get_kotak_snapshot

SYMBOL=os.getenv("BALA_SYMBOL","BTCUSDT")
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


def write_status(s, kotak):
    payload={
        "timestamp":int(time.time()),
        "market":{"symbol":SYMBOL,"price":market_price(SYMBOL),"source":"Binance public feed"},
        "kotak":kotak,
        "signal":{"side":s.side,"score":s.score,"entry":s.entry,"stop":s.stop,"t1":s.t1,"t2":s.t2,"reason":s.reason},
        "execution":"PAPER_ONLY",
        "live_execution":False
    }
    os.makedirs(os.path.dirname(STATUS_PATH),exist_ok=True)
    with open(STATUS_PATH,"w",encoding="utf-8") as f:
        json.dump(payload,f,indent=2)
    return payload


def main():
    s=analyze(SYMBOL)
    kotak=get_kotak_snapshot()
    payload=write_status(s, kotak)
    print(json.dumps(payload,indent=2))
    if s.side in ("BUY","SELL") and s.score>=6:
        msg=(f"BALA BTC ALERT\n{SYMBOL} · {s.side}\nScore: {s.score}/7\n"
             f"Entry: {s.entry:.2f}\nSL: {s.stop:.2f}\nT1: {s.t1:.2f}\nT2: {s.t2:.2f}\n"
             f"Reason: {s.reason}\nExecution: PAPER ONLY")
        sent=telegram(msg)
        print("Telegram alert:","SENT" if sent else "NOT CONFIGURED")
    else:
        print("NO TRADE — confirmation threshold not met")

if __name__ == "__main__": main()
