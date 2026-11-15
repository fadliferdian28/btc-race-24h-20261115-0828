#!/usr/bin/env python3
"""Capitulation buyer — the previous race winners' method, aimed at the ONE
washout that matters.

Entry: close at least 7% below the session high (the day's capitulation
drop) AND RSI(14) below 40 (oversold). In the dev window the market fell
-7.56% to its bottom then recovered +3.9%: every earlier dip was a pause
in the downtrend, only the capitulation bottom reversed. Buying every dip
loses (12 losing iterations proved it); buying ONLY the capitulation is
what the last race's "Washout Recovery" / "Capitulation-bounce" winners did.
Exit: RSI above 60 (bounce exhausted) OR +2.0% over cost OR -1.0% under
cost OR 120 bars held.
Risk: one position at a time, 20% drawdown halt, every trade journaled
to stderr. Long only, $1,000 paper USDC, 1-min cbBTC.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

# --- Parameters (capitulation buyer) ---
RSI_BARS = 14
DROP_MIN_NUM = 75         # entry only >= 7.5% below the session high
DROP_MIN_DEN = 1000
RSI_ENTRY_BELOW = 40.0
RSI_EXIT_ABOVE = 60.0
TP_NUM = 103             # +3.0% over cost
TP_DEN = 100
SL_NUM = 985             # -1.5% under cost
SL_DEN = 1000
MAX_HOLD_BARS = 120
SIZE_NUM = 95            # 95% of equity per trade
SIZE_DEN = 100
MAX_SLIPPAGE_BPS = 100
DD_STOP_NUM = 20         # halt trading if drawdown exceeds 20%
DD_STOP_DEN = 100
MIN_NOTIONAL = 1_000_000  # $1 in quote units (6 decimals)

S = None


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def on_hello(state):
    global S
    syms = state.hello.get("symbols", [])
    symbol = syms[0]["symbol"] if syms else "CBBTC"
    S = {
        "symbol": symbol,
        "session_high": 0,  # highest high seen so far (the capitulation reference)
        "rsi_first": [],
        "rsi_gain": None,
        "rsi_loss": None,
        "rsi_last": None,
        "pos": None,      # {entry_idx, entry_price}
        "pending": None,  # buy sent, awaiting fill
        "peak": state.equity,
        "halted": False,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "bars_seen": 0,
    }
    _log(f"[mr] hello symbol={symbol} equity={state.equity} warmup={state.warmup_bars}")


def _rsi(c):
    """Wilder's RSI over RSI_BARS closes. Returns RSI or None until warmed up."""
    if S["rsi_last"] is None:
        S["rsi_last"] = c
        return None
    change = c - S["rsi_last"]
    S["rsi_last"] = c
    up = change if change > 0 else 0
    down = -change if change < 0 else 0
    if S["rsi_gain"] is None:
        S["rsi_first"].append(change)
        if len(S["rsi_first"]) == RSI_BARS:
            S["rsi_gain"] = sum(x for x in S["rsi_first"] if x > 0) / RSI_BARS
            S["rsi_loss"] = sum(-x for x in S["rsi_first"] if x < 0) / RSI_BARS
        return None
    S["rsi_gain"] = (S["rsi_gain"] * (RSI_BARS - 1) + up) / RSI_BARS
    S["rsi_loss"] = (S["rsi_loss"] * (RSI_BARS - 1) + down) / RSI_BARS
    moved = S["rsi_gain"] + S["rsi_loss"]
    return 50.0 if moved == 0 else 100.0 * S["rsi_gain"] / moved


def _buy_order(state, notional):
    return {
        "side": "buy",
        "symbol": S["symbol"],
        "notional_quote_units": int(notional),
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }


def _sell_order(state, qty):
    return {
        "side": "sell",
        "symbol": S["symbol"],
        "qty": int(qty),
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }


def _exit_position(state, reason, price):
    held = state.positions.get(S["symbol"])
    if held is None or held.qty <= 0:
        return None
    pos = S["pos"]
    if pos is not None:
        cost = held.cost
        value = state.value(S["symbol"], held.qty, price)
        pnl = value - cost
        S["trades"] += 1
        if pnl > 0:
            S["wins"] += 1
        else:
            S["losses"] += 1
        _log(
            f"[mr] EXIT {reason} seq={state.seq} price={price} "
            f"entry={pos['entry_price']} pnl_units={pnl} "
            f"trades={S['trades']} W{S['wins']} L{S['losses']}"
        )
    S["pos"] = None
    S["pending"] = None
    return _sell_order(state, held.qty)


