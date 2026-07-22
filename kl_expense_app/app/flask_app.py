# app/flask_app.py
from flask import Flask

from app.config import FORCE_SECURE_COOKIE, SECRET_KEY
from app.context import AppContext
from app.db_session import close_session, open_session
from app.routes import bp


def create_app(ctx: AppContext) -> Flask:
    app = Flask(__name__)
    app.extensions["ctx"] = ctx

    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = FORCE_SECURE_COOKIE

    app.before_request(open_session)
    app.teardown_appcontext(close_session)

    app.register_blueprint(bp)

    return app
