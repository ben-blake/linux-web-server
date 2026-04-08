# System Monitoring Module — Guide for Bhavya

You own the **System Monitoring** module. This shows real-time system stats (CPU, memory, disk) and lets users view system logs.

## Getting Started

```bash
git clone https://github.com/benblake0/linux-web-server.git
cd linux-web-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000`, login with `admin` / `admin`. Click "Monitor" in the sidebar — you'll see a placeholder page. That's what you're replacing.

## Your Files

| File | What it does |
|------|-------------|
| `blueprints/monitor.py` | Your backend routes (Python) |
| `templates/monitor/index.html` | Your main dashboard template (HTML) |
| `templates/monitor/logs.html` | System logs page (HTML) |

Don't touch other blueprints or `app.py`.

## Create a Feature Branch

```bash
git checkout -b feature/system-monitoring
```

## What to Build

### Routes

| Route | Method | What it does |
|-------|--------|-------------|
| `/monitor/` | GET | Dashboard with CPU, memory, disk stats |
| `/monitor/logs` | GET | View system log entries |

### The Key Library: `psutil`

`psutil` is already in `requirements.txt`. It gives you system stats in Python:

```python
import psutil

# CPU usage (percent)
cpu_percent = psutil.cpu_percent(interval=1)

# Memory
mem = psutil.virtual_memory()
mem_total = mem.total      # bytes
mem_used = mem.used        # bytes
mem_percent = mem.percent  # percentage

# Disk usage
disk = psutil.disk_usage('/')
disk_total = disk.total
disk_used = disk.used
disk_percent = disk.percent
```

### Implementation Guide

Here's the full `blueprints/monitor.py`:

```python
import psutil
from flask import Blueprint, render_template
from utils.decorators import login_required

monitor_bp = Blueprint('monitor', __name__, url_prefix='/monitor')


def bytes_to_gb(b):
    """Convert bytes to GB, rounded to 1 decimal."""
    return round(b / (1024 ** 3), 1)


@monitor_bp.route('/')
@login_required
def index():
    """System monitoring dashboard."""
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
    """View recent system log entries."""
    log_lines = []
    log_file = '/var/log/syslog'  # On Ubuntu; use '/var/log/system.log' on macOS

    try:
        with open(log_file, 'r') as f:
            # Read last 100 lines
            all_lines = f.readlines()
            log_lines = all_lines[-100:]
    except (FileNotFoundError, PermissionError):
        log_lines = ['Log file not accessible. Run the server with appropriate permissions.']

    return render_template('monitor/logs.html', log_lines=log_lines)
```

### Template: `templates/monitor/index.html`

```html
{% extends "base.html" %}
{% block title %}Monitor — NAS Server{% endblock %}

{% block content %}
<h1>System Monitor</h1>
<!-- Auto-refresh every 5 seconds -->
<meta http-equiv="refresh" content="5">

<div class="card-grid">
    <div class="card">
        <h3>CPU Usage</h3>
        <p class="card-number">{{ cpu_percent }}%</p>
    </div>
    <div class="card">
        <h3>Memory</h3>
        <p class="card-number">{{ memory.percent }}%</p>
        <p>{{ memory.used }} GB / {{ memory.total }} GB</p>
    </div>
    <div class="card">
        <h3>Disk</h3>
        <p class="card-number">{{ disk.percent }}%</p>
        <p>{{ disk.used }} GB / {{ disk.total }} GB</p>
    </div>
</div>

<div style="margin-top: 30px;">
    <a href="{{ url_for('monitor.logs') }}" class="btn btn-primary">View System Logs</a>
</div>
{% endblock %}
```

### Template: `templates/monitor/logs.html`

```html
{% extends "base.html" %}
{% block title %}System Logs — NAS Server{% endblock %}

{% block content %}
<h1>System Logs</h1>
<a href="{{ url_for('monitor.index') }}">Back to Monitor</a>

<pre style="background: #1a1a2e; color: #ccc; padding: 20px; border-radius: 8px; margin-top: 20px; max-height: 600px; overflow-y: scroll; font-size: 0.85rem;">
{% for line in log_lines %}{{ line }}{% endfor %}
</pre>
{% endblock %}
```

### Key Things to Remember

1. **Only `@login_required`** — this is read-only data, any logged-in user can view it
2. **`psutil` handles everything** — no need to run shell commands for CPU/memory/disk
3. **Log file access** — on the Ubuntu VM the log is at `/var/log/syslog`. The Flask process needs read permission (run as root or add the user to the `adm` group: `sudo usermod -a -G adm nasadmin`)
4. **Auto-refresh** — the `<meta http-equiv="refresh" content="5">` tag refreshes the page every 5 seconds. Simple and effective, no JavaScript needed.

### Nice Extras (if you have time)

- Show a progress bar for CPU/memory/disk instead of just a number
- Show uptime (`psutil.boot_time()`)
- Show network stats (`psutil.net_io_counters()`)
- Filter logs by keyword

## Testing

Run existing tests to make sure you didn't break anything:

```bash
python3 -m pytest tests/ -v
```

## When You're Done

```bash
git add blueprints/monitor.py templates/monitor/
git commit -m "feat: system monitoring with CPU, memory, disk, and logs"
git push origin feature/system-monitoring
```

Then open a Pull Request on GitHub.
