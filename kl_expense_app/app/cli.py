from argparse import ArgumentParser, Namespace
from sqlalchemy.orm import Session, sessionmaker

from app.manage import add_user, list_users, remove_user, restore_user


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="manage", description="Manage user login codes for the expense app."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a new user code")
    add_parser.add_argument("name", help="Display name")
    list_parser = subparsers.add_parser("list", help="List user codes")
    list_parser.add_argument(
        "--all", action="store_true", dest="show_inactive", help="Include deactivated users"
    )

    remove_parser = subparsers.add_parser("remove", help="Deactivate a user code")
    remove_parser.add_argument("uuid")

    restore_parser = subparsers.add_parser("restore", help="Reactivate a user code")
    restore_parser.add_argument("uuid")

    return parser


def dispatch(args: Namespace, session_maker: sessionmaker[Session]) -> None:
    match args.command:
        case "add":
            add_user(session_maker, args.name)
        case "list":
            list_users(session_maker, args.show_inactive)
        case "remove":
            remove_user(session_maker, args.uuid)
        case "restore":
            restore_user(session_maker, args.uuid)
