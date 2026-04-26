from __future__ import annotations

from datetime import datetime
from typing import Optional


def compute_profit_loss(trade_type: str, entry: float, exit_p: float, qty: float) -> float:
    """
    Compute P/L in quote currency.

    BUY:  (exit - entry) * qty
    SELL: (entry - exit) * qty
    """
    t = (trade_type or "").upper()
    if t == "SELL":
        return round((entry - exit_p) * qty, 2)
    return round((exit_p - entry) * qty, 2)


def parse_dt(value: str) -> Optional[str]:
    """
    Accept common datetime-local input and normalize to a readable ISO-like string.

    HTML `datetime-local` typically submits `YYYY-MM-DDTHH:MM`.
    We store as `YYYY-MM-DD HH:MM` (text) for easy display and SQLite datetime().
    """
    if not value:
        return None
    v = value.strip()
    try:
        if "T" in v:
            dt = datetime.fromisoformat(v)
        else:
            dt = datetime.fromisoformat(v.replace(" ", "T"))
        return dt.isoformat(sep=" ", timespec="minutes")
    except ValueError:
        return v  # fallback: store whatever was provided

