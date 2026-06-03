from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, ForeignKey, Boolean, DateTime, Integer, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from database.enums import RequestStatus, TravelStatus, MatchStatus


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
    __table_args__ = (
        Index("ix_student_requests_status", "status"),
        Index("ix_student_requests_delivery_date", "delivery_date"),
        Index("ix_student_requests_destination_school", "destination_school"),
        Index("ix_student_requests_pickup_location", "pickup_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_description: Mapped[str] = mapped_column(String, nullable=False)
    pickup_location: Mapped[str] = mapped_column(String, nullable=False)
    destination_school: Mapped[str] = mapped_column(String, nullable=False)
    delivery_date: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default=RequestStatus.PENDING.value, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="student_requests")

    def __repr__(self) -> str:
        return f"<StudentRequest id={self.id} user_id={self.user_id} item={self.item_description} status={self.status}>"


class ParentTravel(Base):
    """ParentTravel database model to store parent travel availability schedules."""
    __tablename__ = "parent_travels"
    __table_args__ = (
        Index("ix_parent_travels_status", "status"),
        Index("ix_parent_travels_travel_date", "travel_date"),
        Index("ix_parent_travels_destination_school", "destination_school"),
        Index("ix_parent_travels_origin_location", "origin_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    origin_location: Mapped[str] = mapped_column(String, nullable=False)
    destination_school: Mapped[str] = mapped_column(String, nullable=False)
    travel_date: Mapped[str] = mapped_column(String, nullable=False)
    can_carry_packages: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default=TravelStatus.AVAILABLE.value, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="parent_travels")

    def __repr__(self) -> str:
        return f"<ParentTravel id={self.id} user_id={self.user_id} origin={self.origin_location} status={self.status}>"


class Match(Base):
    """Match database model to store potential matches between student requests and parent travels."""
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_status", "status"),
        Index("ix_matches_student_request_id", "student_request_id"),
        Index("ix_matches_parent_travel_id", "parent_travel_id"),
        Index("ix_matches_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_request_id: Mapped[int] = mapped_column(ForeignKey("student_requests.id"), nullable=False)
    parent_travel_id: Mapped[int] = mapped_column(ForeignKey("parent_travels.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String, default=MatchStatus.PENDING_REVIEW.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    student_request: Mapped["StudentRequest"] = relationship(lazy="selectin")
    parent_travel: Mapped["ParentTravel"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<Match id={self.id} request={self.student_request_id} travel={self.parent_travel_id} status={self.status}>"


class AuditLog(Base):
    """AuditLog model to track all admin actions on matches."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_admin_id", "admin_id"),
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} admin_id={self.admin_id} "
            f"action={self.action} entity_type={self.entity_type} entity_id={self.entity_id}>"
        )
