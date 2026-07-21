from __future__ import annotations

from urllib.parse import quote_plus

from database.models import DriverTrip, Location


def build_student_maps_link(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> str:
    origin = f"{origin_lat},{origin_lng}"
    destination = f"{destination_lat},{destination_lng}"
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={quote_plus(origin)}"
        f"&destination={quote_plus(destination)}"
    )


def build_driver_maps_link(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    waypoints: list[Location],
) -> str:
    origin = f"{origin_lat},{origin_lng}"
    destination = f"{destination_lat},{destination_lng}"
    waypoints_str = "|".join(
        f"{loc.lat},{loc.lng}" for loc in waypoints
    )
    parts = [
        "https://www.google.com/maps/dir/?api=1",
        f"origin={quote_plus(origin)}",
        f"destination={quote_plus(destination)}",
    ]
    if waypoints_str:
        parts.append(f"waypoints={quote_plus(waypoints_str)}")
    return "&".join(parts)
