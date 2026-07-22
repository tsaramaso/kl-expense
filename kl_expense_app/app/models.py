from enum import StrEnum, auto
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DirectionType(StrEnum):
    INCOME = auto()
    EXPENSE = auto()

class GroupType(StrEnum):
    HOME = auto()
    KL = auto()
    OTHER = auto()

class CategoryType(StrEnum):
    KL_ITEM = auto()
    KL_SALARY = auto()
    KL_OTHER = auto()
    KL_EXPENSE = auto()
    GROCERIES = auto()
    RESTAURANT = auto()
    OTHER = auto()


class User(Base):
    __tablename__ = "users"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    expenses: Mapped[list["Operation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Operation(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_uuid: Mapped[str] = mapped_column(ForeignKey("users.uuid"), nullable=False)

    amount: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[DirectionType] = mapped_column(
        SAEnum(DirectionType), nullable=False
    )
    category: Mapped[CategoryType] = mapped_column(SAEnum(CategoryType), nullable=False)
    group: Mapped[GroupType] = mapped_column(SAEnum(GroupType), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="expenses")
