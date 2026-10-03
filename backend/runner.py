"""Run BALA BTC analysis once and optionally send Telegram alert.
Designed for GitHub Actions. It never places an exchange order.
"""
import os, json, time
import requests
from bala_engine import analyze

SYMBOL=os.getenv("BALA_SYMBOL","BTCUSDT")
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","")


def telegram(text):
    if not TOKEN or not CHAT_ID:
        return False
    url=f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r=requests.post(url,json={"chat_id":CHAT_ID,"text":text},timeout=10)
    r.raise_for_status(); return True


def main():
    s=analyze(SYMBOL)
    payload={"symbol":SYMBOL,"timestamp":int(time.time()),"side":s.side,"score":s.score,"entry":s.entry,"stop":s.stop,"t1":s.t1,"t2":s.t2,"reason":s.reason,"execution":"PAPER_ONLY"}
    print(json.dumps(payload,indent=2))
    if s.side in ("BUY","SELL") and s.score>=6:
        msg=(f"BALA BTC ALERT\n{SYMBOL} · {s.side}\nScore: {s.score}/7\n"
             f"Entry: {s.entry:.2f}\nSL: {s.stop:.2f}\nT1: {s.t1:.2f}\nT2: {s.t2:.2f}\n"
             f"Reason: {s.reason}\nExecution: PAPER ONLY")
        sent=telegram(msg); print("Telegram alert:","SENT" if sent else "NOT CONFIGURED")
    else:
        print("NO TRADE — confirmation threshold not met")

if __name__ == "__main__": main()
