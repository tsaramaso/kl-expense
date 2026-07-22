# app/flask_app.py
from flask import Flask

from app.context import AppContext


def create_app(ctx: AppContext) -> Flask:
    app = Flask(__name__)
    app.extensions["ctx"] = ctx

    @app.route("/")
    def index():
        # TODO: replace with real login page — login-route step
        return "expense app placeholder — routes not built yet"

    return app