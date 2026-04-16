"""Tests for per-user storage quotas."""

import io


def _create_user(admin_client, username, quota_gb=None, permissions="read,write"):
    data = {
        "username": username,
        "password": "pass",
        "role": "user",
        "permissions": permissions,
    }
    if quota_gb is not None:
        data["storage_quota_gb"] = str(quota_gb)
    return admin_client.post("/users/create", data=data, follow_redirects=True)


def _get_user(app, username):
    with app.app_context():
        from database import get_db

        db = get_db()
        row = db.execute(
            "SELECT id, storage_quota_bytes FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        db.close()
    return row


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_users_table_has_storage_quota_bytes_column(self, app):
        with app.app_context():
            from database import get_db

            db = get_db()
            cols = {
                r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()
            }
            db.close()
        assert "storage_quota_bytes" in cols


# ---------------------------------------------------------------------------
# Create / edit with quota
# ---------------------------------------------------------------------------


class TestCreateWithQuota:
    def test_create_user_with_quota(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=1)
        row = _get_user(app, "alice")
        assert row is not None
        assert row["storage_quota_bytes"] == 1024**3

    def test_create_user_without_quota_defaults_to_zero(self, admin_client, app):
        _create_user(admin_client, "bob")
        row = _get_user(app, "bob")
        assert row is not None
        assert row["storage_quota_bytes"] == 0

    def test_create_user_with_zero_quota_means_unlimited(self, admin_client, app):
        _create_user(admin_client, "carol", quota_gb=0)
        row = _get_user(app, "carol")
        assert row["storage_quota_bytes"] == 0

    def test_create_user_with_fractional_quota(self, admin_client, app):
        _create_user(admin_client, "dave", quota_gb=0.5)
        row = _get_user(app, "dave")
        assert row["storage_quota_bytes"] == int(0.5 * 1024**3)


class TestEditWithQuota:
    def test_edit_user_quota(self, admin_client, app):
        _create_user(admin_client, "erin", quota_gb=1)
        user = _get_user(app, "erin")
        admin_client.post(
            f"/users/{user['id']}/edit",
            data={
                "role": "user",
                "permissions": "read,write",
                "storage_quota_gb": "2",
            },
            follow_redirects=True,
        )
        row = _get_user(app, "erin")
        assert row["storage_quota_bytes"] == 2 * 1024**3

    def test_edit_user_clear_quota(self, admin_client, app):
        _create_user(admin_client, "frank", quota_gb=1)
        user = _get_user(app, "frank")
        admin_client.post(
            f"/users/{user['id']}/edit",
            data={
                "role": "user",
                "permissions": "read,write",
                "storage_quota_gb": "0",
            },
            follow_redirects=True,
        )
        row = _get_user(app, "frank")
        assert row["storage_quota_bytes"] == 0


# ---------------------------------------------------------------------------
# Total quota sum validation
# ---------------------------------------------------------------------------


class TestQuotaSumValidation:
    def test_sum_quotas_cannot_exceed_global(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=3)
        resp = _create_user(admin_client, "bob", quota_gb=3)
        # Should be rejected: 3 + 3 = 6 > 5 GB global
        assert b"exceed" in resp.data.lower() or b"too large" in resp.data.lower()
        row = _get_user(app, "bob")
        assert row is None, "bob should not have been created"

    def test_sum_quotas_can_equal_global(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=2)
        _create_user(admin_client, "bob", quota_gb=3)
        assert _get_user(app, "alice") is not None
        assert _get_user(app, "bob") is not None

    def test_edit_excludes_own_existing_quota_from_sum(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=2)
        _create_user(admin_client, "bob", quota_gb=2)
        # alice edits her own to 3. Without excluding her own 2 from the sum
        # this would look like 2 + 2 + 3 = 7 > 5 and fail. Excluding her
        # existing 2: 2 (bob) + 3 (new alice) = 5, OK.
        alice = _get_user(app, "alice")
        admin_client.post(
            f"/users/{alice['id']}/edit",
            data={
                "role": "user",
                "permissions": "read,write",
                "storage_quota_gb": "3",
            },
            follow_redirects=True,
        )
        row = _get_user(app, "alice")
        assert row["storage_quota_bytes"] == 3 * 1024**3


# ---------------------------------------------------------------------------
# Quota enforcement on upload
# ---------------------------------------------------------------------------


class TestQuotaEnforcement:
    def test_upload_rejected_when_exceeds_user_quota(self, admin_client, client, app):
        # alice has a tiny 0.000001 GB quota (~1073 bytes)
        _create_user(admin_client, "alice", quota_gb=0.000001)
        client.get("/logout")
        client.post("/login", data={"username": "alice", "password": "pass"})

        resp = client.post(
            "/files/upload",
            data={
                "path": "",
                "file": (io.BytesIO(b"x" * 5000), "big.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"quota" in resp.data.lower()

    def test_upload_accepted_within_user_quota(self, admin_client, client, app):
        _create_user(admin_client, "alice", quota_gb=0.001)  # ~1 MB
        client.get("/logout")
        client.post("/login", data={"username": "alice", "password": "pass"})

        resp = client.post(
            "/files/upload",
            data={
                "path": "",
                "file": (io.BytesIO(b"x" * 100), "small.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Uploaded" in resp.data

    def test_zero_quota_still_allows_upload_within_global(
        self, admin_client, client, app
    ):
        _create_user(admin_client, "alice", quota_gb=0)
        client.get("/logout")
        client.post("/login", data={"username": "alice", "password": "pass"})

        resp = client.post(
            "/files/upload",
            data={
                "path": "",
                "file": (io.BytesIO(b"x" * 100), "small.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Uploaded" in resp.data


# ---------------------------------------------------------------------------
# Storage utility helpers
# ---------------------------------------------------------------------------


class TestStorageHelpers:
    def test_user_used_bytes_reports_user_files_only(self, admin_client, client, app):
        _create_user(admin_client, "alice", quota_gb=1)
        client.get("/logout")
        client.post("/login", data={"username": "alice", "password": "pass"})
        client.post(
            "/files/upload",
            data={"path": "", "file": (io.BytesIO(b"hello"), "a.txt")},
            content_type="multipart/form-data",
        )
        alice = _get_user(app, "alice")

        from utils.storage import user_used_bytes

        with app.app_context():
            bytes_used = user_used_bytes(alice["id"])
        assert bytes_used == 5

    def test_sum_user_quotas_bytes(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=2)
        _create_user(admin_client, "bob", quota_gb=1)

        from utils.storage import sum_user_quotas_bytes

        with app.app_context():
            total = sum_user_quotas_bytes()
        assert total == 3 * 1024**3

    def test_sum_user_quotas_bytes_excludes(self, admin_client, app):
        _create_user(admin_client, "alice", quota_gb=2)
        _create_user(admin_client, "bob", quota_gb=1)
        alice = _get_user(app, "alice")

        from utils.storage import sum_user_quotas_bytes

        with app.app_context():
            total = sum_user_quotas_bytes(exclude_user_id=alice["id"])
        assert total == 1024**3  # only bob's 1 GB
