# app/recap.py

from colorsys import hls_to_rgb, rgb_to_hls
from typing import Any
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.models import Operation

# "year" added here specifically for this page — History currently only
# offers week/month/all. Kept as a small local dict rather than importing
# routes.py's RANGE_WINDOWS, to avoid a circular import (routes.py will
# import *from* this module once the routes land in step 3).
RANGE_WINDOWS = {"week": 7, "month": 30, "year": 365}


def get_recap_data(db_session: Session, range_key: str) -> list[dict]:
    """
    Aggregate active (non-deleted) operations into totals per
    (direction, category, expense_type) for the given range.

    Household-wide by design, matching History's existing scope — no
    per-user filter.
    """
    if range_key not in RANGE_WINDOWS and range_key != "all":
        range_key = "week"

    stmt = select(
        Operation.direction,
        Operation.category,
        Operation.expense_type,
        func.sum(Operation.amount).label("total"),
    ).where(Operation.is_active.is_(True))

    if range_key in RANGE_WINDOWS:
        # Same tz-stripping gotcha as history_page — stored created_at
        # values are naive (SQLite drops the UTC offset on write), so the
        # cutoff has to be naive too or the comparison silently misorders.
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=RANGE_WINDOWS[range_key]
        )
        stmt = stmt.where(Operation.created_at >= cutoff)

    stmt = stmt.group_by(
        Operation.direction, Operation.category, Operation.expense_type
    )

    rows = db_session.execute(stmt).all()

    return [
        {
            "direction": direction.value,
            "category": category.value,
            "expense_type": expense_type.value if expense_type else None,
            "amount": int(total),
        }
        for direction, category, expense_type, total in rows
    ]


def direction_totals(data: list[dict]) -> dict[str, int]:
    """
    Sum amounts per direction straight from get_recap_data's flat rows —
    no need to touch the DB again or reach into build_recap_figure's
    tree-building internals. Missing directions (e.g. an all-income
    range with zero expenses) simply won't have a key; callers should
    default with .get(direction, 0).
    """
    totals: dict[str, int] = {}
    for row in data:
        totals[row["direction"]] = totals.get(row["direction"], 0) + row["amount"]
    return totals


DIRECTION_COLORS = {
    "expense": "#b5651d",  # matches History's expense color
    "income": "#2f6f4f",  # matches History's income color / existing accent
}

# Fixed order so a given category always gets the same hue rotation,
# regardless of which direction it appears under.
CATEGORY_ORDER = ["kl", "home", "user", "other"]
_CATEGORY_HUE_STEP = 0.07  # ~25° per category — distinct, without drifting
# into an unrelated color family


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    red, green, blue = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return rgb_to_hls(red, green, blue)


def _hls_to_hex(hue: float, lightness: float, saturation: float) -> str:
    red, green, blue = hls_to_rgb(
        hue % 1.0, min(max(lightness, 0.0), 1.0), min(max(saturation, 0.0), 1.0)
    )
    return "#{:02x}{:02x}{:02x}".format(
        round(red * 255), round(green * 255), round(blue * 255)
    )


def _category_color(direction: str, category: str) -> str:
    base_hue, base_lightness, base_saturation = _hex_to_hls(DIRECTION_COLORS[direction])
    index = CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else 0
    return _hls_to_hex(
        base_hue + index * _CATEGORY_HUE_STEP, base_lightness + 0.08, base_saturation
    )


def _expense_type_color(direction: str, category: str, index: int) -> str:
    # A lighter tint of the parent category's own color — not a new hue.
    hue, lightness, saturation = _hex_to_hls(_category_color(direction, category))
    return _hls_to_hex(hue, lightness + 0.06 + index * 0.05, saturation * 0.9)


def _build_amount_tree(data: list[dict]) -> dict[str, dict[str, dict[str | None, int]]]:
    """
    Shared by build_recap_figure and build_recap_details — both need the
    same (direction, category, expense_type) -> amount grouping, just
    shaped differently afterward. Keeping this in one place means a
    future change to how rows get grouped can't accidentally apply to
    only one of the two consumers.
    """
    tree: dict[str, dict[str, dict[str | None, int]]] = {}
    for row in data:
        d, c, et, amount = (
            row["direction"],
            row["category"],
            row["expense_type"],
            row["amount"],
        )
        tree.setdefault(d, {}).setdefault(c, {})
        tree[d][c][et] = tree[d][c].get(et, 0) + amount
    return tree


