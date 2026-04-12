import os
import shutil
import tarfile
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils.decorators import admin_required
import config

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

_scheduler = None


def _get_scheduler():
    """Lazy-init the APScheduler background scheduler."""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def perform_backup(backup_type='manual', user_id=None):
    """Create a .tar.gz backup of NAS_STORAGE and record it in the database.

    Safe to call outside a request context (e.g. from the scheduler).
    """
    os.makedirs(config.NAS_BACKUPS, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_name = f'backup_{timestamp}'
    archive_base = os.path.join(config.NAS_BACKUPS, backup_name)

    shutil.make_archive(archive_base, 'gztar', config.NAS_STORAGE)

    archive_path = archive_base + '.tar.gz'
    size = os.path.getsize(archive_path)

    db = get_db()
    db.execute(
        'INSERT INTO backups (name, filepath, size, type, created_by) VALUES (?, ?, ?, ?, ?)',
        (backup_name, archive_path, size, backup_type, user_id),
    )
    db.commit()
    db.close()

    return backup_name


@backup_bp.route('/')
@admin_required
def index():
    """List all backups and show current schedule."""
    db = get_db()
    backups = db.execute('SELECT * FROM backups ORDER BY created_at DESC').fetchall()
    db.close()

    sched = _get_scheduler()
    scheduled_job = sched.get_job('nas_backup')

    return render_template('backup/index.html',
                           backups=backups,
                           scheduled_job=scheduled_job)


@backup_bp.route('/create', methods=['POST'])
@admin_required
def create():
    """Trigger an immediate manual backup."""
    try:
        name = perform_backup(backup_type='manual', user_id=session['user_id'])
        flash(f'Backup "{name}" created successfully.', 'success')
    except Exception as e:
        flash(f'Backup failed: {e}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/schedule', methods=['GET', 'POST'])
@admin_required
def schedule():
    """View or update the automatic backup schedule."""
    sched = _get_scheduler()

    if request.method == 'POST':
        interval_hours = int(request.form.get('interval', 24))

        if sched.get_job('nas_backup'):
            sched.remove_job('nas_backup')

        sched.add_job(
            perform_backup,
            'interval',
            hours=interval_hours,
            id='nas_backup',
            kwargs={'backup_type': 'scheduled', 'user_id': session['user_id']},
        )

        flash(f'Automatic backup scheduled every {interval_hours} hour(s).', 'success')
        return redirect(url_for('backup.index'))

    current_job = sched.get_job('nas_backup')
    return render_template('backup/schedule.html', current_job=current_job)


@backup_bp.route('/restore/<int:backup_id>', methods=['POST'])
@admin_required
def restore(backup_id):
    """Restore NAS storage from a backup archive."""
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
        if os.path.exists(config.NAS_STORAGE):
            shutil.rmtree(config.NAS_STORAGE)
        os.makedirs(config.NAS_STORAGE, exist_ok=True)

        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=config.NAS_STORAGE)

        flash(f'Restored from backup "{backup["name"]}".', 'success')
    except Exception as e:
        flash(f'Restore failed: {e}', 'error')

    return redirect(url_for('backup.index'))


@backup_bp.route('/<int:backup_id>/delete', methods=['POST'])
@admin_required
def delete(backup_id):
    """Delete a backup record and its archive file."""
    db = get_db()
    backup = db.execute('SELECT * FROM backups WHERE id = ?', (backup_id,)).fetchone()

    if backup and os.path.exists(backup['filepath']):
        os.remove(backup['filepath'])

    db.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
    db.commit()
    db.close()

    flash('Backup deleted.', 'success')
    return redirect(url_for('backup.index'))
