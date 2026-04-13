from typing import Optional

import psutil
from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue

from utils.decorators import login_required

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


def _collect_stats() -> dict[str, object]:
    """Return a dict of current CPU, memory, and disk stats."""
    cpu_percent = psutil.cpu_percent(interval=0.1)

    mem = psutil.virtual_memory()
    memory = {
        "total_gb": _bytes_to_gb(mem.total),
        "used_gb": _bytes_to_gb(mem.used),
        "percent": mem.percent,
    }

    disk = psutil.disk_usage("/")
    disk_info = {
        "total_gb": _bytes_to_gb(disk.total),
        "used_gb": _bytes_to_gb(disk.used),
        "percent": disk.percent,
    }

    return {
        "cpu_percent": cpu_percent,
        "memory": memory,
        "disk": disk_info,
    }


@monitor_bp.route("/")
@login_required
def index() -> ResponseReturnValue:
    """System monitoring dashboard — CPU, memory, and disk."""
    stats = _collect_stats()
    return render_template("monitor/index.html", **stats)


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
