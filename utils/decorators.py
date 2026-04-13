from functools import wraps
from typing import Any, Callable, TypeVar

from flask import abort, redirect, session, url_for

from blueprints.auth import SESSION_PERMISSIONS, SESSION_ROLE, SESSION_USER_ID

F = TypeVar("F", bound=Callable[..., Any])


def login_required(f: F) -> F:
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if SESSION_USER_ID not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def admin_required(f: F) -> F:
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if SESSION_USER_ID not in session:
            return redirect(url_for("auth.login"))
        if session.get(SESSION_ROLE) != "admin":
            abort(403)
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def permission_required(permission: str) -> Callable[[F], F]:
    def decorator(f: F) -> F:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if SESSION_USER_ID not in session:
                return redirect(url_for("auth.login"))
            user_permissions = session.get(SESSION_PERMISSIONS, "").split(",")
            if permission not in user_permissions:
                abort(403)
            return f(*args, **kwargs)

        return decorated_function  # type: ignore[return-value]

    return decorator
