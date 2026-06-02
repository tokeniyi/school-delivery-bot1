# SchoolBridge Telegram Bot (SchoolRelay)

SchoolBridge is a Telegram bot designed to safely and efficiently connect students who need items delivered with trusted parent travelers. 

The Telegram bot itself is named **SchoolRelay** (`@SchoolRelay_Bot`).

## Project Overview

This repository contains the foundation and database implementation of the SchoolBridge Telegram Bot.

### Project Directory Structure

```text
school-delivery-bot/
│
├── bot/
│   ├── handlers/
│   │   └── start.py
│   │
│   ├── keyboards/
│   ├── states/
│   └── middlewares/
│
├── database/
│   ├── db.py
│   ├── models.py
│   └── crud.py
│
├── config.py
├── main.py
├── requirements.txt
├── .env
└── README.md
```

---

## Phase 1 Deliverables

1. **Telegram bot launches successfully** with long polling via `main.py`.
2. **SQLite database file (`school_delivery.db`) is created automatically** on startup.
3. **Users table exists** in the database with modern async SQLAlchemy ORM configurations.
4. **`/start` command responds correctly** with the welcome message:
   ```text
   Welcome to SchoolRelay 🚚

   Connecting students and trusted travelers safely.
   ```
5. **Environment variables are loaded successfully** via python-dotenv.

---

## Getting Started

### Prerequisites

* Python 3.10+
* Virtual environment tool (`venv`)

### Installation

1. Clone or download the repository into your local directory.
2. Initialize and activate the virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create and configure your `.env` file in the project root:
   ```env
   BOT_TOKEN=8805436167:AAFDbjzuDeYq6SDidm5O-Co6lHj0Tfv_i58
   ```

### Running the Bot

To start the bot, run the following command in the project root:

```bash
python main.py
```

Upon successful startup, the console will output `Bot is running...` and the database `school_delivery.db` will be automatically generated with the required `users` table.

---

## Database Architecture

### Users Table (`users`)

| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | INTEGER | Primary Key, Auto-increment | Unique internal database ID |
| `telegram_id` | BIGINT | Unique, Indexed, Not Null | Telegram User ID |
| `username` | VARCHAR | Nullable | Telegram Username |
| `full_name` | VARCHAR | Nullable | User's full name |
| `role` | VARCHAR | Default: `"Student"`, Not Null | User role: `Student`, `Parent`, or `Admin` |
