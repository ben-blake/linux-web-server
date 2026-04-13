from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from werkzeug.security import check_password_hash

from database import get_db

auth_bp = Blueprint("auth", __name__)

# Session key constants — import these everywhere rather than using string literals.
SESSION_USER_ID = "user_id"
SESSION_USERNAME = "username"
SESSION_ROLE = "role"
SESSION_PERMISSIONS = "permissions"


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")

        db = get_db()
        try:
            user = db.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            db.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session[SESSION_USER_ID] = user["id"]
            session[SESSION_USERNAME] = user["username"]
            session[SESSION_ROLE] = user["role"]
            session[SESSION_PERMISSIONS] = user["permissions"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout() -> ResponseReturnValue:
    session.clear()
    return redirect(url_for("auth.login"))
