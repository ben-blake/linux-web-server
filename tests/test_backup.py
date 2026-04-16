"""Tests for the backup & restore blueprint."""

import os
import tarfile
import tempfile

import config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_backup(client):
    """Trigger a manual backup via POST and follow redirects to the list page."""
    return client.post("/backup/create", follow_redirects=True)


def _get_backup_id(app, name_like=""):
    """Return the DB id of the most-recently created backup."""
    with app.app_context():
        from database import get_db

        db = get_db()
        if name_like:
            row = db.execute(
                "SELECT id FROM backups WHERE name LIKE ? ORDER BY id DESC LIMIT 1",
                (f"%{name_like}%",),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT id FROM backups ORDER BY id DESC LIMIT 1",
            ).fetchone()
        db.close()
    return row["id"] if row else None


# ---------------------------------------------------------------------------
# Auth / permission guards
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_index_requires_login(self, client):
        resp = client.get("/backup/", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "")

    def test_create_requires_login(self, client):
        resp = client.post("/backup/create", follow_redirects=False)
        assert resp.status_code == 302

    def test_schedule_requires_login(self, client):
        resp = client.get("/backup/schedule", follow_redirects=False)
        assert resp.status_code == 302

    def test_restore_requires_login(self, client):
        resp = client.post("/backup/restore/1", follow_redirects=False)
        assert resp.status_code == 302

    def test_delete_requires_login(self, client):
        resp = client.post("/backup/1/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_regular_user_cannot_access_backup(self, user_client):
        resp = user_client.get("/backup/")
        assert resp.status_code == 403

    def test_regular_user_cannot_create_backup(self, user_client):
        resp = user_client.post("/backup/create", follow_redirects=False)
        assert resp.status_code == 403

    def test_admin_can_view_backup_list(self, admin_client):
        resp = admin_client.get("/backup/")
        assert resp.status_code == 200
        assert b"Backup" in resp.data


# ---------------------------------------------------------------------------
# Index / listing
# ---------------------------------------------------------------------------


class TestBackupIndex:
    def test_empty_state_shown_when_no_backups(self, admin_client):
        resp = admin_client.get("/backup/")
        assert b"No backups yet" in resp.data

    def test_backup_appears_in_list_after_creation(self, admin_client):
        _create_backup(admin_client)
        resp = admin_client.get("/backup/")
        assert b"backup_" in resp.data


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestBackupCreate:
    def test_create_produces_archive_on_disk(self, admin_client):
        _create_backup(admin_client)
        archives = [f for f in os.listdir(config.NAS_BACKUPS) if f.endswith(".tar.gz")]
        assert len(archives) == 1

    def test_create_flash_success(self, admin_client):
        resp = _create_backup(admin_client)
        assert b"created successfully" in resp.data

    def test_create_download_route_serves_file(self, admin_client, app):
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        resp = admin_client.get(f"/backup/{backup_id}/download")
        assert resp.status_code == 200
        assert resp.content_type in (
            "application/gzip",
            "application/x-tar",
            "application/octet-stream",
        )
        assert resp.data[:2] == b"\x1f\x8b"  # gzip magic bytes

    def test_create_records_in_database(self, admin_client, app):
        _create_backup(admin_client)
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT * FROM backups ORDER BY id DESC LIMIT 1"
            ).fetchone()
            db.close()
        assert row is not None
        assert row["type"] == "manual"
        assert row["size"] > 0

    def test_create_multiple_backups(self, admin_client, app):
        _create_backup(admin_client)
        _create_backup(admin_client)
        with app.app_context():
            from database import get_db

            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM backups").fetchone()[0]
            db.close()
        assert count == 2

    def test_archive_is_valid_tar_gz(self, admin_client):
        _create_backup(admin_client)
        archives = [
            os.path.join(config.NAS_BACKUPS, f)
            for f in os.listdir(config.NAS_BACKUPS)
            if f.endswith(".tar.gz")
        ]
        assert tarfile.is_tarfile(archives[0])


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestBackupDelete:
    def test_delete_removes_archive_file(self, admin_client, app):
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        admin_client.post(f"/backup/{backup_id}/delete", follow_redirects=True)

        archives = [f for f in os.listdir(config.NAS_BACKUPS) if f.endswith(".tar.gz")]
        assert len(archives) == 0

    def test_delete_removes_db_record(self, admin_client, app):
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        admin_client.post(f"/backup/{backup_id}/delete", follow_redirects=True)

        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT id FROM backups WHERE id = ?", (backup_id,)
            ).fetchone()
            db.close()
        assert row is None

    def test_delete_flash_success(self, admin_client, app):
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        resp = admin_client.post(f"/backup/{backup_id}/delete", follow_redirects=True)
        assert b"deleted" in resp.data.lower()

    def test_delete_nonexistent_backup_is_safe(self, admin_client):
        resp = admin_client.post("/backup/9999/delete", follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_missing_file_still_removes_db_record(self, admin_client, app):
        """If the archive was already removed from disk, the DB record is still cleaned up."""
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)

        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT filepath FROM backups WHERE id = ?", (backup_id,)
            ).fetchone()
            db.close()
        os.remove(row["filepath"])

        admin_client.post(f"/backup/{backup_id}/delete", follow_redirects=True)

        with app.app_context():
            from database import get_db

            db = get_db()
            gone = db.execute(
                "SELECT id FROM backups WHERE id = ?", (backup_id,)
            ).fetchone()
            db.close()
        assert gone is None


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


