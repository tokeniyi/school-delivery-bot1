FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for asyncpg (libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create logs directory
RUN mkdir -p logs

# Run migrations then start the bot
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
