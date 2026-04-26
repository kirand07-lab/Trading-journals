from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from random import choice, randint, random

from flask import Flask, g, redirect, render_template, url_for

import db as db_module
from auth import bp as auth_bp, login_required
from trades import bp as trades_bp
from analytics import bp as analytics_bp
from utils import compute_profit_loss


def create_app() -> Flask:
    app = Flask(__name__)

    # In a real deployment, set SECRET_KEY via environment variable.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

    # Store the SQLite DB in the project folder for beginner-friendly setup.
    app.config["DATABASE"] = os.environ.get(
        "DATABASE",
        str(Path(__file__).with_name("trading_journal.sqlite3")),
    )

    app.teardown_appcontext(db_module.close_db)
    app.register_blueprint(auth_bp)
    app.register_blueprint(trades_bp)
    app.register_blueprint(analytics_bp)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Initialize the database tables."""
        with app.app_context():
            db_module.init_db()
        print("Initialized the database.")

    @app.cli.command("seed")
    def seed_command() -> None:
        """Seed a demo user and dummy trades for testing."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            db_module.init_db()

            demo_user = db_module.query_one("SELECT id FROM users WHERE username = ?", ("demo",))
            if demo_user is None:
                user_id = db_module.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    ("demo", "demo@example.com", generate_password_hash("demo1234")),
                )
            else:
                user_id = int(demo_user["id"])

            # Ensure some strategies exist
            strategies = ["Breakout", "MeanReversion", "Swing", "Scalp", "News"]
            for s in strategies:
                db_module.execute(
                    "INSERT OR IGNORE INTO strategies (user_id, name, description) VALUES (?, ?, ?)",
                    (user_id, s, f"Demo strategy: {s}"),
                )

            strategy_rows = db_module.query_all(
                "SELECT id, name FROM strategies WHERE user_id = ? ORDER BY id",
                (user_id,),
            )
            strat_ids = [int(r["id"]) for r in strategy_rows]

            assets = ["AAPL", "TSLA", "BTCUSDT", "ETHUSDT", "EURUSD", "XAUUSD", "NIFTY"]
            now = datetime.now()

            # Create ~50 trades across the last 60 days
            for _ in range(50):
                trade_type = choice(["BUY", "SELL"])
                asset = choice(assets)
                qty = round(randint(1, 5) * (1 if "USD" in asset else 10), 4)
                entry = round(50 + random() * 200, 2)
                # Exit price around entry with random drift
                drift = (random() - 0.48) * 8.0
                exit_p = round(max(0.01, entry * (1 + drift / 100.0)), 2)

                closed_at = now - timedelta(days=randint(0, 59), hours=randint(0, 23))
                opened_at = closed_at - timedelta(hours=randint(1, 72))
                strategy_id = choice(strat_ids) if strat_ids else None

                pl = compute_profit_loss(trade_type, entry, exit_p, qty)
                db_module.execute(
                    """
                    INSERT INTO trades
                      (user_id, trade_type, asset, entry_price, exit_price, quantity, opened_at, closed_at, strategy_id, notes, profit_loss)
                    VALUES
                      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        trade_type,
                        asset,
                        entry,
                        exit_p,
                        qty,
                        opened_at.isoformat(sep=" ", timespec="minutes"),
                        closed_at.isoformat(sep=" ", timespec="minutes"),
                        strategy_id,
                        "Seeded demo trade",
                        pl,
                    ),
                )

            # Cache one analytics snapshot payload (simple placeholder)
            payload = {"generated_at": datetime.now().isoformat(), "note": "Seed snapshot"}
            db_module.execute(
                "INSERT INTO analytics_snapshots (user_id, payload_json) VALUES (?, ?)",
                (user_id, json.dumps(payload)),
            )

        print("Seeded demo data. Login with demo / demo1234")

    @app.get("/")
    def index():
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        # A small first pass; later we’ll expand with full analytics + charts endpoints.
        user_id = int(g.user["id"])
        total_trades = db_module.query_one("SELECT COUNT(*) AS c FROM trades WHERE user_id = ?", (user_id,))["c"]
        wins = db_module.query_one(
            "SELECT COUNT(*) AS c FROM trades WHERE user_id = ? AND profit_loss > 0",
            (user_id,),
        )["c"]
        pnl = db_module.query_one(
            "SELECT COALESCE(SUM(profit_loss), 0) AS s FROM trades WHERE user_id = ?",
            (user_id,),
        )["s"]
        avg_pl = db_module.query_one(
            "SELECT COALESCE(AVG(profit_loss), 0) AS a FROM trades WHERE user_id = ?",
            (user_id,),
        )["a"]

        recent = db_module.query_all(
            """
            SELECT t.id, t.trade_type, t.asset, t.entry_price, t.exit_price, t.quantity, t.closed_at, t.profit_loss,
                   s.name AS strategy_name
            FROM trades t
            LEFT JOIN strategies s ON s.id = t.strategy_id
            WHERE t.user_id = ?
            ORDER BY datetime(t.closed_at) DESC
            LIMIT 8
            """,
            (user_id,),
        )

        win_rate = (float(wins) / float(total_trades) * 100.0) if total_trades else 0.0
        return render_template(
            "dashboard.html",
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=float(pnl),
            avg_pl=float(avg_pl),
            recent_trades=recent,
        )

    return app

app = create_app()