class TestBackupRestore:
    def test_restore_recovers_files(self, admin_client, app):
        """A file uploaded before backup is recoverable via restore."""
        import io

        # Upload a sentinel file
        admin_client.post(
            "/files/upload",
            data={"path": "", "file": (io.BytesIO(b"sentinel"), "sentinel.txt")},
            content_type="multipart/form-data",
        )
        # Create backup
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)

        # Delete the file from disk
        os.remove(os.path.join(config.NAS_STORAGE, "sentinel.txt"))
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "sentinel.txt"))

        # Restore
        resp = admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)
        assert resp.status_code == 200
        assert os.path.exists(os.path.join(config.NAS_STORAGE, "sentinel.txt"))

    def test_restore_flash_success(self, admin_client, app):
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        resp = admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)
        assert b"Restored" in resp.data

    def test_restore_missing_backup_id(self, admin_client):
        resp = admin_client.post("/backup/restore/9999", follow_redirects=True)
        assert b"not found" in resp.data.lower()

    def test_restore_resyncs_files_table(self, admin_client, app):
        """After restore the files table reflects what is on disk."""
        import io

        # Upload two files before backup
        for name in ("alpha.txt", "beta.txt"):
            admin_client.post(
                "/files/upload",
                data={"path": "", "file": (io.BytesIO(b"data"), name)},
                content_type="multipart/form-data",
            )
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)

        # Upload a third file AFTER backup (should disappear after restore)
        admin_client.post(
            "/files/upload",
            data={"path": "", "file": (io.BytesIO(b"extra"), "gamma.txt")},
            content_type="multipart/form-data",
        )

        # Restore — gamma.txt should vanish, alpha and beta should be back
        admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)

        with app.app_context():
            from database import get_db

            db = get_db()
            rows = db.execute(
                "SELECT filename, uploaded_by FROM files ORDER BY filename"
            ).fetchall()
            db.close()

        names = {r["filename"] for r in rows}
        assert names == {"alpha.txt", "beta.txt"}
        # Ownership must be preserved — both files were uploaded by admin (id=1)
        assert all(r["uploaded_by"] is not None for r in rows), (
            "uploaded_by should be preserved after restore, not set to NULL"
        )

    def test_restore_preserves_per_user_attribution(self, admin_client, client, app):
        """After restore, the monitor's per-user storage query must show the
        original uploader's bytes, not zero. Regression test for the bug where
        a non-admin user's uploads lost attribution after restore."""
        import io

        # Create a non-admin user with write permission
        admin_client.post(
            "/users/create",
            data={
                "username": "alice",
                "password": "alicepass",
                "role": "user",
                "permissions": "read,write",
            },
        )

        # Log in as alice and upload a file
        client.get("/logout")
        client.post("/login", data={"username": "alice", "password": "alicepass"})
        client.post(
            "/files/upload",
            data={"path": "", "file": (io.BytesIO(b"hello world"), "alice.txt")},
            content_type="multipart/form-data",
        )

        # Capture per-user storage before backup
        from blueprints.monitor import _per_user_storage

        with app.app_context():
            pre = {u["username"]: int(u["used_bytes"]) for u in _per_user_storage()}
        assert pre.get("alice", 0) > 0, "precondition: alice should have bytes"

        # Back in as admin, create a backup, then restore
        client.get("/logout")
        admin_client.post("/login", data={"username": "admin", "password": "admin"})
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)

        # Per-user storage should match exactly what it was before the backup
        with app.app_context():
            post = {u["username"]: int(u["used_bytes"]) for u in _per_user_storage()}
        assert post.get("alice", 0) == pre.get("alice", 0), (
            f"alice's attributed bytes changed from {pre.get('alice')} to {post.get('alice')} after restore"
        )

    def test_restore_preserves_attribution_with_noncanonical_db_path(
        self, admin_client, app
    ):
        """If the DB has a filepath that doesn't match disk realpath exactly
        (injected ./ segments, trailing slash, etc.), restore must still
        preserve uploaded_by attribution.

        This is the most likely cause of the production bug — DB records
        from an older code path may have filepaths that don't match what
        os.walk returns after extraction."""
        import io

        # Upload a file (admin = user id 1)
        admin_client.post(
            "/files/upload",
            data={"path": "", "file": (io.BytesIO(b"data"), "a.txt")},
            content_type="multipart/form-data",
        )

        # Mangle the DB filepath to a non-canonical-but-valid form
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute("SELECT id, filepath FROM files").fetchone()
            noncanonical = row["filepath"].replace("/", "/./", 1)
            db.execute(
                "UPDATE files SET filepath = ? WHERE id = ?",
                (noncanonical, row["id"]),
            )
            db.commit()
            db.close()

        _create_backup(admin_client)
        backup_id = _get_backup_id(app)
        admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)

        with app.app_context():
            from database import get_db

            db = get_db()
            rows = db.execute("SELECT uploaded_by FROM files").fetchall()
            db.close()

        assert all(r["uploaded_by"] is not None for r in rows), (
            "attribution should survive non-canonical DB paths after restore"
        )

    def test_restore_missing_archive_file(self, admin_client, app):
        """If the archive file is gone from disk, an error is shown."""
        _create_backup(admin_client)
        backup_id = _get_backup_id(app)

        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT filepath FROM backups WHERE id = ?", (backup_id,)
            ).fetchone()
            db.close()
        os.remove(row["filepath"])

        resp = admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)
        assert b"not found on disk" in resp.data


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class TestBackupSchedule:
    def test_schedule_page_renders(self, admin_client):
        resp = admin_client.get("/backup/schedule")
        assert resp.status_code == 200
        assert b"Schedule" in resp.data

    def test_schedule_post_redirects_to_index(self, admin_client):
        resp = admin_client.post(
            "/backup/schedule", data={"interval": "6"}, follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Backup" in resp.data

    def test_schedule_post_flash_success(self, admin_client):
        resp = admin_client.post(
            "/backup/schedule", data={"interval": "12"}, follow_redirects=True
        )
        assert b"scheduled" in resp.data.lower()

    def test_schedule_non_integer_interval_rejected(self, admin_client):
        resp = admin_client.post(
            "/backup/schedule", data={"interval": "abc"}, follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Invalid interval" in resp.data

    def test_schedule_zero_interval_rejected(self, admin_client):
        resp = admin_client.post(
            "/backup/schedule", data={"interval": "0"}, follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Invalid interval" in resp.data

    def test_schedule_negative_interval_rejected(self, admin_client):
        resp = admin_client.post(
            "/backup/schedule", data={"interval": "-5"}, follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Invalid interval" in resp.data


# ---------------------------------------------------------------------------
# Restore security
# ---------------------------------------------------------------------------


class TestRestoreSecurity:
    def test_restore_rejects_path_traversal_in_archive(self, admin_client, app):
        """A tar archive containing path traversal entries is rejected during restore."""

        malicious_tar = os.path.join(config.NAS_BACKUPS, "malicious.tar.gz")
        sentinel = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        sentinel.write(b"malicious content")
        sentinel.close()

        with tarfile.open(malicious_tar, "w:gz") as tar:
            tar.add(sentinel.name, arcname="../evil.txt")
        os.unlink(sentinel.name)

        with app.app_context():
            from database import get_db

            db = get_db()
            db.execute(
                "INSERT INTO backups (name, filepath, size, type, created_by) VALUES (?, ?, ?, ?, ?)",
                ("malicious", malicious_tar, 100, "manual", None),
            )
            db.commit()
            backup_id = db.execute(
                "SELECT id FROM backups ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
            db.close()

        resp = admin_client.post(f"/backup/restore/{backup_id}", follow_redirects=True)
        assert resp.status_code == 200
        assert b"failed" in resp.data.lower()
        evil_path = os.path.join(os.path.dirname(config.NAS_STORAGE), "evil.txt")
        assert not os.path.exists(evil_path)
