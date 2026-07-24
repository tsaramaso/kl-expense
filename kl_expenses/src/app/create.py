# src/app/create.py
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import FORCE_SECURE_COOKIE, SECRET_KEY, STATIC_FOLDER, TEMPLATE_FOLDER
from src.app.context import AppContext
from src.db.session import close_session, open_session
from src.app.routes import bp


def create_app(ctx: AppContext) -> Flask:
    app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
    app.extensions["ctx"] = ctx

    # nginx is the only thing that can reach gunicorn (bound to 127.0.0.1),
    # so it's safe to trust the headers it sets on every proxied request.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1, x_host=1)  # type: ignore[method-assign]

    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = FORCE_SECURE_COOKIE

    app.before_request(open_session)
    app.teardown_appcontext(close_session)

    app.register_blueprint(bp)

    return app
