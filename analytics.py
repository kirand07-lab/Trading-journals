from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from flask import Blueprint, g, jsonify, render_template
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

import db as db_module
from auth import login_required


bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def _load_trades_df(user_id: int) -> pd.DataFrame:
    rows = db_module.query_all(
        """
        SELECT t.trade_type, t.asset, t.entry_price, t.exit_price, t.quantity,
               t.opened_at, t.closed_at, t.strategy_id, t.profit_loss,
               s.name AS strategy_name
        FROM trades t
        LEFT JOIN strategies s ON s.id = t.strategy_id
        WHERE t.user_id = ?
        ORDER BY datetime(t.closed_at) ASC
        """,
        (user_id,),
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")
    df["opened_at"] = pd.to_datetime(df["opened_at"], errors="coerce")
    df["is_win"] = (df["profit_loss"] > 0).astype(int)
    df["date"] = df["closed_at"].dt.date
    df["hour"] = df["closed_at"].dt.hour.fillna(0).astype(int)
    df["session"] = pd.cut(
        df["hour"],
        bins=[-1, 10, 15, 24],
        labels=["morning", "afternoon", "evening"],
    ).astype(str)
    df["holding_mins"] = (
        (df["closed_at"] - df["opened_at"]).dt.total_seconds() / 60.0
    ).replace([np.inf, -np.inf], np.nan)
    df["holding_mins"] = df["holding_mins"].fillna(0).clip(lower=0)
    df["position_value_proxy"] = (df["entry_price"].abs() * df["quantity"].abs()).fillna(0)
    df["strategy_name"] = df["strategy_name"].fillna("Unspecified")
    return df


def _equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["closed_at", "equity"])
    out = df[["closed_at", "profit_loss"]].dropna(subset=["closed_at"]).copy()
    out["equity"] = out["profit_loss"].cumsum()
    return out