def build_recap_figure(data: list[dict]) -> go.Figure:
    """
    Shape aggregated (direction, category, expense_type, amount) rows
    into a 3-ring sunburst: Direction -> Category -> ExpenseType.

    Assumes the app-level invariant that expense_type is always set for
    direction=expense and always None for direction=income (enforced in
    routes.py's insert validation) — a single category's rows never mix
    both, so there's no "orphaned amount" case to reconcile here.
    """
    tree = _build_amount_tree(data)

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[int] = []
    colors: list[str] = []

    for direction, categories in tree.items():
        direction_total = 0

        for category, expense_types in categories.items():
            category_id = f"{direction}/{category}"
            category_total = sum(expense_types.values())
            direction_total += category_total

            # Filtered explicitly rather than relying on the invariant
            # holding at the type level — mypy can't see the business
            # rule that a category is never a mix of None and real
            # expense_type values, so we make the "real values only"
            # set concrete here instead of asserting it implicitly.
            real_expense_types: list[tuple[str, int]] = [
                (et, amount) for et, amount in expense_types.items() if et is not None
            ]

            for i, (et, amount) in enumerate(sorted(real_expense_types)):
                ids.append(f"{category_id}/{et}")
                labels.append(et.replace("_", " ").title())
                parents.append(category_id)
                values.append(amount)
                colors.append(_expense_type_color(direction, category, i))

            ids.append(category_id)
            labels.append(category.replace("_", " ").title())
            parents.append(direction)
            values.append(category_total)
            colors.append(_category_color(direction, category))

        ids.append(direction)
        labels.append(direction.title())
        parents.append("")
        values.append(direction_total)
        colors.append(DIRECTION_COLORS.get(direction, "#999999"))

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(colors=colors),
            hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
        )
    )
    fig.update_layout(margin=dict(t=10, l=10, r=10, b=10))
    return fig


def _pct(value: int, parent_total: int) -> float:
    # Guard against a zero parent total (an empty range) rather than
    # relying on callers to check first every time.
    return round(value / parent_total * 100, 1) if parent_total else 0.0


# Heterogeneous by nature (id: str, value: int, pct_of_parent: float,
# children: list) — without this, mypy infers the value type of each
# literal dict as the join of all four, which collapses to `object`
# the moment it's put in a list, breaking any arithmetic on node["value"]
# later (e.g. the unary "-" in the sort-by-value calls below).
DetailNode = dict[str, Any]


def build_recap_details(data: list[dict]) -> list[DetailNode]:
    """
    Build the grouped tree for the Details list under the chart:
    Direction -> Category -> ExpenseType, each node carrying its own
    fixed percentage of its immediate parent (never recalculated on
    zoom — the client only filters *which* nodes are visible, it
    doesn't touch these numbers) and children sorted biggest-first.

    ids match the sunburst's own ids exactly ("income", "income/kl",
    "income/kl/food", ...) so the client can reuse one id scheme for
    both zoom-tracking and list-filtering instead of a second mapping.
    """
    tree = _build_amount_tree(data)
    grand_total = sum(
        amount
        for categories in tree.values()
        for expense_types in categories.values()
        for amount in expense_types.values()
    )

    direction_nodes: list[DetailNode] = []

    for direction, categories in tree.items():
        direction_total = sum(
            sum(expense_types.values()) for expense_types in categories.values()
        )

        category_nodes: list[DetailNode] = []
        for category, expense_types in categories.items():
            category_id = f"{direction}/{category}"
            category_total = sum(expense_types.values())

            # Same explicit None-filter as build_recap_figure, for the
            # same reason: don't rely on the invariant implicitly.
            real_expense_types = [
                (et, amount) for et, amount in expense_types.items() if et is not None
            ]

            type_nodes: list[DetailNode] = [
                {
                    "id": f"{category_id}/{et}",
                    "label": et.replace("_", " ").title(),
                    "value": amount,
                    "pct_of_parent": _pct(amount, category_total),
                    "children": [],
                }
                for et, amount in real_expense_types
            ]
            type_nodes.sort(key=lambda node: -node["value"])

            category_nodes.append(
                {
                    "id": category_id,
                    "label": category.replace("_", " ").title(),
                    "value": category_total,
                    "pct_of_parent": _pct(category_total, direction_total),
                    "children": type_nodes,
                }
            )
        category_nodes.sort(key=lambda node: -node["value"])

        direction_nodes.append(
            {
                "id": direction,
                "label": direction.title(),
                "value": direction_total,
                "pct_of_parent": _pct(direction_total, grand_total),
                "children": category_nodes,
            }
        )

    direction_nodes.sort(key=lambda node: -node["value"])
    return direction_nodes
