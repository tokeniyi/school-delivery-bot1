import enum


class Role(str, enum.Enum):
    STUDENT = "student"
    PARENT = "parent"
    DRIVER = "driver"
    ADMIN = "admin"


class Direction(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class TripStatus(str, enum.Enum):
    OPEN = "open"
    FULL = "full"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MatchStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class GeocodeSource(str, enum.Enum):
    MANUAL = "manual"
    NOMINATIM = "nominatim"
    GOOGLE = "google"
    OSRM = "osrm"
    MOCK = "mock"
