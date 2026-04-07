import os
from flask import Flask, render_template, session
from database import init_db, get_db
from utils.decorators import login_required
import config


def create_app():
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
    from blueprints.users import users_bp
    from blueprints.files import files_bp
    from blueprints.monitor import monitor_bp
    from blueprints.backup import backup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(backup_bp)

    @app.route('/')
    @login_required
    def dashboard():
        db = get_db()
        user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        file_count = db.execute('SELECT COUNT(*) FROM files').fetchone()[0]
        last_backup = db.execute('SELECT created_at FROM backups ORDER BY created_at DESC LIMIT 1').fetchone()
        db.close()

        return render_template('dashboard.html',
            user_count=user_count,
            file_count=file_count,
            last_backup=last_backup['created_at'] if last_backup else 'Never'
        )

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
