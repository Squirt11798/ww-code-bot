FROM python:3.12-slim

# Don't write .pyc files; flush stdout/stderr immediately for clean container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

# Persisted SQLite lives here; docker-compose mounts a named volume at /data.
RUN mkdir -p /data
VOLUME ["/data"]

# Run as a non-root user.
RUN useradd --create-home appuser && chown -R appuser /app /data
USER appuser

CMD ["python", "-m", "bot"]
