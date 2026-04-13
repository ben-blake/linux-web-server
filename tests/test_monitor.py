"""Tests for the system monitoring blueprint."""

from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_stats():
    """Return a psutil-like namespace for mocking _collect_stats."""
    return {
        "cpu_percent": 42.5,
        "memory": {"total_gb": 8.0, "used_gb": 4.0, "percent": 50.0},
        "disk": {"total_gb": 100.0, "used_gb": 30.0, "percent": 30.0},
    }


def _patch_stats():
    """Context manager that patches _collect_stats in the monitor blueprint."""
    return patch("blueprints.monitor._collect_stats", return_value=_make_mock_stats())


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


class TestAuthGuards:
    def test_index_requires_login(self, client):
        resp = client.get("/monitor/", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "")

    def test_logs_requires_login(self, client):
        resp = client.get("/monitor/logs", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers.get("Location", "")

    def test_regular_user_can_view_monitor(self, user_client):
        with _patch_stats():
            resp = user_client.get("/monitor/")
        assert resp.status_code == 200

    def test_admin_can_view_monitor(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Dashboard / index
# ---------------------------------------------------------------------------


class TestMonitorIndex:
    def test_page_renders(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert resp.status_code == 200
        assert b"System Monitor" in resp.data

    def test_cpu_percent_displayed(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"42.5" in resp.data

    def test_memory_percent_displayed(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"50.0" in resp.data

    def test_memory_gb_displayed(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"4.0 GB" in resp.data
        assert b"8.0 GB" in resp.data

    def test_disk_percent_displayed(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"30.0" in resp.data

    def test_disk_gb_displayed(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"30.0 GB" in resp.data
        assert b"100.0 GB" in resp.data

    def test_logs_link_present(self, admin_client):
        with _patch_stats():
            resp = admin_client.get("/monitor/")
        assert b"/monitor/logs" in resp.data


# ---------------------------------------------------------------------------
# Logs page
# ---------------------------------------------------------------------------


class TestMonitorLogs:
    def test_logs_page_renders(self, admin_client):
        resp = admin_client.get("/monitor/logs")
        assert resp.status_code == 200
        assert b"System Logs" in resp.data

    def test_logs_page_shows_fallback_when_no_file(self, admin_client):
        """When no log file is accessible, a helpful message is shown."""
        fallback = (["No log file is accessible on this host.\n"], None)
        with patch("blueprints.monitor._read_logs", return_value=fallback):
            resp = admin_client.get("/monitor/logs")
        assert resp.status_code == 200
        assert b"accessible" in resp.data

    def test_logs_page_shows_file_content(self, admin_client):
        """When a log file is readable, its content appears on the page."""
        lines = ["Apr 12 10:00:00 host kernel: test log entry\n"]
        with patch(
            "blueprints.monitor._read_logs", return_value=(lines, "/fake/syslog")
        ):
            resp = admin_client.get("/monitor/logs")
        assert resp.status_code == 200
        assert b"test log entry" in resp.data

    def test_logs_page_shows_log_source(self, admin_client):
        """When log file is read, its path appears in the page description."""
        lines = ["line\n"]
        with patch(
            "blueprints.monitor._read_logs", return_value=(lines, "/fake/syslog")
        ):
            resp = admin_client.get("/monitor/logs")
        assert b"/fake/syslog" in resp.data

    def test_back_to_monitor_link_present(self, admin_client):
        resp = admin_client.get("/monitor/logs")
        assert b"/monitor/" in resp.data
