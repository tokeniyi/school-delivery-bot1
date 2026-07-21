from __future__ import annotations

import logging

from config import DISTANCE_PROVIDER, OSRM_BASE_URL

from .providers.haversine import HaversineDistanceProvider
from .providers.mock import MockDistanceProvider
from .distance_base import DistanceProvider

logger = logging.getLogger(__name__)


def get_distance_provider() -> DistanceProvider:
    provider_name = (DISTANCE_PROVIDER or "mock").lower()
    if provider_name == "mock":
        return MockDistanceProvider()
    if provider_name == "haversine":
        return HaversineDistanceProvider()
    raise ValueError(f"Unsupported DISTANCE_PROVIDER: {provider_name}")
