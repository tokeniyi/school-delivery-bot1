"""Rebuild delivery schema for Fixed Hub Model

Revision ID: 002_rebuild_delivery_schema
Revises: 5196523efe8d
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_rebuild_delivery_schema"
down_revision: Union[str, None] = "5196523efe8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("geocode_source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_locations_lat_lng", "locations", ["lat", "lng"])

    op.create_table(
        "driver_trips",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("travel_date", sa.Date(), nullable=False),
        sa.Column("primary_location_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("max_stops", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["primary_location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_driver_trips_status", "driver_trips", ["status"])
    op.create_index("ix_driver_trips_travel_date", "driver_trips", ["travel_date"])
    op.create_index("ix_driver_trips_direction", "driver_trips", ["direction"])
    op.create_index("ix_driver_trips_user_id", "driver_trips", ["user_id"])

    op.create_table(
        "delivery_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("travel_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_requests_status", "delivery_requests", ["status"])
    op.create_index("ix_delivery_requests_travel_date", "delivery_requests", ["travel_date"])
    op.create_index("ix_delivery_requests_direction", "delivery_requests", ["direction"])
    op.create_index("ix_delivery_requests_user_id", "delivery_requests", ["user_id"])

    op.create_table(
        "trip_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_trip_id", sa.Integer(), nullable=False),
        sa.Column("delivery_request_id", sa.Integer(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("distance_from_previous_km", sa.Float(), nullable=True),
        sa.Column("time_from_previous_min", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["driver_trip_id"], ["driver_trips.id"]),
        sa.ForeignKeyConstraint(["delivery_request_id"], ["delivery_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "driver_trip_id",
            "delivery_request_id",
            name="uq_trip_matches_driver_trip_delivery_request",
        ),
    )
    op.create_index("ix_trip_matches_status", "trip_matches", ["status"])
    op.create_index("ix_trip_matches_driver_trip_id", "trip_matches", ["driver_trip_id"])
    op.create_index("ix_trip_matches_delivery_request_id", "trip_matches", ["delivery_request_id"])
    op.create_index("ix_trip_matches_created_at", "trip_matches", ["created_at"])

    op.drop_table("matches")
    op.drop_table("parent_travels")
    op.drop_table("student_requests")


def downgrade() -> None:
    op.create_table(
        "student_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.String(), nullable=False),
        sa.Column("pickup_location", sa.String(), nullable=False),
        sa.Column("destination_school", sa.String(), nullable=False),
        sa.Column("delivery_date", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_requests_status", "student_requests", ["status"])
    op.create_index("ix_student_requests_delivery_date", "student_requests", ["delivery_date"])
    op.create_index("ix_student_requests_destination_school", "student_requests", ["destination_school"])
    op.create_index("ix_student_requests_pickup_location", "student_requests", ["pickup_location"])

    op.create_table(
        "parent_travels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("origin_location", sa.String(), nullable=False),
        sa.Column("destination_school", sa.String(), nullable=False),
        sa.Column("travel_date", sa.String(), nullable=False),
        sa.Column("can_carry_packages", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="available"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parent_travels_status", "parent_travels", ["status"])
    op.create_index("ix_parent_travels_travel_date", "parent_travels", ["travel_date"])
    op.create_index("ix_parent_travels_destination_school", "parent_travels", ["destination_school"])
    op.create_index("ix_parent_travels_origin_location", "parent_travels", ["origin_location"])

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_request_id", sa.Integer(), nullable=False),
        sa.Column("parent_travel_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_request_id"], ["student_requests.id"]),
        sa.ForeignKeyConstraint(["parent_travel_id"], ["parent_travels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_student_request_id", "matches", ["student_request_id"])
    op.create_index("ix_matches_parent_travel_id", "matches", ["parent_travel_id"])
    op.create_index("ix_matches_created_at", "matches", ["created_at"])

    op.drop_table("trip_matches")
    op.drop_table("delivery_requests")
    op.drop_table("driver_trips")
    op.drop_table("locations")
