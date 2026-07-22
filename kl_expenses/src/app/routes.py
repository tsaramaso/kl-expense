# app/routes.py
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session as flask_session,
    url_for,
)

from src.auth import current_user, login_required
from src.db import get_session
from src.app.models import User

bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
def login_page():
    if current_user() is not None:
        return redirect(url_for("main.insert_page"))
    return render_template("login.html", error=None)


@bp.route("/login", methods=["POST"])
def login():
    uuid = request.form.get("uuid", "").strip()
    user = get_session().get(User, uuid)
    if user is None or not user.is_active:
        return (
            render_template("login.html", error="Unknown code. Check and try again."),
            401,
        )

    flask_session.clear()
    flask_session["uuid"] = user.uuid
    flask_session.permanent = False
    return redirect(url_for("main.insert_page"))


@bp.route("/logout", methods=["POST"])
def logout():
    flask_session.clear()
    return redirect(url_for("main.login_page"))


@bp.route("/insert", methods=["GET"])
@login_required
def insert_page():
    user = current_user()
    return render_template(
        "insert.html",
        user_name=user.name or user.uuid[:8],
        message=request.args.get("message"),
    )
