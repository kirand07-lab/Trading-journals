from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute, query_one


bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.before_app_request
def load_logged_in_user() -> None:
    """Attach the logged-in user (if any) to `g.user`."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    g.user = query_one("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(**kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped


@bp.get("/signup")
def signup() -> str:
    return render_template("auth/signup.html")


@bp.post("/signup")
def signup_post():
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    error: Optional[str] = None
    if not username:
        error = "Username is required."
    elif not email:
        error = "Email is required."
    elif not password or len(password) < 6:
        error = "Password must be at least 6 characters."

    if error is None:
        existing = query_one(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            (username, email),
        )
        if existing is not None:
            error = "Username or email already exists."

    if error is not None:
        flash(error, "danger")
        return redirect(url_for("auth.signup"))

    user_id = execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, generate_password_hash(password)),
    )
    session.clear()
    session["user_id"] = user_id
    flash("Account created. Welcome!", "success")
    return redirect(url_for("dashboard"))


@bp.get("/login")
def login() -> str:
    return render_template("auth/login.html")


@bp.post("/login")
def login_post():
    identifier = (request.form.get("identifier") or "").strip()
    password = request.form.get("password") or ""

    user = query_one(
        "SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?",
        (identifier, identifier.lower()),
    )

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid username/email or password.", "danger")
        return redirect(url_for("auth.login"))

    session.clear()
    session["user_id"] = user["id"]
    flash(f"Welcome back, {user['username']}!", "success")
    return redirect(url_for("dashboard"))


@bp.post("/logout")
def logout():
    session.clear()
    flash("You are now logged out.", "info")
    return redirect(url_for("auth.login"))

