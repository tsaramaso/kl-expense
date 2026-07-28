# app/filters.py
from flask import Flask


def space_sep(value: int) -> str:
    return f"{value:,}".replace(",", "\u00a0")


def register_filters(app: Flask) -> None:
    app.jinja_env.filters["space_sep"] = space_sep
