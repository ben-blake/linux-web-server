import os
import sqlite3

from werkzeug.security import generate_password_hash

import config


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    db = sqlite3.connect(config.DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db() -> None:
    """Create tables and seed the default admin user."""
    db = get_db()

    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        db.executescript(f.read())

    # Seed default admin if not exists
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password_hash, role, permissions) VALUES (?, ?, ?, ?)",
            (
                "admin",
                generate_password_hash("admin", method="pbkdf2:sha256"),
                "admin",
                "read,write,edit",
            ),
        )
        db.commit()

    db.close()
