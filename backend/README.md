# BALA BTC backend

This is the first paper/alert backend for the BALA BTC project.

## Data
- Binance public BTCUSDT klines
- 15m structure
- 5m confirmation
- 1m execution context

## BALA checks currently implemented
- 15m/5m breakout context
- EMA momentum filter
- liquidity sweep proxy
- displacement proxy
- relative-volume filter
- risk levels from ATR
- confirmation threshold with `WAIT / NO TRADE` when conditions are insufficient

## Alerts
`runner.py` sends a Telegram alert only when a BUY/SELL threshold is met. It never submits an exchange order.

GitHub Actions reads these repository secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

No exchange API key is required for this alert-only stage.

## Important
GitHub Actions is not a permanent websocket server. The included workflow runs every 5 minutes, so this stage is an alert/paper backend rather than a tick-by-tick execution server. Live execution remains disabled.
