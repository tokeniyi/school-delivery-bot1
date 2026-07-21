from __future__ import annotations

import math

from matching.distance_base import DistanceResult, DistanceProvider


_EARTH_RADIUS_KM = 6371.0


class HaversineDistanceProvider(DistanceProvider):
    async def get_distance_and_time(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> DistanceResult:
        lat1 = math.radians(origin_lat)
        lon1 = math.radians(origin_lng)
        lat2 = math.radians(destination_lat)
        lon2 = math.radians(destination_lng)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        dist_km = round(_EARTH_RADIUS_KM * c, 2)
        duration = round(dist_km * 2.5, 1)
        return DistanceResult(
            distance_km=dist_km,
            duration_min=duration,
            source="haversine",
        )
