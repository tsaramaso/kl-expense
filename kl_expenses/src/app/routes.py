# app/routes.py
import json
from datetime import datetime, timedelta, timezone

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
from src.app.recap import (
    RANGE_WINDOWS as RECAP_RANGE_WINDOWS,
    build_recap_details,
    build_recap_figure,
    direction_totals,
    get_recap_data,
)

bp = Blueprint("main", __name__)

RANGE_WINDOWS = {"week": 7, "month": 30}


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
    flask_session.permanent = True
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
def insert_operation():
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

    operation = Operation(
        user_uuid=user.uuid,
        related_user_uuid=related_user_uuid,
        amount=amount,
        direction=direction,
        category=category,
        expense_type=expense_type,
        comment=comment,
    )
    db_session.add(operation)
    db_session.commit()
    logger.info(
        f"Operation recorded: user={user.uuid} amount={amount} "
        f"direction={direction} category={category} expense_type={expense_type} "
        f"related_user={related_user_uuid}"
    )
    return redirect(url_for("main.insert_page", message="Saved."))


@bp.route("/history", methods=["GET"])
@login_required
def history_page():
    user = current_user()
    db_session = get_session()

    view_range = request.args.get("range", "week")
    if view_range not in ("week", "month", "all"):
        view_range = "week"

    stmt = select(Operation).order_by(Operation.created_at.desc())
    if view_range in RANGE_WINDOWS:
        # Stored created_at values are tz-aware UTC at write time, but
        # SQLite strips the offset on storage (naive string, no "+00:00").
        # Binding a tz-aware cutoff here would compare mismatched string
        # shapes and silently misorder — strip tzinfo so the bound cutoff
        # matches the stored shape exactly.
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=RANGE_WINDOWS[view_range]
        )
        stmt = stmt.where(Operation.created_at >= cutoff)

    operations = db_session.scalars(stmt).all()

    return render_template(
        "history.html",
        user_name=user.name or user.uuid[:8],
        operations=operations,
        view_range=view_range,
    )


@bp.route("/history/<int:operation_id>/toggle", methods=["POST"])
@login_required
def toggle_operation(operation_id):
    db_session = get_session()
    operation = db_session.get(Operation, operation_id)

    if operation is not None:
        operation.is_active = not operation.is_active
        db_session.commit()
        logger.info(
            f"Operation {'restored' if operation.is_active else 'soft-deleted'}: "
            f"id={operation_id} by user={current_user().uuid}"
        )

    view_range = request.form.get("range", "week")
    if view_range not in ("week", "month", "all"):
        view_range = "week"
    return redirect(url_for("main.history_page", range=view_range))


def _recap_view_range() -> str:
    view_range = request.args.get("range", "week")
    if view_range not in RECAP_RANGE_WINDOWS and view_range != "all":
        view_range = "week"
    return view_range


@bp.route("/recap", methods=["GET"])
@login_required
def recap_page():
    user = current_user()
    db_session = get_session()

    view_range = _recap_view_range()
    data = get_recap_data(db_session, view_range)
    fig = build_recap_figure(data)
    totals = direction_totals(data)
    details = build_recap_details(data)

    return render_template(
        "recap.html",
        user_name=user.name or user.uuid[:8],
        view_range=view_range,
        figure_json=fig.to_json(),
        income_total=totals.get("income", 0),
        expense_total=totals.get("expense", 0),
        details_json=json.dumps(details),
    )


@bp.route("/recap/data", methods=["GET"])
@login_required
def recap_data():
    db_session = get_session()

    view_range = _recap_view_range()
    data = get_recap_data(db_session, view_range)
    fig = build_recap_figure(data)
    totals = direction_totals(data)
    details = build_recap_details(data)

    payload = {
        "figure": json.loads(fig.to_json()),
        "totals": {
            "income": totals.get("income", 0),
            "expense": totals.get("expense", 0),
        },
        "details": details,
    }
    return json.dumps(payload), 200, {"Content-Type": "application/json"}
