from __future__ import annotations

import csv
import io
from typing import Optional

from flask import Blueprint, flash, g, redirect, render_template, request, send_file, url_for

import db as db_module
from auth import login_required
from utils import compute_profit_loss, parse_dt


bp = Blueprint("trades", __name__, url_prefix="/trades")


def _load_strategies(user_id: int):
    return db_module.query_all(
        "SELECT id, name FROM strategies WHERE user_id = ? ORDER BY name COLLATE NOCASE",
        (user_id,),
    )


@bp.get("/")
@login_required
def list_trades():
    user_id = int(g.user["id"])

    asset = (request.args.get("asset") or "").strip()
    strategy_id = (request.args.get("strategy_id") or "").strip()
    outcome = (request.args.get("outcome") or "").strip()  # win/loss/any
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()

    where = ["t.user_id = ?"]
    params: list = [user_id]

    if asset:
        where.append("t.asset LIKE ?")
        params.append(f"%{asset}%")

    if strategy_id.isdigit():
        where.append("t.strategy_id = ?")
        params.append(int(strategy_id))

    if outcome == "win":
        where.append("t.profit_loss > 0")
    elif outcome == "loss":
        where.append("t.profit_loss < 0")

    if start:
        where.append("datetime(t.closed_at) >= datetime(?)")
        params.append(start)
    if end:
        where.append("datetime(t.closed_at) <= datetime(?)")
        params.append(end)

    rows = db_module.query_all(
        f"""
        SELECT t.*, s.name AS strategy_name
        FROM trades t
        LEFT JOIN strategies s ON s.id = t.strategy_id
        WHERE {' AND '.join(where)}
        ORDER BY datetime(t.closed_at) DESC
        LIMIT 250
        """,
        tuple(params),
    )

    strategies = _load_strategies(user_id)
    return render_template(
        "trades/list.html",
        trades=rows,
        strategies=strategies,
        filters={"asset": asset, "strategy_id": strategy_id, "outcome": outcome, "start": start, "end": end},
    )


@bp.get("/new")
@login_required
def new_trade():
    user_id = int(g.user["id"])
    strategies = _load_strategies(user_id)
    return render_template("trades/form.html", mode="new", trade=None, strategies=strategies)


