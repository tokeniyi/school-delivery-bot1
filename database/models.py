from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, ForeignKey, Boolean, Date, DateTime, Integer, Index, UniqueConstraint, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from database.enums import RequestStatus, TripStatus, MatchStatus, Role, GeocodeSource


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default=Role.STUDENT.value, nullable=False)

    driver_trips: Mapped[list["DriverTrip"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    delivery_requests: Mapped[list["DeliveryRequest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} username={self.username} role={self.role}>"


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_lat_lng", "lat", "lng"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    geocode_source: Mapped[str] = mapped_column(
        String, default=GeocodeSource.MANUAL.value, nullable=False
    )
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Location id={self.id} raw={self.raw_text!r} lat={self.lat} lng={self.lng}>"


class DriverTrip(Base):
    __tablename__ = "driver_trips"
    __table_args__ = (
        Index("ix_driver_trips_status", "status"),
        Index("ix_driver_trips_travel_date", "travel_date"),
        Index("ix_driver_trips_direction", "direction"),
        Index("ix_driver_trips_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    travel_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    primary_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default=TripStatus.OPEN.value, nullable=False)
    max_stops: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="driver_trips")
    primary_location: Mapped["Location"] = relationship()
    trip_matches: Mapped[list["TripMatch"]] = relationship(
        back_populates="driver_trip", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DriverTrip id={self.id} user_id={self.user_id} direction={self.direction} date={self.travel_date} status={self.status}>"


class DeliveryRequest(Base):
    __tablename__ = "delivery_requests"
    __table_args__ = (
        Index("ix_delivery_requests_status", "status"),
        Index("ix_delivery_requests_travel_date", "travel_date"),
        Index("ix_delivery_requests_direction", "direction"),
        Index("ix_delivery_requests_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_description: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    travel_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, default=RequestStatus.PENDING.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="delivery_requests")
    location: Mapped["Location"] = relationship()
    trip_matches: Mapped[list["TripMatch"]] = relationship(
        back_populates="delivery_request", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DeliveryRequest id={self.id} user_id={self.user_id} direction={self.direction} date={self.travel_date} status={self.status}>"


class TripMatch(Base):
    __tablename__ = "trip_matches"
    __table_args__ = (
        Index("ix_trip_matches_status", "status"),
        Index("ix_trip_matches_driver_trip_id", "driver_trip_id"),
        Index("ix_trip_matches_delivery_request_id", "delivery_request_id"),
        Index("ix_trip_matches_created_at", "created_at"),
        UniqueConstraint(
            "driver_trip_id",
            "delivery_request_id",
            name="uq_trip_matches_driver_trip_delivery_request",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_trip_id: Mapped[int] = mapped_column(ForeignKey("driver_trips.id"), nullable=False)
    delivery_request_id: Mapped[int] = mapped_column(ForeignKey("delivery_requests.id"), nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_from_previous_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_from_previous_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default=MatchStatus.PENDING_REVIEW.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    driver_trip: Mapped["DriverTrip"] = relationship(back_populates="trip_matches")
    delivery_request: Mapped["DeliveryRequest"] = relationship(back_populates="trip_matches")

    def __repr__(self) -> str:
        return (
            f"<TripMatch id={self.id} trip={self.driver_trip_id} req={self.delivery_request_id} "
            f"seq={self.sequence_index} status={self.status}>"
        )


class AuditLog(Base):
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
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} admin_id={self.admin_id} "
            f"action={self.action} entity_type={self.entity_type} entity_id={self.entity_id}>"
        )
