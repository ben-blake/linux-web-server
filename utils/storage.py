import os

import config


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
