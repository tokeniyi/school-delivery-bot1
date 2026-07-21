from __future__ import annotations

import random

from matching.distance_base import DistanceResult, DistanceProvider


class MockDistanceProvider(DistanceProvider):
    async def get_distance_and_time(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> DistanceResult:
        dist = abs(origin_lat - destination_lat) + abs(origin_lng - destination_lng)
        dist_km = round(dist * 100.0, 2)
        duration = round(dist_km * 2.5, 1)
        return DistanceResult(
            distance_km=dist_km,
            duration_min=duration,
            source="mock",
        )
