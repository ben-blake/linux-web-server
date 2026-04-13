import os

from flask import Flask, render_template
from flask.typing import ResponseReturnValue
from flask.wrappers import Response

import config
from database import get_db, init_db
from utils.decorators import login_required


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # Ensure storage directories exist
    os.makedirs(config.NAS_STORAGE, exist_ok=True)
    os.makedirs(config.NAS_BACKUPS, exist_ok=True)

    # Initialize database
    with app.app_context():
        init_db()

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.backup import backup_bp
    from blueprints.files import files_bp
    from blueprints.monitor import monitor_bp
    from blueprints.users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(backup_bp)

    @app.route("/")
    @login_required
    def dashboard() -> ResponseReturnValue:
        db = get_db()
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        file_count = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        last_backup = db.execute(
            "SELECT created_at FROM backups ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        db.close()

        return render_template(
            "dashboard.html",
            user_count=user_count,
            file_count=file_count,
            last_backup=last_backup["created_at"] if last_backup else "Never",
        )

    @app.after_request
    def add_ngrok_header(response: Response) -> Response:
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)  # nosec B201 — dev-only entrypoint
