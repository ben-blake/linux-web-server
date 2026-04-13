from functools import wraps
from flask import session, redirect, url_for, abort
from blueprints.auth import SESSION_USER_ID, SESSION_ROLE, SESSION_PERMISSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if SESSION_USER_ID not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if SESSION_USER_ID not in session:
            return redirect(url_for('auth.login'))
        if session.get(SESSION_ROLE) != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if SESSION_USER_ID not in session:
                return redirect(url_for('auth.login'))
            user_permissions = session.get(SESSION_PERMISSIONS, '').split(',')
            if permission not in user_permissions:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
