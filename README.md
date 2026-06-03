# SchoolBridge Telegram Bot (SchoolRelay)

SchoolBridge is a Telegram bot that safely connects students who need items delivered with trusted parent travelers heading to the same school.

The Telegram bot is named **SchoolRelay** (`@SchoolRelay_Bot`).

---

## Project Structure

```text
school-delivery-bot/
│
├── bot/
│   ├── handlers/
│   │   ├── admin.py        # Admin commands: /admin_matches, /health
│   │   ├── parent.py       # Parent travel registration flow
│   │   ├── start.py        # /start command
│   │   └── student.py      # Student request flow
│   ├── keyboards/
│   ├── middlewares/
│   │   ├── error_middleware.py       # Global exception handler
│   │   └── rate_limit_middleware.py  # 5 req/min per user
│   └── states/
│
├── database/
│   ├── crud.py     # All database operations
│   ├── db.py       # SQLAlchemy async engine (PostgreSQL)
│   ├── enums.py    # RequestStatus, TravelStatus, MatchStatus
│   └── models.py   # ORM models + indexes + AuditLog
│
├── migrations/          # Alembic migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── services/
│   ├── matching.py       # SQL JOIN-based match finder
│   └── notifications.py  # Telegram notifications with retry logic
│
├── logs/                 # Rotating log files (app.log)
├── tests/
│
├── config.py
├── main.py
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env
```

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

| Variable       | Required | Description                                      | Example                                                      |
|----------------|----------|--------------------------------------------------|--------------------------------------------------------------|
| `BOT_TOKEN`    | ✅ Yes   | Telegram Bot API token from @BotFather           | `8805436167:AAFDbjz...`                                      |
| `DATABASE_URL` | ✅ Yes   | PostgreSQL async connection string               | `postgresql+asyncpg://postgres:password@localhost:5432/schoolbridge` |
| `ADMIN_IDS`    | ✅ Yes   | Comma-separated Telegram IDs of admins           | `123456789,987654321`                                        |
| `ENVIRONMENT`  | No       | `development` or `production` (default: `development`) | `production`                                          |
| `LOG_LEVEL`    | No       | Logging verbosity (default: `INFO`)              | `INFO`, `WARNING`, `ERROR`                                   |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ running locally
- Virtual environment tool (`venv`)

### 1. Clone and Set Up Environment

```bash
git clone <repo-url>
cd school-delivery-bot
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Create PostgreSQL Database

```bash
psql -U postgres -c "CREATE DATABASE schoolbridge;"
```

### 5. Run Migrations

```bash
alembic upgrade head
```

### 6. Start the Bot

```bash
python main.py
```

Logs are written to `logs/app.log` and to the console simultaneously.

---

## Docker Deployment

### Single-Command Startup

```bash
docker compose up -d
```

This starts:
- `postgres` — PostgreSQL 16 with a named volume (`pgdata`) for data persistence
- `schoolbridge-bot` — the bot container; automatically runs `alembic upgrade head` before starting

### Stopping

```bash
docker compose down
```

Data in the `pgdata` volume persists across container restarts.

### Viewing Logs

```bash
# Bot logs (live)
docker compose logs -f schoolbridge-bot

# Or read the mounted log file
cat logs/app.log
```

### Rebuilding After Code Changes

```bash
docker compose up -d --build
```

---

## Database Migration Commands

| Command                           | Description                                  |
|-----------------------------------|----------------------------------------------|
| `alembic upgrade head`            | Apply all pending migrations                 |
| `alembic downgrade -1`            | Roll back one migration                      |
| `alembic downgrade base`          | Roll back all migrations                     |
| `alembic revision --autogenerate -m "description"` | Generate a new migration from model changes |
| `alembic history`                 | Show migration history                       |
| `alembic current`                 | Show current applied revision                |

> [!IMPORTANT]
> **Never** use `Base.metadata.create_all()` in production. Always use Alembic migrations.

---

## Backup Strategy

### Daily Backup (PostgreSQL)

```bash
# Dump the database to a timestamped file
pg_dump -U postgres -d schoolbridge -F c -f backup_$(date +%Y%m%d).dump
```

For Docker:

```bash
docker exec schoolbridge-postgres pg_dump -U postgres -d schoolbridge -F c \
  > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Restore from Backup

```bash
# Local restore
pg_restore -U postgres -d schoolbridge -c backup_20260601.dump

# Docker restore
cat backup_20260601.dump | docker exec -i schoolbridge-postgres \
  pg_restore -U postgres -d schoolbridge -c
```

### Recommended Schedule

| Frequency | Method           |
|-----------|------------------|
| Daily     | Automated cron `pg_dump` to external storage or S3 |
| Weekly    | Retain last 7 daily dumps |
| Monthly   | Archive monthly snapshot off-site |

---

## Health Monitoring

Send `/health` as an admin to check system status:

```
🩺 System Health

Database:     ✅ OK
Telegram API: ✅ OK
Application:  ✅ Running
```

---

## Admin Commands

| Command           | Description                              |
|-------------------|------------------------------------------|
| `/health`         | Check DB and Telegram API connectivity   |
| `/admin_matches`  | List all pending matches for review      |

---

## Troubleshooting

### Bot won't start: `DATABASE_URL is not set`
Ensure `.env` contains a valid `DATABASE_URL` and that `python-dotenv` is installed.

### `asyncpg.InvalidCatalogNameError: database "schoolbridge" does not exist`
Create the database first:
```bash
psql -U postgres -c "CREATE DATABASE schoolbridge;"
```

### Migrations fail with connection error
Verify PostgreSQL is running and the credentials in `DATABASE_URL` are correct.

### `alembic upgrade head` produces no changes
Your models are already in sync with the current schema. No action needed.

### Docker: bot container exits immediately
Check logs: `docker compose logs schoolbridge-bot`. Usually a missing `.env` variable or unreachable Postgres.

### Rate limit false positives
The rate limiter is in-memory and resets on restart. Limit is 5 messages per 60 seconds per user. Adjust `_MAX_REQUESTS` and `_WINDOW_SECONDS` in `bot/middlewares/rate_limit_middleware.py` if needed.
