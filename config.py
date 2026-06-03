import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ===== Bot =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables or .env file.")

# ===== Database =====
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables or .env file.")

# ===== Admin IDs =====
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_env.split(",") if x.strip().isdigit()]
if not ADMIN_IDS:
    ADMIN_IDS = [7922991513, 5670012095]  # Fallback for local development

# ===== Application =====
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
