import os
import shutil
import tarfile
from datetime import datetime
from typing import Any, Optional

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from flask.typing import ResponseReturnValue

import config
from blueprints.auth import SESSION_USER_ID
from database import get_db
from utils.decorators import admin_required

backup_bp = Blueprint("backup", __name__, url_prefix="/backup")

_scheduler = None


def restore_schedule_from_db() -> None:
    """Re-register the backup job from the database after a server restart."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'backup_interval_hours'"
        ).fetchone()
    finally:
        db.close()

    if row:
        interval_hours = int(row["value"])
        sched = _get_scheduler()
        if not sched.get_job("nas_backup"):
            sched.add_job(
                perform_backup,
                "interval",
                hours=interval_hours,
                id="nas_backup",
                kwargs={"backup_type": "scheduled", "user_id": None},
            )


def _get_scheduler() -> Any:
    """Lazy-init the APScheduler background scheduler."""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def perform_backup(backup_type: str = "manual", user_id: Optional[int] = None) -> str:
    """Create a .tar.gz backup of NAS_STORAGE and record it in the database.

    Safe to call outside a request context (e.g. from the scheduler).
    """
    os.makedirs(config.NAS_BACKUPS, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"backup_{timestamp}"
    archive_base = os.path.join(config.NAS_BACKUPS, backup_name)

    shutil.make_archive(archive_base, "gztar", config.NAS_STORAGE)

    archive_path = archive_base + ".tar.gz"
    size = os.path.getsize(archive_path)

    db = get_db()
    try:
        db.execute(
            "INSERT INTO backups (name, filepath, size, type, created_by) VALUES (?, ?, ?, ?, ?)",
            (backup_name, archive_path, size, backup_type, user_id),
        )
        db.commit()
    finally:
        db.close()

    return backup_name


@backup_bp.route("/")
@admin_required
def index() -> ResponseReturnValue:
    """List all backups and show current schedule."""
    db = get_db()
    try:
        backups = db.execute(
            "SELECT * FROM backups ORDER BY created_at DESC"
        ).fetchall()
    finally:
        db.close()

    sched = _get_scheduler()
    scheduled_job = sched.get_job("nas_backup")

    return render_template(
        "backup/index.html", backups=backups, scheduled_job=scheduled_job
    )


@backup_bp.route("/create", methods=["POST"])
@admin_required
def create() -> ResponseReturnValue:
    """Trigger an immediate manual backup."""
    try:
        name = perform_backup(backup_type="manual", user_id=session[SESSION_USER_ID])
        flash(f'Backup "{name}" created successfully.', "success")
    except OSError as e:
        flash(f"Backup failed: {e}", "error")

    return redirect(url_for("backup.index"))


@backup_bp.route("/<int:backup_id>/download")
@admin_required
def download(backup_id: int) -> ResponseReturnValue:
    """Download a backup archive to the local machine."""
    db = get_db()
    try:
        backup = db.execute(
            "SELECT * FROM backups WHERE id = ?", (backup_id,)
        ).fetchone()
    finally:
        db.close()

    if not backup:
        flash("Backup not found.", "error")
        return redirect(url_for("backup.index"))

    archive_path = backup["filepath"]
    if not os.path.exists(archive_path):
        flash("Backup file not found on disk.", "error")
        return redirect(url_for("backup.index"))

    return send_file(
        archive_path,
        as_attachment=True,
        download_name=backup["name"] + ".tar.gz",
    )


@backup_bp.route("/schedule", methods=["GET", "POST"])
@admin_required
def schedule() -> ResponseReturnValue:
    """View or update the automatic backup schedule."""
    sched = _get_scheduler()

    if request.method == "POST":
        try:
            interval_hours = int(request.form.get("interval", 24))
            if interval_hours < 1:
                raise ValueError("Interval must be at least 1 hour.")
        except (ValueError, TypeError):
            flash(
                "Invalid interval. Enter a whole number of hours (minimum 1).", "error"
            )
            return redirect(url_for("backup.schedule"))

        if sched.get_job("nas_backup"):
            sched.remove_job("nas_backup")

        sched.add_job(
            perform_backup,
            "interval",
            hours=interval_hours,
            id="nas_backup",
            kwargs={"backup_type": "scheduled", "user_id": session[SESSION_USER_ID]},
        )

        db = get_db()
        try:
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_interval_hours', ?)",
                (str(interval_hours),),
            )
            db.commit()
        finally:
            db.close()

        flash(f"Automatic backup scheduled every {interval_hours} hour(s).", "success")
        return redirect(url_for("backup.index"))

    current_job = sched.get_job("nas_backup")
    return render_template("backup/schedule.html", current_job=current_job)


def _resync_files_table() -> None:
    """Rebuild the files table to match what is actually on disk after a restore.

    Preserves uploaded_by attribution for any path that was already tracked
    before the restore. Files in the archive that had no prior DB record get
    NULL for uploaded_by.
    """
    db = get_db()
    try:
        # Remember who owned each path before we wipe records.
        prior: dict[str, Optional[int]] = {
            row["filepath"]: row["uploaded_by"]
            for row in db.execute("SELECT filepath, uploaded_by FROM files").fetchall()
        }

        db.execute("DELETE FROM files")

        storage_root = os.path.realpath(config.NAS_STORAGE)
        for dirpath, _dirnames, filenames in os.walk(storage_root):
            for name in filenames:
                full_path = os.path.realpath(os.path.join(dirpath, name))
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    continue
                db.execute(
                    "INSERT INTO files (filename, filepath, size, uploaded_by)"
                    " VALUES (?, ?, ?, ?)",
                    (name, full_path, size, prior.get(full_path)),
                )
        db.commit()
    finally:
        db.close()


@backup_bp.route("/restore/<int:backup_id>", methods=["POST"])
@admin_required
def restore(backup_id: int) -> ResponseReturnValue:
    """Restore NAS storage from a backup archive."""
    db = get_db()
    try:
        backup = db.execute(
            "SELECT * FROM backups WHERE id = ?", (backup_id,)
        ).fetchone()
    finally:
        db.close()

    if not backup:
        flash("Backup not found.", "error")
        return redirect(url_for("backup.index"))

    archive_path = backup["filepath"]
    if not os.path.exists(archive_path):
        flash("Backup file not found on disk.", "error")
        return redirect(url_for("backup.index"))

    try:
        if not tarfile.is_tarfile(archive_path):
            raise ValueError("Backup archive is not a valid tar file.")

        # Clear contents without deleting the directory itself.
        # Deleting /srv/nas requires write permission on /srv (owned by root),
        # but clearing its contents only needs permission on /srv/nas itself.
        if os.path.exists(config.NAS_STORAGE):
            for item in os.listdir(config.NAS_STORAGE):
                item_path = os.path.join(config.NAS_STORAGE, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        else:
            os.makedirs(config.NAS_STORAGE, exist_ok=True)

        storage_root = os.path.normpath(config.NAS_STORAGE)
        with tarfile.open(archive_path, "r:gz") as tar:
            safe_members = []
            for member in tar.getmembers():
                # Skip the archive root entry to avoid touching /srv/nas itself
                if os.path.normpath(member.name) in (".", ""):
                    continue
                dest = os.path.normpath(os.path.join(storage_root, member.name))
                if not dest.startswith(storage_root + os.sep) and dest != storage_root:
                    raise ValueError(f"Unsafe path in archive: {member.name}")
                safe_members.append(member)
            tar.extractall(path=config.NAS_STORAGE, members=safe_members)  # nosec B202 — members validated above

        _resync_files_table()

        flash(f'Restored from backup "{backup["name"]}".', "success")
    except (OSError, tarfile.TarError, ValueError) as e:
        flash(f"Restore failed: {e}", "error")

    return redirect(url_for("backup.index"))


@backup_bp.route("/<int:backup_id>/delete", methods=["POST"])
@admin_required
def delete(backup_id: int) -> ResponseReturnValue:
    """Delete a backup record and its archive file."""
    db = get_db()
    try:
        backup = db.execute(
            "SELECT * FROM backups WHERE id = ?", (backup_id,)
        ).fetchone()

        if backup:
            filepath = os.path.abspath(backup["filepath"])
            backup_dir = os.path.abspath(config.NAS_BACKUPS)
            if filepath.startswith(backup_dir + os.sep) and os.path.exists(filepath):
                os.remove(filepath)

        db.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        db.commit()
    finally:
        db.close()

    flash("Backup deleted.", "success")
    return redirect(url_for("backup.index"))