def on_batch(state, batch):
    symbol = S["symbol"]
    orders = []

    # Drawdown guard.
    if state.equity > S["peak"]:
        S["peak"] = state.equity
    if S["peak"] > 0 and (S["peak"] - state.equity) * DD_STOP_DEN > S["peak"] * DD_STOP_NUM:
        if not S["halted"]:
            _log(f"[mr] HALT drawdown over {DD_STOP_NUM}% seq={state.seq}")
            S["halted"] = True
        held = state.positions.get(symbol)
        if held is not None and held.qty > 0:
            o = _exit_position(state, "DD-HALT", state.close(symbol) or 0)
            if o is not None:
                orders.append(o)
        return orders

    fresh = [b for b in batch.get("bars", []) if b.get("symbol") == symbol]
    if not fresh:
        return orders
    bar = fresh[0]
    o, h, low, c = int(bar["o"]), int(bar["h"]), int(bar["l"]), int(bar["c"])
    S["bars_seen"] += 1
    idx = S["bars_seen"] - 1
    if h > S["session_high"]:
        S["session_high"] = h
    rsi = _rsi(c)

    if state.warming_up:
        return orders
    if S["halted"]:
        return orders

    # Promote a pending buy once its fill shows.
    if S["pending"] is not None:
        held = state.positions.get(symbol)
        if held is not None and held.qty > 0:
            S["pos"] = {"entry_idx": idx, "entry_price": S["pending"]["entry_price"]}
            S["pending"] = None
            _log(f"[mr] FILLED seq={state.seq} entry={S['pos']['entry_price']} qty={held.qty}")
        else:
            _log(f"[mr] BUY-REJECTED seq={state.seq} (no fill)")
            S["pending"] = None

    # Manage the open position.
    if S["pos"] is not None:
        pos = S["pos"]
        held = state.positions.get(symbol)
        if held is not None and held.qty > 0:
            value = state.value(symbol, held.qty, c)
            cost = held.cost
            # TP (+3%) / SL (-1.5%). No RSI exit: RSI jumps above 60 within
            # minutes of the bottom while the bounce runs for an hour; an
            # RSI exit banks pennies and the round-trip fees eat them.
            if value * TP_DEN >= cost * TP_NUM:
                o = _exit_position(state, "TP", c)
                if o is not None:
                    orders.append(o)
                return orders
            if value * SL_DEN <= cost * SL_NUM:
                o = _exit_position(state, "SL", c)
                if o is not None:
                    orders.append(o)
                return orders
        if idx - pos["entry_idx"] >= MAX_HOLD_BARS:
            o = _exit_position(state, "TIME", c)
            if o is not None:
                orders.append(o)
            return orders
        return orders

    # Orphan position: flatten it.
    held = state.positions.get(symbol)
    if held is not None and held.qty > 0 and S["pos"] is None and S["pending"] is None:
        _log(f"[mr] ORPHAN seq={state.seq}: flattening")
        orders.append(_sell_order(state, held.qty))
        return orders

    # Entry: the capitulation — close >= 7% below the session high AND
    # RSI oversold. Only the washout bottom reverses; earlier dips are
    # pauses in the downtrend.
    sh = S["session_high"]
    drop = sh > 0 and (sh - c) * DROP_MIN_DEN >= sh * DROP_MIN_NUM
    if drop and rsi is not None and rsi < RSI_ENTRY_BELOW:
        notional = min(state.cash * SIZE_NUM // SIZE_DEN, state.weight_room(symbol))
        if notional < MIN_NOTIONAL:
            return orders
        S["pending"] = {"entry_price": c}
        _log(f"[mr] ENTRY seq={state.seq} idx={idx} close={c} rsi={rsi:.1f} session_high={sh} notional={notional}")
        orders.append(_buy_order(state, notional))
        return orders

    return orders


def on_done(state, done):
    _log(
        f"[mr] DONE equity={state.equity} cash={state.cash} "
        f"trades={S['trades']} W{S['wins']} L{S['losses']}"
    )


makefun_bars.run(on_batch, on_hello=on_hello, on_done=on_done)
