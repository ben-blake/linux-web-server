from typing import Any, Optional

import psutil
from flask import Blueprint, jsonify, render_template, session
from flask.typing import ResponseReturnValue

import config
from database import get_db
from utils.decorators import login_required
from utils.storage import nas_used_bytes, quota_bytes

monitor_bp = Blueprint("monitor", __name__, url_prefix="/monitor")

_LOG_PATHS = [
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/system.log",
]
_LOG_TAIL_LINES = 100


def _bytes_to_gb(b: int) -> float:
    """Convert bytes to GB, rounded to 1 decimal place."""
    return round(b / (1024**3), 1)


def _bytes_human(b: int) -> str:
    """Return a human-readable size string picking the most appropriate unit."""
    if b < 1024:
        return f"{b} B"
    if b < 1024**2:
        return f"{b / 1024:.1f} KB"
    if b < 1024**3:
        return f"{b / 1024**2:.1f} MB"
    return f"{b / 1024**3:.2f} GB"


def _collect_stats() -> dict[str, object]:
    """Return a dict of current CPU, memory, and disk stats."""
    cpu_percent = psutil.cpu_percent(interval=0.1)

    mem = psutil.virtual_memory()
    memory = {
        "total_gb": _bytes_to_gb(mem.total),
        "used_gb": _bytes_to_gb(mem.used),
        "percent": mem.percent,
    }

    _quota = quota_bytes()
    used_bytes = nas_used_bytes()
    disk_info = {
        "total_gb": config.NAS_QUOTA_GB,
        "used_gb": _bytes_to_gb(used_bytes),
        "used_human": _bytes_human(used_bytes),
        "percent": round(min(used_bytes / _quota * 100, 100), 1),
    }

    return {
        "cpu_percent": cpu_percent,
        "memory": memory,
        "disk": disk_info,
    }


def _per_user_storage() -> list[dict[str, Any]]:
    """Return bytes used and quota per user, sorted by usage descending.
    Admin-only."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT u.username,
                   u.storage_quota_bytes AS quota_bytes,
                   COALESCE(SUM(f.size), 0) AS used_bytes
            FROM users u
            LEFT JOIN files f ON f.uploaded_by = u.id
            GROUP BY u.id
            ORDER BY used_bytes DESC
            """
        ).fetchall()
    finally:
        db.close()
    return [
        {
            "username": row["username"],
            "used_human": _bytes_human(row["used_bytes"]),
            "used_bytes": row["used_bytes"],
            "quota_bytes": row["quota_bytes"] or 0,
            "quota_human": (
                _bytes_human(row["quota_bytes"]) if row["quota_bytes"] else "—"
            ),
        }
        for row in rows
    ]


@monitor_bp.route("/")
@login_required
def index() -> ResponseReturnValue:
    """System monitoring dashboard — CPU, memory, and disk."""
    from blueprints.auth import SESSION_ROLE

    stats = _collect_stats()
    is_admin = session.get(SESSION_ROLE) == "admin"
    user_storage = _per_user_storage() if is_admin else []
    return render_template(
        "monitor/index.html", **stats, is_admin=is_admin, user_storage=user_storage
    )


@monitor_bp.route("/stats")
@login_required
def stats() -> ResponseReturnValue:
    """JSON endpoint for live stat polling — consumed by the monitor page."""
    return jsonify(_collect_stats())


def _read_logs() -> tuple[list[str], Optional[str]]:
    """Return (log_lines, log_source) from the first accessible log file.

    Extracted so tests can patch this function without intercepting other
    internal uses of open() (e.g. Jinja template loading).
    """
    for path in _LOG_PATHS:
        try:
            with open(path, errors="replace") as f:
                lines = f.readlines()[-_LOG_TAIL_LINES:]
                return lines, path
        except (FileNotFoundError, PermissionError):
            continue

    return [
        "No log file is accessible on this host.\n",
        "On Ubuntu, ensure the server process has read access to /var/log/syslog\n",
        "(e.g. add the user to the adm group: sudo usermod -a -G adm <user>)\n",
    ], None


@monitor_bp.route("/logs")
@login_required
def logs() -> ResponseReturnValue:
    """View recent system log entries."""
    log_lines, log_source = _read_logs()
    return render_template(
        "monitor/logs.html", log_lines=log_lines, log_source=log_source
    )
