# Backup & Restore Module — Guide for Bhavya

You own the **Backup & Restore** module. This lets admins create backups of the NAS storage, schedule automatic backups, and restore from previous backups.

This is the second hardest module — it involves file archiving, scheduling, and restore logic. Take it step by step.

## Getting Started

```bash
git clone https://github.com/benblake0/linux-web-server.git
cd linux-web-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000`, login with `admin` / `admin`. Click "Backups" in the sidebar — you'll see a placeholder page. That's what you're replacing.

## Your Files

| File | What it does |
|------|-------------|
| `blueprints/backup.py` | Your backend routes (Python) |
| `templates/backup/index.html` | Backup list + create/schedule forms (HTML) |

Don't touch other blueprints or `app.py`.

## Create a Feature Branch

```bash
git checkout -b feature/backup-restore
```

## What to Build

### Routes

| Route | Method | What it does |
|-------|--------|-------------|
| `/backup/` | GET | List all backups |
| `/backup/create` | POST | Create a manual backup now |
| `/backup/schedule` | GET/POST | View and set backup schedule |
| `/backup/restore/<id>` | POST | Restore from a specific backup |
| `/backup/<id>/delete` | POST | Delete a backup |

### How It Works

- **Backups** = compressed `.tar.gz` archives of the NAS storage directory
- **Storage directory** (what gets backed up): `config.NAS_STORAGE` (defaults to `./storage/`)
- **Backup directory** (where archives go): `config.NAS_BACKUPS` (defaults to `./backups/`)
- **Backup metadata** is stored in the `backups` database table:

```sql
CREATE TABLE backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filepath TEXT NOT NULL,
    size INTEGER,
    type TEXT NOT NULL DEFAULT 'manual',  -- 'manual' or 'scheduled'
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Key Libraries

- `shutil` (built-in) — for creating `.tar.gz` archives
- `APScheduler` (already in `requirements.txt`) — for scheduling automatic backups

### Implementation Guide

Here's the full `blueprints/backup.py`:

```python
import os
import shutil
import tarfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from database import get_db
from utils.decorators import admin_required
import config

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

# APScheduler setup (in-process scheduler)
scheduler = None


def get_scheduler():
    """Lazy-init the scheduler."""
    global scheduler
    if scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.start()
    return scheduler


def perform_backup(backup_type='manual', user_id=None):
    """Create a .tar.gz backup of the NAS storage directory."""
    os.makedirs(config.NAS_BACKUPS, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'backup_{timestamp}'
    archive_path = os.path.join(config.NAS_BACKUPS, backup_name)

    # Create the archive
    shutil.make_archive(archive_path, 'gztar', config.NAS_STORAGE)

    archive_file = archive_path + '.tar.gz'
    size = os.path.getsize(archive_file)

    # Save metadata to database
    db = get_db()
    db.execute(
        'INSERT INTO backups (name, filepath, size, type, created_by) VALUES (?, ?, ?, ?, ?)',
        (backup_name, archive_file, size, backup_type, user_id)
    )
    db.commit()
    db.close()

    return backup_name


@backup_bp.route('/')
@admin_required
def index():
    """List all backups."""
    db = get_db()
    backups = db.execute('SELECT * FROM backups ORDER BY created_at DESC').fetchall()
    db.close()

    # Check if a scheduled job exists
    sched = get_scheduler()
    scheduled_job = sched.get_job('nas_backup')

    return render_template('backup/index.html',
        backups=backups,
        scheduled_job=scheduled_job
    )


@backup_bp.route('/create', methods=['POST'])
@admin_required
def create():
    """Create a manual backup."""
    try:
        name = perform_backup(backup_type='manual', user_id=session['user_id'])
        flash(f'Backup "{name}" created.', 'success')
    except Exception as e:
        flash(f'Backup failed: {str(e)}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/schedule', methods=['GET', 'POST'])
@admin_required
def schedule():
    """Set up scheduled backups."""
    sched = get_scheduler()

    if request.method == 'POST':
        interval_hours = int(request.form.get('interval', 24))

        # Remove existing job if any
        if sched.get_job('nas_backup'):
            sched.remove_job('nas_backup')

        # Add new scheduled job
        sched.add_job(
            perform_backup,
            'interval',
            hours=interval_hours,
            id='nas_backup',
            kwargs={'backup_type': 'scheduled', 'user_id': session['user_id']}
        )

        flash(f'Automatic backup scheduled every {interval_hours} hours.', 'success')
        return redirect(url_for('backup.index'))

    return render_template('backup/schedule.html')


@backup_bp.route('/restore/<int:backup_id>', methods=['POST'])
@admin_required
def restore(backup_id):
    """Restore from a backup."""
    db = get_db()
    backup = db.execute('SELECT * FROM backups WHERE id = ?', (backup_id,)).fetchone()
    db.close()

    if not backup:
        flash('Backup not found.', 'error')
        return redirect(url_for('backup.index'))

    archive_path = backup['filepath']
    if not os.path.exists(archive_path):
        flash('Backup file not found on disk.', 'error')
        return redirect(url_for('backup.index'))

    try:
        # Clear current storage
        if os.path.exists(config.NAS_STORAGE):
            shutil.rmtree(config.NAS_STORAGE)
        os.makedirs(config.NAS_STORAGE, exist_ok=True)

        # Extract backup
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=config.NAS_STORAGE)

        flash(f'Restored from backup "{backup["name"]}".', 'success')
    except Exception as e:
        flash(f'Restore failed: {str(e)}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/<int:backup_id>/delete', methods=['POST'])
