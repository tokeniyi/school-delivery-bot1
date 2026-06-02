from sqlalchemy import BigInteger, String, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

class User(Base):
    """User database model to store students, parents, and admins."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="Student", nullable=False)

    # Relationships
    student_requests: Mapped[list["StudentRequest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    parent_travels: Mapped[list["ParentTravel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} username={self.username} role={self.role}>"

class StudentRequest(Base):
    """StudentRequest database model to store student delivery requests."""
    __tablename__ = "student_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_description: Mapped[str] = mapped_column(String, nullable=False)
    pickup_location: Mapped[str] = mapped_column(String, nullable=False)
    destination_school: Mapped[str] = mapped_column(String, nullable=False)
    delivery_date: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="student_requests")

    def __repr__(self) -> str:
        return f"<StudentRequest id={self.id} user_id={self.user_id} item={self.item_description} status={self.status}>"

class ParentTravel(Base):
    """ParentTravel database model to store parent travel availability schedules."""
    __tablename__ = "parent_travels"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    destination_school: Mapped[str] = mapped_column(String, nullable=False)
    travel_date: Mapped[str] = mapped_column(String, nullable=False)
    can_carry_packages: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String, default="available", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="parent_travels")

    def __repr__(self) -> str:
        return f"<ParentTravel id={self.id} user_id={self.user_id} origin={self.origin_location} status={self.status}>"


