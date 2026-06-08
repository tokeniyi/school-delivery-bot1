# Fly.io Telegram Bot Deployment Debugging Report

## Initial Problem

After deploying the Telegram bot to Fly.io using:

```bash
fly deploy
```

the deployment appeared successful, but the bot did not respond to `/start`.

Checking the machine status showed:

```bash
fly machine list
```

Output:

```text
school-delivery-bot
STATE: stopped
```

The bot machine repeatedly crashed and restarted.

---

## Step 1: Inspect Application Logs

Ran:

```bash
fly logs
```

Observed a long SQLAlchemy/asyncpg traceback ending with:

```text
socket.gaierror: [Errno -5] No address associated with hostname
```

This indicated that the application could not resolve the database hostname before even attempting authentication.

---

## Step 2: Verify Database Machine Status

Checked database app:

```bash
fly machine list -a school-relay-db
```

Output:

```text
STATE: stopped
```

Question raised:

"Do I need to start the database machine before the bot?"

Answer:

Yes.

Since the database was deployed as a self-managed PostgreSQL machine on Fly's free tier, the database must be running before the bot can connect to it.

Unlike Managed Postgres, Fly will not automatically manage availability.

---

## Step 3: Verify Database Existence

Connected to database machine:

```bash
fly ssh console -a school-relay-db
```

Switched to postgres user:

```bash
su postgres
```

Connected to PostgreSQL:

```bash
psql -p 5433 -U postgres
```

Listed databases:

```sql
\l
```

Result:

```text
postgres
repmgr
school_delivery_bot
template0
template1
```

Confirmed:

* PostgreSQL server is running
* Database exists
* Database machine is healthy

---

## Step 4: Verify DNS Resolution

From inside database machine:

```bash
getent hosts school-relay-db.internal
```

Returned:

```text
fdaa:...
```

Meaning:

```text
school-relay-db.internal
```

is a valid Fly internal hostname.

Next:

```bash
getent hosts postgres
```

Returned nothing.

Confirmed:

```text
postgres
```

is not a valid hostname on Fly.

---

## Step 5: Compare Deployment URL with Actual Database

Current development URL:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/schoolbridge
```

Problems discovered:

### Wrong Host

Current:

```text
postgres
```

Actual:

```text
school-relay-db.internal
```

### Wrong Port

Current:

```text
5432
```

Actual:

```text
5433
```

### Wrong Database Name

Current:

```text
schoolbridge
```

Actual:

```text
school_delivery_bot
```

### Unknown Password

Current:

```text
password
```

No evidence that this password exists in production.

---

## Step 6: Confirm Root Cause

The application attempted to connect using:

```text
postgresql+asyncpg://postgres:password@postgres:5432/schoolbridge
```

The hostname:

```text
postgres
```

cannot be resolved inside Fly.

This directly explains:

```text
socket.gaierror: [Errno -5] No address associated with hostname
```

The application crashes during hostname lookup before authentication occurs.

---

## Step 7: Environment Configuration Analysis

Development environment:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/schoolbridge
```

This URL is intended for Docker Compose development where:

```yaml
services:
  postgres:
```

creates a hostname named:

```text
postgres
```

Production deployment on Fly requires different values.

---

## Production Database URL Format

Expected production URL:

```text
postgresql+asyncpg://postgres:<PASSWORD>@school-relay-db.internal:5433/school_delivery_bot
```

Where:

* Host = school-relay-db.internal
* Port = 5433
* Database = school_delivery_bot
* Password = actual postgres password

---

## Additional Observation

Fly secrets exist:

```bash
fly secrets list
```

Output included:

```text
DATABASE_URL
REDIS_URL
BOT_TOKEN
```

However, it is still necessary to verify:

1. The secret contains the correct production URL.
2. The application is not overriding Fly secrets using a local `.env`.

If `load_dotenv()` is used incorrectly inside the container, development values may override production values.

---

## Current Conclusion

Database server is operational.

Bot application crashes because it cannot resolve the hostname specified in DATABASE_URL.

Most likely causes:

1. DATABASE_URL secret still contains development values.
2. Application loads development `.env` during deployment.
3. Production DATABASE_URL has not yet been updated to use:

   * school-relay-db.internal
   * port 5433
   * database school_delivery_bot

Next action:

* Verify actual DATABASE_URL secret value.
* Update secret with correct Fly internal hostname.
* Redeploy bot.
* Confirm successful startup and Telegram `/start` response.
