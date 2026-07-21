from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from matching.distance_base import DistanceResult, DistanceProvider

logger = logging.getLogger(__name__)


@dataclass
class CandidateRequest:
    delivery_request_id: int
    location_id: int
    lat: float
    lng: float
    item_description: str
    distance_result: DistanceResult


@dataclass
class MatchedStop:
    delivery_request_id: int
    location_id: int
    lat: float
    lng: float
    item_description: str
    sequence_index: int
    distance_from_previous_km: float | None
    time_from_previous_min: float | None


class MatchingEngine:
    def __init__(self, provider: DistanceProvider | None = None):
        self.provider = provider or _default_provider()

    async def build_chain(
        self,
        primary_lat: float,
        primary_lng: float,
        candidates: Sequence[CandidateRequest],
        max_stops: int = 4,
    ) -> list[MatchedStop]:
        if not candidates:
            return []

        remaining = list(candidates)
        chain: list[MatchedStop] = []
        last_lat = primary_lat
        last_lng = primary_lng

        while remaining and len(chain) < max_stops:
            best_idx = -1
            best_distance = float("inf")
            best_result: DistanceResult | None = None

            for idx, candidate in enumerate(remaining):
                result = await self.provider.get_distance_and_time(
                    last_lat,
                    last_lng,
                    candidate.lat,
                    candidate.lng,
                )
                if result.distance_km < best_distance:
                    best_distance = result.distance_km
                    best_result = result
                    best_idx = idx

            if best_idx < 0 or best_result is None:
                break

            if best_result.distance_km > 8.0:
                break

            candidate = remaining.pop(best_idx)
            chain.append(
                MatchedStop(
                    delivery_request_id=candidate.delivery_request_id,
                    location_id=candidate.location_id,
                    lat=candidate.lat,
                    lng=candidate.lng,
                    item_description=candidate.item_description,
                    sequence_index=len(chain),
                    distance_from_previous_km=best_result.distance_km,
                    time_from_previous_min=best_result.duration_min,
                )
            )
            last_lat = candidate.lat
            last_lng = candidate.lng

        return chain


_default_provider: DistanceProvider | None = None


def _get_default_provider() -> DistanceProvider:
    global _default_provider
    if _default_provider is None:
        from matching.distance import get_distance_provider
        _default_provider = get_distance_provider()
    return _default_provider


def set_default_provider(provider: DistanceProvider) -> None:
    global _default_provider
    _default_provider = provider