def compute_kpis(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pl": 0.0}
    total = float(len(df))
    wins = float(df["is_win"].sum())
    return {
        "total_trades": int(total),
        "win_rate": round((wins / total) * 100.0, 2) if total else 0.0,
        "total_pnl": float(df["profit_loss"].sum()),
        "avg_pl": float(df["profit_loss"].mean()),
    }


def rule_based_insights(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return ["Add a few trades to generate insights."]

    insights: List[str] = []

    # Winning strategies (minimum sample size)
    strat = (
        df.groupby("strategy_name")
        .agg(trades=("profit_loss", "size"), win_rate=("is_win", "mean"), avg_pl=("profit_loss", "mean"))
        .reset_index()
    )
    strat = strat[strat["trades"] >= 5].sort_values(["win_rate", "avg_pl"], ascending=False)
    if not strat.empty:
        best = strat.iloc[0]
        insights.append(
            f'You perform best with "{best["strategy_name"]}" (win rate {best["win_rate"]*100:.1f}% over {int(best["trades"])} trades).'
        )

    # Overtrading detection (simple rule)
    per_day = df.groupby("date").size()
    if not per_day.empty:
        avg = per_day.mean()
        high_days = int((per_day >= max(6, avg * 2)).sum())
        if high_days > 0:
            insights.append("Losses often increase during overtrading. Consider a daily trade limit.")

    # Time-of-day / session effect
    sess = df.groupby("session").agg(trades=("is_win", "size"), win_rate=("is_win", "mean")).reset_index()
    sess = sess[sess["trades"] >= 5].sort_values("win_rate", ascending=False)
    if not sess.empty:
        top = sess.iloc[0]
        insights.append(f"Your win rate is highest in {top['session']} sessions ({top['win_rate']*100:.1f}%).")

    # Risk flags: unusually large position values
    if df["position_value_proxy"].notna().any():
        p90 = float(df["position_value_proxy"].quantile(0.9))
        if p90 > 0:
            insights.append("Risk check: avoid sizing trades far above your typical position value.")

    if not insights:
        insights.append("Keep journaling consistently to unlock deeper analytics.")
    return insights[:6]


def ml_factors(df: pd.DataFrame) -> List[str]:
    """
    Train a tiny logistic regression model to find factors correlated with wins.
    Guardrail: only run if enough trades.
    """
    if df.empty or len(df) < 30:
        return []

    X_cat = df[["strategy_name", "session"]].astype(str)
    X_num = df[["holding_mins", "position_value_proxy"]].astype(float)
    y = df["is_win"].astype(int).to_numpy()

    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    Xc = enc.fit_transform(X_cat)
    X = np.hstack([Xc, X_num.to_numpy()])

    model = LogisticRegression(max_iter=500)
    model.fit(X, y)

    feature_names = list(enc.get_feature_names_out(["strategy", "session"])) + ["holding_mins", "position_value_proxy"]
    coefs = model.coef_.ravel()

    ranked = sorted(zip(feature_names, coefs), key=lambda x: x[1], reverse=True)
    top_pos = [r for r in ranked[:3] if r[1] > 0]
    top_neg = [r for r in ranked[-3:] if r[1] < 0]

    out: List[str] = []
    if top_pos:
        out.append("Factors correlated with wins (ML): " + ", ".join([n.replace("strategy_", "").replace("session_", "") for n, _ in top_pos]))
    if top_neg:
        out.append("Factors correlated with losses (ML): " + ", ".join([n.replace("strategy_", "").replace("session_", "") for n, _ in top_neg]))
    return out


@bp.get("/insights")
@login_required
def insights_page():
    user_id = int(g.user["id"])
    df = _load_trades_df(user_id)
    kpis = compute_kpis(df)
    insights = rule_based_insights(df)
    ml = ml_factors(df)
    return render_template("insights.html", kpis=kpis, insights=insights, ml=ml)


@bp.get("/api/charts/pnl_timeseries")
@login_required
def api_pnl_timeseries():
    user_id = int(g.user["id"])
    df = _load_trades_df(user_id)
    curve = _equity_curve(df)
    if curve.empty:
        return jsonify({"labels": [], "values": []})

    curve = curve.dropna(subset=["closed_at"]).copy()
    curve["label"] = curve["closed_at"].dt.strftime("%Y-%m-%d")
    grouped = curve.groupby("label").agg(equity=("equity", "last")).reset_index()
    return jsonify({"labels": grouped["label"].tolist(), "values": grouped["equity"].round(2).tolist()})


@bp.get("/api/charts/win_loss_pie")
@login_required
def api_win_loss_pie():
    user_id = int(g.user["id"])
    df = _load_trades_df(user_id)
    if df.empty:
        return jsonify({"labels": ["Wins", "Losses"], "values": [0, 0]})
    wins = int((df["profit_loss"] > 0).sum())
    losses = int((df["profit_loss"] < 0).sum())
    return jsonify({"labels": ["Wins", "Losses"], "values": [wins, losses]})


@bp.get("/api/charts/monthly_performance")
@login_required
def api_monthly_performance():
    user_id = int(g.user["id"])
    df = _load_trades_df(user_id)
    if df.empty:
        return jsonify({"labels": [], "values": []})
    df = df.dropna(subset=["closed_at"]).copy()
    df["month"] = df["closed_at"].dt.to_period("M").astype(str)
    grouped = df.groupby("month").agg(pnl=("profit_loss", "sum")).reset_index()
    return jsonify({"labels": grouped["month"].tolist(), "values": grouped["pnl"].round(2).tolist()})


@bp.get("/api/charts/strategy_success")
@login_required
def api_strategy_success():
    user_id = int(g.user["id"])
    df = _load_trades_df(user_id)
    if df.empty:
        return jsonify({"labels": [], "values": []})
    grouped = (
        df.groupby("strategy_name")
        .agg(win_rate=("is_win", "mean"), trades=("is_win", "size"))
        .reset_index()
    )
    grouped = grouped[grouped["trades"] >= 3].sort_values("win_rate", ascending=False).head(8)
    return jsonify({"labels": grouped["strategy_name"].tolist(), "values": (grouped["win_rate"] * 100).round(1).tolist()})

