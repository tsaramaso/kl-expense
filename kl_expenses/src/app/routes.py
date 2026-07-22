# app/routes.py
from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session as flask_session,
    url_for,
)
from loguru import logger

from src.auth import current_user, login_required
from src.db.session import get_session
from src.app.models import CategoryType, DirectionType, GroupType, Operation, User

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
        errors=None,
        form=None,
        directions=list(DirectionType),
        categories=list(CategoryType),
        groups=list(GroupType),
    )


@bp.route("/insert", methods=["POST"])
@login_required
def insert_expense():
    user = current_user()
    form = request.form
    errors = []

    amount_raw = form.get("amount", "")
    direction_raw = form.get("direction", "")
    category_raw = form.get("category", "")
    group_raw = form.get("group", "")
    comment = form.get("comment", "").strip() or None

    amount = None
    try:
        amount = int(amount_raw)
        if amount <= 0:
            errors.append("Amount must be a positive number.")
    except ValueError:
        errors.append("Amount must be a whole number.")

    direction = None
    try:
        direction = DirectionType(direction_raw)
    except ValueError:
        errors.append("Choose a valid direction.")

    category = None
    try:
        category = CategoryType(category_raw)
    except ValueError:
        errors.append("Choose a valid category.")

    group = None
    try:
        group = GroupType(group_raw)
    except ValueError:
        errors.append("Choose a valid group.")

    if errors:
        return (
            render_template(
                "insert.html",
                user_name=user.name or user.uuid[:8],
                message=None,
                errors=errors,
                form=form,
                directions=list(DirectionType),
                categories=list(CategoryType),
                groups=list(GroupType),
            ),
            400,
        )

    db_session = get_session()
    expense = Operation(
        user_uuid=user.uuid,
        amount=amount,
        direction=direction,
        category=category,
        group=group,
        comment=comment,
    )
    db_session.add(expense)
    db_session.commit()
    logger.info(
        f"Expense recorded: user={user.uuid} amount={amount} "
        f"direction={direction} category={category} group={group}"
    )
    return redirect(url_for("main.insert_page", message="Saved."))
