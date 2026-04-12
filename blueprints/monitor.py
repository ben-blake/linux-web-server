import psutil
from flask import Blueprint, render_template
from utils.decorators import login_required

monitor_bp = Blueprint('monitor', __name__, url_prefix='/monitor')

def bytes_to_gb(b):
    return round(b / (1024 ** 3), 1)

@monitor_bp.route('/')
@login_required
def index():
    cpu_percent = psutil.cpu_percent(interval=1)

    mem = psutil.virtual_memory()
    memory = {
        'total': bytes_to_gb(mem.total),
        'used': bytes_to_gb(mem.used),
        'percent': mem.percent
    }

    disk = psutil.disk_usage('/')
    disk_info = {
        'total': bytes_to_gb(disk.total),
        'used': bytes_to_gb(disk.used),
        'percent': disk.percent
    }

    return render_template('monitor/index.html',
        cpu_percent=cpu_percent,
        memory=memory,
        disk=disk_info
    )

@monitor_bp.route('/logs')
@login_required
def logs():
    log_lines = []
    try:
        with open('/var/log/system.log', 'r') as f:
            log_lines = f.readlines()[-100:]
    except (FileNotFoundError, PermissionError):
        log_lines = ['Log file not accessible.']

    return render_template('monitor/logs.html', log_lines=log_lines)
