import io
import os

import config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload(client, filename, content=b"hello", path=""):
    return client.post(
        "/files/upload",
        data={"path": path, "file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def _mkdir(client, name, path=""):
    return client.post(
        "/files/mkdir",
        data={"path": path, "name": name},
        follow_redirects=True,
    )


def _rename(client, old_rel, new_name, parent=""):
    return client.post(
        "/files/rename",
        data={"path": old_rel, "new_name": new_name, "parent_path": parent},
        follow_redirects=True,
    )


def _delete(client, rel, parent=""):
    return client.post(
        "/files/delete",
        data={"path": rel, "parent_path": parent},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Auth / permission guards
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_index_requires_login(self, client):
        resp = client.get("/files/")
        assert resp.status_code == 302
        assert b"/login" in resp.data or "login" in resp.headers.get("Location", "")

    def test_upload_requires_login(self, client):
        resp = client.post("/files/upload", data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_download_requires_login(self, client):
        resp = client.get("/files/download?path=anything", follow_redirects=False)
        assert resp.status_code == 302

    def test_mkdir_requires_login(self, client):
        resp = client.post("/files/mkdir", data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_rename_requires_login(self, client):
        resp = client.post("/files/rename", data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_delete_requires_login(self, client):
        resp = client.post("/files/delete", data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_read_only_user_can_browse(self, user_client):
        resp = user_client.get("/files/")
        assert resp.status_code == 200
        assert b"File Management" in resp.data

    def test_read_only_user_cannot_upload(self, user_client):
        resp = _upload(user_client, "blocked.txt")
        assert resp.status_code == 403

    def test_read_only_user_cannot_mkdir(self, user_client):
        resp = _mkdir(user_client, "blocked")
        assert resp.status_code == 403

    def test_read_only_user_cannot_delete(self, user_client):
        resp = _delete(user_client, "anything")
        assert resp.status_code == 403

    def test_read_only_user_cannot_rename(self, user_client):
        resp = _rename(user_client, "anything", "other")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Browse / index
# ---------------------------------------------------------------------------


class TestBrowse:
    def test_index_shows_storage_summary(self, admin_client):
        resp = admin_client.get("/files/")
        assert resp.status_code == 200
        assert b"items in this folder" in resp.data or b"item" in resp.data

    def test_index_empty_folder(self, admin_client):
        resp = admin_client.get("/files/")
        assert b"This folder is empty" in resp.data

    def test_index_lists_uploaded_file(self, admin_client):
        _upload(admin_client, "visible.txt", b"data")
        resp = admin_client.get("/files/")
        assert b"visible.txt" in resp.data

    def test_index_lists_created_folder(self, admin_client):
        _mkdir(admin_client, "mydir")
        resp = admin_client.get("/files/")
        assert b"mydir" in resp.data

    def test_subfolder_browse(self, admin_client):
        _mkdir(admin_client, "sub")
        _upload(admin_client, "inner.txt", b"x", path="sub")
        resp = admin_client.get("/files/?path=sub")
        assert resp.status_code == 200
        assert b"inner.txt" in resp.data

    def test_breadcrumbs_rendered_for_subfolder(self, admin_client):
        _mkdir(admin_client, "docs")
        resp = admin_client.get("/files/?path=docs")
        assert b"docs" in resp.data
        assert b"Storage root" in resp.data


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestUpload:
    def test_upload_creates_file_on_disk(self, admin_client):
        _upload(admin_client, "hello.txt", b"world")
        assert os.path.isfile(os.path.join(config.NAS_STORAGE, "hello.txt"))

    def test_upload_flash_success(self, admin_client):
        resp = _upload(admin_client, "flash.txt", b"x")
        assert b"Uploaded" in resp.data

    def test_upload_records_in_database(self, admin_client, app):
        _upload(admin_client, "db.txt", b"stored")
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute("SELECT * FROM files WHERE filename = 'db.txt'").fetchone()
            db.close()
        assert row is not None
        assert row["size"] == len(b"stored")

    def test_upload_no_file_selected(self, admin_client):
        resp = admin_client.post(
            "/files/upload",
            data={"path": ""},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"No file selected" in resp.data

    def test_upload_into_subfolder(self, admin_client):
        _mkdir(admin_client, "uploads")
        _upload(admin_client, "nested.txt", b"hi", path="uploads")
        assert os.path.isfile(os.path.join(config.NAS_STORAGE, "uploads", "nested.txt"))

    def test_upload_overwrites_existing_file(self, admin_client):
        _upload(admin_client, "over.txt", b"v1")
        _upload(admin_client, "over.txt", b"v2")
        with open(os.path.join(config.NAS_STORAGE, "over.txt"), "rb") as f:
            assert f.read() == b"v2"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownload:
    def test_download_returns_file_content(self, admin_client):
        _upload(admin_client, "get.txt", b"fetch me")
        resp = admin_client.get("/files/download?path=get.txt")
        assert resp.status_code == 200
        assert resp.data == b"fetch me"

    def test_download_missing_file_flashes_error(self, admin_client):
        resp = admin_client.get("/files/download?path=ghost.txt", follow_redirects=True)
        assert b"File not found" in resp.data

    def test_download_traversal_blocked(self, admin_client):
        resp = admin_client.get(
            "/files/download?path=../etc/passwd", follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Invalid path" in resp.data

    def test_read_only_user_can_download(self, user_client):
        # Write file directly — avoids shared session conflict between admin_client/user_client
        filepath = os.path.join(config.NAS_STORAGE, "shared.txt")
        with open(filepath, "wb") as f:
            f.write(b"read me")
        resp = user_client.get("/files/download?path=shared.txt")
        assert resp.status_code == 200
        assert resp.data == b"read me"


# ---------------------------------------------------------------------------
# Mkdir
# ---------------------------------------------------------------------------


class TestMkdir:
    def test_mkdir_creates_directory(self, admin_client):
        _mkdir(admin_client, "newdir")
        assert os.path.isdir(os.path.join(config.NAS_STORAGE, "newdir"))

    def test_mkdir_flash_success(self, admin_client):
        resp = _mkdir(admin_client, "flashdir")
        assert b"Created folder" in resp.data

    def test_mkdir_duplicate_name_rejected(self, admin_client):
        _mkdir(admin_client, "dupe")
        resp = _mkdir(admin_client, "dupe")
        assert b"already exists" in resp.data

    def test_mkdir_empty_name_rejected(self, admin_client):
        resp = _mkdir(admin_client, "")
        assert b"required" in resp.data

    def test_mkdir_nested(self, admin_client):
        _mkdir(admin_client, "parent")
        _mkdir(admin_client, "child", path="parent")
        assert os.path.isdir(os.path.join(config.NAS_STORAGE, "parent", "child"))


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


class TestRename:
    def test_rename_file(self, admin_client):
        _upload(admin_client, "old.txt", b"x")
        _rename(admin_client, "old.txt", "new.txt")
        assert os.path.isfile(os.path.join(config.NAS_STORAGE, "new.txt"))
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "old.txt"))

    def test_rename_folder(self, admin_client):
        _mkdir(admin_client, "before")
        _rename(admin_client, "before", "after")
        assert os.path.isdir(os.path.join(config.NAS_STORAGE, "after"))
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "before"))

    def test_rename_flash_success(self, admin_client):
        _upload(admin_client, "r.txt", b"x")
        resp = _rename(admin_client, "r.txt", "r2.txt")
        assert b"Renamed" in resp.data

    def test_rename_conflict_rejected(self, admin_client):
        _upload(admin_client, "a.txt", b"x")
        _upload(admin_client, "b.txt", b"y")
        resp = _rename(admin_client, "a.txt", "b.txt")
        assert b"already exists" in resp.data

    def test_rename_missing_item(self, admin_client):
        resp = _rename(admin_client, "ghost.txt", "whatever.txt")
        assert b"not found" in resp.data

    def test_rename_empty_name_rejected(self, admin_client):
        _upload(admin_client, "noname.txt", b"x")
        resp = _rename(admin_client, "noname.txt", "")
        assert b"required" in resp.data

    def test_rename_updates_db_filepath(self, admin_client, app):
        _upload(admin_client, "tracked.txt", b"x")
        _rename(admin_client, "tracked.txt", "renamed.txt")
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT filename FROM files WHERE filename = 'renamed.txt'"
            ).fetchone()
            old = db.execute(
                "SELECT filename FROM files WHERE filename = 'tracked.txt'"
            ).fetchone()
            db.close()
        assert row is not None
        assert old is None

    def test_rename_requires_edit_permission(self, user_client):
        resp = _rename(user_client, "anything", "other")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_file(self, admin_client):
        _upload(admin_client, "gone.txt", b"bye")
        _delete(admin_client, "gone.txt")
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "gone.txt"))

    def test_delete_folder(self, admin_client):
        _mkdir(admin_client, "rmdir")
        _delete(admin_client, "rmdir")
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "rmdir"))

    def test_delete_folder_with_contents(self, admin_client):
        _mkdir(admin_client, "tree")
        _upload(admin_client, "leaf.txt", b"x", path="tree")
        _delete(admin_client, "tree")
        assert not os.path.exists(os.path.join(config.NAS_STORAGE, "tree"))

    def test_delete_flash_success(self, admin_client):
        _upload(admin_client, "bye.txt", b"x")
        resp = _delete(admin_client, "bye.txt")
        assert b"Deleted" in resp.data

    def test_delete_missing_item(self, admin_client):
        resp = _delete(admin_client, "ghost.txt")
        assert b"not found" in resp.data

    def test_delete_removes_db_record(self, admin_client, app):
        _upload(admin_client, "nodb.txt", b"x")
        _delete(admin_client, "nodb.txt")
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT id FROM files WHERE filename = 'nodb.txt'"
            ).fetchone()
            db.close()
        assert row is None

    def test_cannot_delete_storage_root(self, admin_client):
        resp = _delete(admin_client, "")
        assert b"Cannot delete" in resp.data


