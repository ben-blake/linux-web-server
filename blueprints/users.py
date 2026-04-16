from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from werkzeug.security import check_password_hash, generate_password_hash

import config
from blueprints.auth import SESSION_USER_ID
from database import get_db
from utils.decorators import admin_required, login_required
from utils.storage import quota_bytes, sum_user_quotas_bytes

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _parse_quota_gb(raw: str) -> Optional[int]:
    """Return storage_quota_bytes from a form field, or None if invalid.

    Empty string → 0 (no per-user limit).
    """
    raw = (raw or "").strip()
    if raw == "":
        return 0
    try:
        gb = float(raw)
    except ValueError:
        return None
    if gb < 0:
        return None
    return int(gb * 1024**3)


def _quota_sum_ok(proposed_bytes: int, exclude_user_id: Optional[int] = None) -> bool:
    """Return True if adding proposed_bytes to the sum of other user quotas
    stays within the global NAS quota."""
    return sum_user_quotas_bytes(exclude_user_id) + proposed_bytes <= quota_bytes()


@users_bp.route("/")
@admin_required
def list_users() -> ResponseReturnValue:
    db = get_db()
    try:
        users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    finally:
        db.close()
    return render_template("users/list.html", users=users)


@users_bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_user() -> ResponseReturnValue:
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form["role"]
        permissions = ",".join(request.form.getlist("permissions")) or "read"
        quota_raw = request.form.get("storage_quota_gb", "")

        if not username or not password or not password.strip():
            flash("Username and password are required.", "error")
            return render_template("users/create.html")

        quota_b = _parse_quota_gb(quota_raw)
        if quota_b is None:
            flash("Invalid storage quota — enter a non-negative number of GB.", "error")
            return render_template("users/create.html")
        if not _quota_sum_ok(quota_b):
            flash(
                f"Storage quota would exceed the global {config.NAS_QUOTA_GB} GB limit.",
                "error",
            )
            return render_template("users/create.html")

        db = get_db()
        try:
            existing = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                flash("Username already exists.", "error")
                return render_template("users/create.html")

            db.execute(
                "INSERT INTO users (username, password_hash, role, permissions, storage_quota_bytes)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    username,
                    generate_password_hash(password, method="pbkdf2:sha256"),
                    role,
                    permissions,
                    quota_b,
                ),
            )
            db.commit()
        finally:
            db.close()
        flash(f'User "{username}" created.', "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/create.html")


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id: int) -> ResponseReturnValue:
    if request.method == "POST":
        role = request.form["role"]
        permissions = ",".join(request.form.getlist("permissions")) or "read"
        quota_raw = request.form.get("storage_quota_gb", "")

        quota_b = _parse_quota_gb(quota_raw)
        if quota_b is None:
            flash("Invalid storage quota — enter a non-negative number of GB.", "error")
            return redirect(url_for("users.edit_user", user_id=user_id))
        if not _quota_sum_ok(quota_b, exclude_user_id=user_id):
            flash(
                f"Storage quota would exceed the global {config.NAS_QUOTA_GB} GB limit.",
                "error",
            )
            return redirect(url_for("users.edit_user", user_id=user_id))

        db = get_db()
        try:
            db.execute(
                "UPDATE users SET role = ?, permissions = ?, storage_quota_bytes = ? WHERE id = ?",
                (role, permissions, quota_b, user_id),
            )
            db.commit()
        finally:
            db.close()
        flash("User updated.", "success")
        return redirect(url_for("users.list_users"))

    db = get_db()
    try:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        db.close()

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("users.list_users"))

    return render_template("users/edit.html", user=user)


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id: int) -> ResponseReturnValue:
    if user_id == session.get(SESSION_USER_ID):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("users.list_users"))

    db = get_db()
    try:
        # Orphan user's files and backups rather than deleting, to preserve data
        db.execute(
            "UPDATE files SET uploaded_by = NULL WHERE uploaded_by = ?", (user_id,)
        )
        db.execute(
            "UPDATE backups SET created_by = NULL WHERE created_by = ?", (user_id,)
        )
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
    finally:
        db.close()
    flash("User deleted.", "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile() -> ResponseReturnValue:
    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        if not new_password or not new_password.strip():
            flash("New password is required.", "error")
            return render_template("profile.html")

        db = get_db()
        try:
            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (session[SESSION_USER_ID],)
            ).fetchone()

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
                return render_template("profile.html")

            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (
                    generate_password_hash(new_password, method="pbkdf2:sha256"),
                    session[SESSION_USER_ID],
                ),
            )
            db.commit()
        finally:
            db.close()
        flash("Password updated.", "success")
        return redirect(url_for("users.profile"))

    return render_template("profile.html")
