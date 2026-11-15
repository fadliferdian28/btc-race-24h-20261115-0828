# Capitulation Buyer — btc-race-24h-20261115-0828

[![make.fun](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/fadliferdian28/btc-race-24h-20261115-0828/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/fadliferdian28/btc-race-24h-20261115-0828/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828)

A bot for the [make.fun](https://make.fun/bounty/btc-race-24h-20261115-0828) BTC trading race: it trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute on-chain prices with $1,000 of paper money.

## Strategy

Capitulation buyer — the method the previous race's winners used ("Washout Recovery", "Capitulation-bounce", "Deep-dip mean-reversion"):

- **Entry:** close at least 7.5% below the session high AND RSI(14) below 40. Only the washout bottom reverses; earlier dips in a downtrend are pauses, not reversals.
- **Exit:** +3.0% over cost (TP) or -1.5% under cost (SL), or 120 bars held.
- **Risk:** one position at a time, 95% of equity per trade, 20% drawdown halt, every trade journaled to stderr.

Local dev-window replay: **+$28.93 net PnL** (1 trade, 1 win, max drawdown 0.85%).

## Files

- `main.py` — the bot (Python 3.13, stdlib only, speaks `agent-fun/bars-replay/v1`)
- `vendor/makefun_bars.py` — byte-identical copy of the kit's Python SDK shim