# ---------------------------------------------------------------------------
# Database consistency
# ---------------------------------------------------------------------------


class TestDatabaseConsistency:
    def test_stale_record_pruned_on_browse(self, admin_client, app):
        """A file deleted outside the app is removed from the DB when /files/ is visited."""
        _upload(admin_client, "external.txt", b"x")
        os.remove(os.path.join(config.NAS_STORAGE, "external.txt"))
        admin_client.get("/files/")
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT id FROM files WHERE filename = 'external.txt'"
            ).fetchone()
            db.close()
        assert row is None

    def test_dashboard_count_correct_after_prune(self, admin_client, app):
        """Dashboard file_count is 0 after an externally deleted file is pruned."""
        _upload(admin_client, "counted.txt", b"x")
        os.remove(os.path.join(config.NAS_STORAGE, "counted.txt"))
        admin_client.get("/files/")  # triggers prune
        with app.app_context():
            from database import get_db

            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            db.close()
        assert count == 0

    def test_upload_same_file_twice_one_db_record(self, admin_client, app):
        """Re-uploading a file updates the existing record rather than inserting a duplicate."""
        _upload(admin_client, "once.txt", b"v1")
        _upload(admin_client, "once.txt", b"v2")
        with app.app_context():
            from database import get_db

            db = get_db()
            rows = db.execute(
                "SELECT id FROM files WHERE filename = 'once.txt'"
            ).fetchall()
            db.close()
        assert len(rows) == 1

    def test_upload_overwrite_updates_size_in_db(self, admin_client, app):
        """Re-uploading a file updates its recorded size in the DB."""
        _upload(admin_client, "sized.txt", b"small")
        _upload(admin_client, "sized.txt", b"much larger content here")
        with app.app_context():
            from database import get_db

            db = get_db()
            row = db.execute(
                "SELECT size FROM files WHERE filename = 'sized.txt'"
            ).fetchone()
            db.close()
        assert row["size"] == len(b"much larger content here")


# ---------------------------------------------------------------------------
# Path traversal / security
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_traversal_in_index_blocked(self, admin_client):
        resp = admin_client.get("/files/?path=../etc", follow_redirects=True)
        assert b"Invalid path" in resp.data

    def test_traversal_double_dot_blocked(self, admin_client):
        resp = admin_client.get(
            "/files/?path=..%2F..%2Fetc%2Fpasswd", follow_redirects=True
        )
        assert b"Invalid path" in resp.data

    def test_traversal_in_upload_blocked(self, admin_client):
        resp = _upload(admin_client, "x.txt", b"x", path="../outside")
        assert b"Invalid path" in resp.data

    def test_traversal_in_mkdir_blocked(self, admin_client):
        resp = _mkdir(admin_client, "x", path="../outside")
        assert b"Invalid path" in resp.data

    def test_traversal_in_delete_blocked(self, admin_client):
        resp = _delete(admin_client, "../outside/file")
        assert b"Invalid path" in resp.data

    def test_traversal_in_rename_blocked(self, admin_client):
        resp = _rename(admin_client, "../outside/file", "new")
        assert b"Invalid path" in resp.data