@bp.post("/new")
@login_required
def new_trade_post():
    user_id = int(g.user["id"])
    trade_type = (request.form.get("trade_type") or "").upper().strip()
    asset = (request.form.get("asset") or "").strip().upper()
    strategy_id = request.form.get("strategy_id") or ""
    notes = (request.form.get("notes") or "").strip()
    opened_at = parse_dt(request.form.get("opened_at") or "")
    closed_at = parse_dt(request.form.get("closed_at") or "")

    try:
        entry = float(request.form.get("entry_price") or "0")
        exit_p = float(request.form.get("exit_price") or "0")
        qty = float(request.form.get("quantity") or "0")
    except ValueError:
        flash("Entry/Exit/Quantity must be numbers.", "danger")
        return redirect(url_for("trades.new_trade"))

    error: Optional[str] = None
    if trade_type not in {"BUY", "SELL"}:
        error = "Trade type must be BUY or SELL."
    elif not asset:
        error = "Asset is required."
    elif qty <= 0:
        error = "Quantity must be greater than 0."
    elif not closed_at:
        error = "Close date/time is required."

    if error:
        flash(error, "danger")
        return redirect(url_for("trades.new_trade"))

    pl = compute_profit_loss(trade_type, entry, exit_p, qty)
    sid = int(strategy_id) if strategy_id.isdigit() else None

    db_module.execute(
        """
        INSERT INTO trades
          (user_id, trade_type, asset, entry_price, exit_price, quantity, opened_at, closed_at, strategy_id, notes, profit_loss)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, trade_type, asset, entry, exit_p, qty, opened_at, closed_at, sid, notes, pl),
    )
    flash("Trade added.", "success")
    return redirect(url_for("trades.list_trades"))


@bp.get("/<int:trade_id>/edit")
@login_required
def edit_trade(trade_id: int):
    user_id = int(g.user["id"])
    trade = db_module.query_one("SELECT * FROM trades WHERE id = ? AND user_id = ?", (trade_id, user_id))
    if trade is None:
        flash("Trade not found.", "warning")
        return redirect(url_for("trades.list_trades"))
    strategies = _load_strategies(user_id)
    return render_template("trades/form.html", mode="edit", trade=trade, strategies=strategies)


@bp.post("/<int:trade_id>/edit")
@login_required
def edit_trade_post(trade_id: int):
    user_id = int(g.user["id"])
    existing = db_module.query_one("SELECT id FROM trades WHERE id = ? AND user_id = ?", (trade_id, user_id))
    if existing is None:
        flash("Trade not found.", "warning")
        return redirect(url_for("trades.list_trades"))

    trade_type = (request.form.get("trade_type") or "").upper().strip()
    asset = (request.form.get("asset") or "").strip().upper()
    strategy_id = request.form.get("strategy_id") or ""
    notes = (request.form.get("notes") or "").strip()
    opened_at = parse_dt(request.form.get("opened_at") or "")
    closed_at = parse_dt(request.form.get("closed_at") or "")

    try:
        entry = float(request.form.get("entry_price") or "0")
        exit_p = float(request.form.get("exit_price") or "0")
        qty = float(request.form.get("quantity") or "0")
    except ValueError:
        flash("Entry/Exit/Quantity must be numbers.", "danger")
        return redirect(url_for("trades.edit_trade", trade_id=trade_id))

    if trade_type not in {"BUY", "SELL"} or not asset or qty <= 0 or not closed_at:
        flash("Please fill all required fields correctly.", "danger")
        return redirect(url_for("trades.edit_trade", trade_id=trade_id))

    pl = compute_profit_loss(trade_type, entry, exit_p, qty)
    sid = int(strategy_id) if strategy_id.isdigit() else None

    db_module.execute(
        """
        UPDATE trades
        SET trade_type = ?, asset = ?, entry_price = ?, exit_price = ?, quantity = ?,
            opened_at = ?, closed_at = ?, strategy_id = ?, notes = ?, profit_loss = ?
        WHERE id = ? AND user_id = ?
        """,
        (trade_type, asset, entry, exit_p, qty, opened_at, closed_at, sid, notes, pl, trade_id, user_id),
    )
    flash("Trade updated.", "success")
    return redirect(url_for("trades.list_trades"))


@bp.post("/<int:trade_id>/delete")
@login_required
def delete_trade(trade_id: int):
    user_id = int(g.user["id"])
    db_module.execute("DELETE FROM trades WHERE id = ? AND user_id = ?", (trade_id, user_id))
    flash("Trade deleted.", "info")
    return redirect(url_for("trades.list_trades"))


@bp.get("/export.csv")
@login_required
def export_csv():
    user_id = int(g.user["id"])

    rows = db_module.query_all(
        """
        SELECT t.id, t.trade_type, t.asset, t.entry_price, t.exit_price, t.quantity, t.opened_at, t.closed_at,
               s.name AS strategy, t.notes, t.profit_loss
        FROM trades t
        LEFT JOIN strategies s ON s.id = t.strategy_id
        WHERE t.user_id = ?
        ORDER BY datetime(t.closed_at) DESC
        """,
        (user_id,),
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "trade_type",
            "asset",
            "entry_price",
            "exit_price",
            "quantity",
            "opened_at",
            "closed_at",
            "strategy",
            "notes",
            "profit_loss",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["id"],
                r["trade_type"],
                r["asset"],
                r["entry_price"],
                r["exit_price"],
                r["quantity"],
                r["opened_at"],
                r["closed_at"],
                r["strategy"],
                r["notes"],
                r["profit_loss"],
            ]
        )

    out = io.BytesIO(buf.getvalue().encode("utf-8"))
    out.seek(0)
    return send_file(out, mimetype="text/csv", as_attachment=True, download_name="trades.csv")

