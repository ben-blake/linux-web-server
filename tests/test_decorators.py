from flask import Flask, session, Blueprint


def make_app():
    """Create a minimal Flask app for testing decorators."""
    app = Flask(__name__)
    app.secret_key = 'test-secret'

    # Register a minimal auth blueprint so url_for('auth.login') resolves
    auth_bp = Blueprint('auth', __name__)

    @auth_bp.route('/login')
    def login():
        return 'Login page'

    app.register_blueprint(auth_bp)

    from utils.decorators import login_required, admin_required, permission_required

    @app.route('/protected')
    @login_required
    def protected():
        return 'OK'

    @app.route('/admin-only')
    @admin_required
    def admin_only():
        return 'OK'

    @app.route('/needs-write')
    @permission_required('write')
    def needs_write():
        return 'OK'

    return app


def test_login_required_redirects_when_not_logged_in():
    app = make_app()
    with app.test_client() as client:
        resp = client.get('/protected')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']


def test_login_required_allows_logged_in_user():
    app = make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'user'
            sess['permissions'] = 'read'
        resp = client.get('/protected')
        assert resp.status_code == 200


def test_admin_required_blocks_regular_user():
    app = make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'user'
            sess['permissions'] = 'read'
        resp = client.get('/admin-only')
        assert resp.status_code == 403


def test_admin_required_allows_admin():
    app = make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['permissions'] = 'read,write,edit,admin'
        resp = client.get('/admin-only')
        assert resp.status_code == 200


def test_permission_required_blocks_without_permission():
    app = make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'user'
            sess['permissions'] = 'read'
        resp = client.get('/needs-write')
        assert resp.status_code == 403


def test_permission_required_allows_with_permission():
    app = make_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'user'
            sess['permissions'] = 'read,write'
        resp = client.get('/needs-write')
        assert resp.status_code == 200
