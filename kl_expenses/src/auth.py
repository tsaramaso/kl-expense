# app/auth.py
from functools import wraps
from typing import Callable

from flask import redirect, session as flask_session, url_for

from src.db import get_session
from src.app.models import User


def current_user() -> User | None:
    uuid = flask_session.get("uuid")
    if uuid is None:
        return None
    user = get_session().get(User, uuid)
    if user is None or not user.is_active:
        return None
    return user


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("main.login_page"))
        return view(*args, **kwargs)

    return wrapped
