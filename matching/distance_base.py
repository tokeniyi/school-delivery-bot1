from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DistanceResult:
    distance_km: float
    duration_min: float
    source: str


class DistanceProvider(ABC):
    @abstractmethod
    async def get_distance_and_time(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> DistanceResult:
        ...
