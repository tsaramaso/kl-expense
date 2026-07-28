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
from sqlalchemy import select

from src.auth import current_user, login_required
from src.db.session import get_session
from src.app.models import CategoryType, DirectionType, ExpenseType, Operation, User

bp = Blueprint("main", __name__)


def _active_users(db_session):
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.created_at)
    return db_session.scalars(stmt).all()


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
    db_session = get_session()
    return render_template(
        "insert.html",
        user_name=user.name or user.uuid[:8],
        message=request.args.get("message"),
        errors=None,
        form=None,
        directions=list(DirectionType),
        categories=list(CategoryType),
        expense_types=list(ExpenseType),
        users=_active_users(db_session),
    )


@bp.route("/insert", methods=["POST"])
@login_required
def insert_expense():
    user = current_user()
    form = request.form
    errors = []
    db_session = get_session()

    amount_raw = form.get("amount", "")
    direction_raw = form.get("direction", "")
    category_raw = form.get("category", "")
    expense_type_raw = form.get("expense_type", "")
    related_user_uuid_raw = form.get("related_user_uuid", "").strip()
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

    # expense_type is required whenever direction=EXPENSE (pick OTHER for
    # anything that doesn't fit a more specific type) and meaningless
    # otherwise, so it's ignored entirely for income rows regardless of
    # what the form sent.
    expense_type = None
    if direction == DirectionType.EXPENSE:
        try:
            expense_type = ExpenseType(expense_type_raw)
        except ValueError:
            errors.append("Choose an expense type (pick Other if unsure).")

    # related_user_uuid is optional regardless of category; if provided,
    # it must be a real, active user.
    related_user_uuid = None
    if related_user_uuid_raw:
        related_user = db_session.get(User, related_user_uuid_raw)
        if related_user is None or not related_user.is_active:
            errors.append("Choose a valid user to flag this to.")
        else:
            related_user_uuid = related_user.uuid

    # Category=USER without a chosen related user is ambiguous — who is it
    # for? Require a comment instead in that case, so there's at least a
    # human-readable trail. Client-side JS blocks this too, but this check
    # is the one that actually matters since forms can be posted directly.
    if category == CategoryType.USER and related_user_uuid is None and comment is None:
        errors.append(
            "Category is User but no one is selected — add a comment, or pick a user."
        )

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
                expense_types=list(ExpenseType),
                users=_active_users(db_session),
            ),
            400,
        )

    expense = Operation(
        user_uuid=user.uuid,
        related_user_uuid=related_user_uuid,
        amount=amount,
        direction=direction,
        category=category,
        expense_type=expense_type,
        comment=comment,
    )
    db_session.add(expense)
    db_session.commit()
    logger.info(
        f"Expense recorded: user={user.uuid} amount={amount} "
        f"direction={direction} category={category} expense_type={expense_type} "
        f"related_user={related_user_uuid}"
    )
    return redirect(url_for("main.insert_page", message="Saved."))
