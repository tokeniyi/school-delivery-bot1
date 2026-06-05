import os
from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default=None, required: bool = False):
    value = os.getenv(name, default)

    if required and (value is None or value == ""):
        raise ValueError(f"{name} is not set")

    return value


# ===== Application =====
ENVIRONMENT = get_env("ENVIRONMENT", "development")

# ===== Redis =====
REDIS_URL = get_env(
    "REDIS_URL",
    required=(ENVIRONMENT == "production")
)

# ===== Bot =====
BOT_TOKEN = get_env(
    "BOT_TOKEN",
    required=(ENVIRONMENT == "production")
)
# ===== Database =====
DATABASE_URL = get_env(
    "DATABASE_URL",
    required=(ENVIRONMENT == "production")
)

if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip()

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1,
        )

    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )

# ===== Admin IDs =====
admin_env = get_env("ADMIN_IDS", "") or ""
ADMIN_IDS = [int(x.strip()) for x in admin_env.split(",") if x.strip().isdigit()]
if not ADMIN_IDS:
    if ENVIRONMENT == "production":
        raise ValueError("ADMIN_IDS must be set in environment variables for production deployment")
    # Allow fallback only in development
    ADMIN_IDS = os.getenv("ADMIN_IDS")

# ===== Logging =====
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")