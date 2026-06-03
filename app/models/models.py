from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Model


class Category(Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    icon: Mapped[str] = mapped_column(default="📦")
    slug: Mapped[str] = mapped_column(unique=True, nullable=False)
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Model):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(default=True)
    image: Mapped[str | None] = mapped_column(nullable=True)
    slug: Mapped[str] = mapped_column(unique=True, nullable=False)
    category: Mapped["Category"] = relationship(back_populates="products")


class User(Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    image: Mapped[str | None] = mapped_column(nullable=True)


class EventLog(Model):
    __tablename__ = "event_logs"
    __table_args__ = (
        UniqueConstraint(
            "topic",
            "partition",
            "offset",
            name="uq_event_logs_topic_partition_offset",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str]
    partition: Mapped[int]
    offset: Mapped[int] = mapped_column(BigInteger)
    message_key: Mapped[str | None] = mapped_column(nullable=True)
    subject: Mapped[str | None] = mapped_column(nullable=True)
    action: Mapped[str | None] = mapped_column(nullable=True)
    table_name: Mapped[str | None] = mapped_column(nullable=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
