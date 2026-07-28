from enum import StrEnum, auto
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DirectionType(StrEnum):
    INCOME = auto()
    EXPENSE = auto()


class CategoryType(StrEnum):
    KL = auto()
    HOME = auto()
    USER = auto()
    OTHER = auto()


class ExpenseType(StrEnum):
    GROCERIES = auto()
    UTILITIES = auto()
    OTHER = auto()
    MATERIAL = auto()
    FOOD = auto()
    RENT = auto()
    BILL = auto()
    SALARY = auto()
    PERSONAL = auto()
    FUEL = auto()


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
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Operation.user_uuid",
    )


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_uuid: Mapped[str] = mapped_column(ForeignKey("users.uuid"), nullable=False)
    related_user_uuid: Mapped[str | None] = mapped_column(
        ForeignKey("users.uuid"), nullable=True
    )

    amount: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[DirectionType] = mapped_column(
        SAEnum(DirectionType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    category: Mapped[CategoryType] = mapped_column(
        SAEnum(CategoryType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    expense_type: Mapped[ExpenseType | None] = mapped_column(
        SAEnum(ExpenseType, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=true(), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(
        back_populates="expenses", foreign_keys=[user_uuid]
    )
    related_user: Mapped["User | None"] = relationship(foreign_keys=[related_user_uuid])
