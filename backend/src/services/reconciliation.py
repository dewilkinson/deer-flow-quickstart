import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def reconcile_trades(history: list[dict], allow_short: bool = False) -> dict:
    """
    Core FIFO Reconciliation Engine for calculating exact Win Rates from raw broker execution logs.
    Reads chronological arrays of execution dicts and stitches them into closed 'round trip' trades.

    Args:
        history: List of standardized SnapTrade dicts [{'date', 'symbol', 'action', 'quantity', 'price'}]
        allow_short: Whether naked Sells should be treated as Short positions or orphaned errors.
    """
    if not history:
        return {"velocity": 0, "buys": 0, "sells": 0, "total_closed_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate_pct": 0, "net_realized_pnl": 0}

    # Ensure chronology mathematically flows Forward in time
    sorted_history = sorted(history, key=lambda x: str(x.get("date", "")))

    # Track open position lots per symbol
    open_lots = defaultdict(list)
    closed_trades = []

    total_executions = len(history)
    buys = sum(1 for t in history if "BUY" in str(t.get("action", "")).upper())
    sells = sum(1 for t in history if "SELL" in str(t.get("action", "")).upper())

    ignore_list = {"CASH", "FZFXX", "SPAXX", "FCASH", "FDRXX"}

    for t in sorted_history:
        sym = t.get("symbol")
        if not sym or sym in ignore_list:
            continue

        action = str(t.get("action", "")).upper()
        if action not in ["BUY", "SELL"]:
            continue

        try:
            qty = float(t.get("quantity", 0))
            price = float(t.get("price", 0))
        except ValueError:
            continue

        if qty <= 0:
            continue

        remaining_qty = qty

        # Pull from open lots if they exist to match FIFO principles
        while remaining_qty > 0.0001 and open_lots[sym]:
            oldest_lot = open_lots[sym][0]

            # Are we adding to the lot (same direction) or closing?
            same_direction = (action == "BUY" and not oldest_lot["is_short"]) or (action == "SELL" and oldest_lot["is_short"])

            if same_direction:
                # Same direction means we are adding to the position queue. Break and append.
                break

            # Opposite direction -> We are closing an active lot!
            close_qty = min(remaining_qty, oldest_lot["qty"])

            # Calculate PnL for this closed quantity
            if action == "SELL":
                # We sold to close a Long
                pnl = (price - oldest_lot["price"]) * close_qty
            else:
                # We bought to cover a Short
                pnl = (oldest_lot["price"] - price) * close_qty

            closed_trades.append(
                {
                    "symbol": sym,
                    "pnl": pnl,
                }
            )

            remaining_qty -= close_qty
            oldest_lot["qty"] -= close_qty

            # If the oldest lot is empty, discard it
            if oldest_lot["qty"] <= 0.0001:
                open_lots[sym].pop(0)

        # If we STILL have quantity left over, we've opened a new position
        if remaining_qty > 0.0001:
            if action == "SELL" and not allow_short:
                # IRA Constraint: This is a naked backfill sell from a multi-year swing trade. Do not parse it as an open short.
                pass
            else:
                open_lots[sym].append({"qty": remaining_qty, "price": price, "is_short": (action == "SELL")})

    # Mathematical Digests
    sum_pnl = sum(t["pnl"] for t in closed_trades)
    winning_trades = sum(1 for t in closed_trades if t["pnl"] > 0)
    losing_trades = sum(1 for t in closed_trades if t["pnl"] <= 0)
    total_closed = len(closed_trades)

    win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0

    # Calculate Max Drawdown safely as a heuristic of biggest losing sequence

    return {"velocity": total_executions, "buys": buys, "sells": sells, "total_closed_trades": total_closed, "winning_trades": winning_trades, "losing_trades": losing_trades, "win_rate_pct": win_rate, "net_realized_pnl": sum_pnl}