@admin_required
def delete(backup_id):
    """Delete a backup."""
    db = get_db()
    backup = db.execute('SELECT * FROM backups WHERE id = ?', (backup_id,)).fetchone()

    if backup and os.path.exists(backup['filepath']):
        os.remove(backup['filepath'])

    db.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
    db.commit()
    db.close()

    flash('Backup deleted.', 'success')
    return redirect(url_for('backup.index'))
```

### Template: `templates/backup/index.html`

```html
{% extends "base.html" %}
{% block title %}Backups — NAS Server{% endblock %}

{% block content %}
<h1>Backup & Restore</h1>

<div style="display: flex; gap: 10px; margin-bottom: 20px;">
    <form method="POST" action="{{ url_for('backup.create') }}">
        <button type="submit" class="btn btn-primary">Create Backup Now</button>
    </form>
    <a href="{{ url_for('backup.schedule') }}" class="btn btn-primary">Schedule Backups</a>
</div>

{% if scheduled_job %}
<p>Automatic backups: <strong>Every {{ scheduled_job.trigger.interval }} </strong></p>
{% else %}
<p>No automatic backups scheduled.</p>
{% endif %}

<table style="margin-top: 20px;">
    <thead>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Size</th>
            <th>Created</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for backup in backups %}
        <tr>
            <td>{{ backup['name'] }}</td>
            <td>{{ backup['type'] }}</td>
            <td>{{ (backup['size'] / 1024 / 1024) | round(1) }} MB</td>
            <td>{{ backup['created_at'] }}</td>
            <td>
                <form method="POST" action="{{ url_for('backup.restore', backup_id=backup['id']) }}" style="display:inline;">
                    <button type="submit" class="btn btn-primary" onclick="return confirm('Restore from this backup? Current files will be replaced.')">Restore</button>
                </form>
                <form method="POST" action="{{ url_for('backup.delete', backup_id=backup['id']) }}" style="display:inline;">
                    <button type="submit" class="btn btn-danger" onclick="return confirm('Delete this backup?')">Delete</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### Template: `templates/backup/schedule.html`

```html
{% extends "base.html" %}
{% block title %}Schedule Backups — NAS Server{% endblock %}

{% block content %}
<h1>Schedule Automatic Backups</h1>
<form method="POST" style="max-width: 500px;">
    <label for="interval">Backup Interval (hours)</label>
    <select id="interval" name="interval">
        <option value="1">Every 1 hour</option>
        <option value="6">Every 6 hours</option>
        <option value="12">Every 12 hours</option>
        <option value="24" selected>Every 24 hours (daily)</option>
    </select>
    <button type="submit">Set Schedule</button>
</form>
<a href="{{ url_for('backup.index') }}">Back to Backups</a>
{% endblock %}
```

### Key Things to Remember

1. **All routes use `@admin_required`** — only admins can manage backups
2. **`shutil.make_archive`** creates the `.tar.gz` — you don't need to use `tar` commands
3. **`tarfile.open`** extracts for restore — use `extractall()`
4. **APScheduler runs in-process** — the schedule is lost when the server restarts. That's fine for a demo. If you want persistence, save the interval to a config file and reload on startup.
5. **Restore is destructive** — it clears the storage directory first. The confirmation dialog in the template helps prevent accidents.

### Gotchas

- The `perform_backup` function is called both by the manual route AND by the scheduler. Make sure it works standalone (the scheduler calls it without a request context).
- `get_db()` inside `perform_backup` may not work from the scheduler context if the database path is relative. Use `config.DATABASE` which is an absolute path, so it should be fine.

## Testing

Run existing tests to make sure you didn't break anything:

```bash
python3 -m pytest tests/ -v
```

## When You're Done

```bash
git add blueprints/backup.py templates/backup/
git commit -m "feat: backup and restore with scheduling"
git push origin feature/backup-restore
```

Then open a Pull Request on GitHub.
