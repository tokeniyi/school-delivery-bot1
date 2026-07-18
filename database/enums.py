import enum


class RequestStatus(str, enum.Enum):
    """Status values for StudentRequest records."""
    PENDING = "pending"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TravelStatus(str, enum.Enum):
    """Status values for ParentTravel records."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MatchStatus(str, enum.Enum):
    """Status values for Match records."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Role(str, enum.Enum):
    """Canonical role values stored for users."""
    STUDENT = "student"
    PARENT = "parent"
    ADMIN = "admin"
