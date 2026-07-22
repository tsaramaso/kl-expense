from loguru import logger
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select

from src.models import User


def add_user(session_maker: sessionmaker[Session], name: str | None = None) -> None:
    with session_maker() as session:
        user = User(name=name)
        session.add(user)
        session.commit()
        logger.info(f"User created: uuid={user.uuid} name={name!r}")
        print(f"Created user{f' \"{name}\"' if name else ''} with code:")
        print(user.uuid)


def list_users(
    session_maker: sessionmaker[Session], show_inactive: bool = False
) -> None:
    with session_maker() as session:
        stmt = select(User)
        if not show_inactive:
            stmt = stmt.where(User.is_active.is_(True))
        stmt = stmt.order_by(User.created_at)
        users = session.scalars(stmt).all()
        if not users:
            print("No users yet.")
            return
        for user in users:
            status = "" if user.is_active else "  [inactive]"
            print(
                f"{user.uuid}  {user.name or ''}  (created {user.created_at}){status}"
            )


def remove_user(session_maker: sessionmaker[Session], target_uuid: str) -> None:
    with session_maker() as session:
        user = session.get(User, target_uuid)
        if user is None:
            logger.warning(f"Deactivate failed, no such user: uuid={target_uuid}")
            print(f"No user found with code {target_uuid}")
            return
        if not user.is_active:
            print(f"{target_uuid} is already inactive.")
            return
        user.is_active = False
        session.commit()
        logger.info(f"User deactivated: uuid={target_uuid} name={user.name!r}")
        print(f"Deactivated {target_uuid}")


def restore_user(session_maker: sessionmaker[Session], target_uuid: str) -> None:
    with session_maker() as session:
        user = session.get(User, target_uuid)
        if user is None:
            logger.warning(f"Restore failed, no such user: uuid={target_uuid}")
            print(f"No user found with code {target_uuid}")
            return
        if user.is_active:
            print(f"{target_uuid} is already active.")
            return
        user.is_active = True
        session.commit()
        logger.info(f"User restored: uuid={target_uuid} name={user.name!r}")
        print(f"Restored {target_uuid}")
