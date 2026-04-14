"""Tests for the system monitoring blueprint."""

from unittest.mock import patch

from blueprints.monitor import _bytes_to_gb, _collect_stats, _read_logs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_stats():
    """Return a psutil-like namespace for mocking _collect_stats."""
    return {
        "cpu_percent": 42.5,
        "memory": {"total_gb": 8.0, "used_gb": 4.0, "percent": 50.0},
        "disk": {"total_gb": 100.0, "used_gb": 30.0, "used_human": "30.00 GB", "percent": 30.0},
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
        assert b"30.00 GB" in resp.data
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


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


class TestBytesToGb:
    def test_zero(self):
        assert _bytes_to_gb(0) == 0.0

    def test_one_gb(self):
        assert _bytes_to_gb(1024**3) == 1.0

    def test_fractional(self):
        assert _bytes_to_gb(int(1.5 * 1024**3)) == 1.5


class TestCollectStats:
    def test_returns_expected_keys(self):
        stats = _collect_stats()
        assert "cpu_percent" in stats
        assert "memory" in stats
        assert "disk" in stats

    def test_memory_has_expected_keys(self):
        stats = _collect_stats()
        memory = stats["memory"]
        assert isinstance(memory, dict)
        assert set(memory) == {"total_gb", "used_gb", "percent"}

    def test_disk_has_expected_keys(self):
        stats = _collect_stats()
        disk = stats["disk"]
        assert isinstance(disk, dict)
        assert set(disk) == {"total_gb", "used_gb", "used_human", "percent"}

    def test_values_are_numeric(self):
        stats = _collect_stats()
        memory = stats["memory"]
        disk = stats["disk"]
        assert isinstance(memory, dict)
        assert isinstance(disk, dict)
        assert isinstance(stats["cpu_percent"], float)
        assert isinstance(memory["total_gb"], float)
        assert isinstance(disk["percent"], float)


class TestReadLogs:
    def test_fallback_when_all_paths_inaccessible(self):
        """When every log path raises FileNotFoundError, the fallback is returned."""
        with patch("blueprints.monitor._LOG_PATHS", []):
            lines, source = _read_logs()
        assert source is None
        assert any("No log file" in line for line in lines)

    def test_returns_lines_and_path_when_readable(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("line one\nline two\n")
        with patch("blueprints.monitor._LOG_PATHS", [str(log_file)]):
            lines, source = _read_logs()
        assert source == str(log_file)
        assert any("line one" in ln for ln in lines)

    def test_skips_permission_error_and_falls_back(self):
        """PermissionError on a path is skipped; fallback fires when no more paths."""
        with patch("blueprints.monitor._LOG_PATHS", ["/no/such/path"]):
            _, source = _read_logs()
        assert source is None
