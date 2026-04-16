import os
from typing import Optional

import config
from database import get_db


def nas_used_bytes() -> int:
    """Return total bytes consumed by files under NAS_STORAGE."""
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(config.NAS_STORAGE):
            for name in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def quota_bytes() -> int:
    """Return the configured quota in bytes."""
    return int(config.NAS_QUOTA_GB * 1024**3)


def quota_exceeded(incoming_bytes: int) -> bool:
    """Return True if adding incoming_bytes would exceed the quota."""
    return nas_used_bytes() + incoming_bytes > quota_bytes()


def user_used_bytes(user_id: int) -> int:
    """Return the total bytes attributed to a given user in the files table."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT COALESCE(SUM(size), 0) AS used FROM files WHERE uploaded_by = ?",
            (user_id,),
        ).fetchone()
    finally:
        db.close()
    return int(row["used"] or 0)


def user_quota_bytes(user_id: int) -> int:
    """Return a user's individual storage quota in bytes (0 = no per-user limit)."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT storage_quota_bytes FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        db.close()
    if not row:
        return 0
    return int(row["storage_quota_bytes"] or 0)


def user_quota_exceeded(user_id: int, incoming_bytes: int) -> bool:
    """Return True if the upload would push the user past their individual quota.

    A quota of 0 means "no individual limit" — the global NAS quota still applies.
    """
    quota = user_quota_bytes(user_id)
    if quota <= 0:
        return False
    return user_used_bytes(user_id) + incoming_bytes > quota


def sum_user_quotas_bytes(exclude_user_id: Optional[int] = None) -> int:
    """Return the sum of all users' individual storage quotas.

    Used to validate that Σ(user quotas) ≤ global NAS quota. When editing a
    user, pass their id as exclude_user_id so their existing quota doesn't
    double-count against the new proposed value.
    """
    db = get_db()
    try:
        if exclude_user_id is None:
            row = db.execute(
                "SELECT COALESCE(SUM(storage_quota_bytes), 0) AS total FROM users"
            ).fetchone()
        else:
            row = db.execute(
                "SELECT COALESCE(SUM(storage_quota_bytes), 0) AS total"
                " FROM users WHERE id != ?",
                (exclude_user_id,),
            ).fetchone()
    finally:
        db.close()
    return int(row["total"] or 0)
