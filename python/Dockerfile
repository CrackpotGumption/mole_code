FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so Docker can cache them.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python package into the container.
COPY app ./app

# Your status HTTP service runs on 8080.
EXPOSE 8080

# Don't buffer stdout/stderr so Arduino/game logs appear immediately.
ENV PYTHONUNBUFFERED=1
ENV GAME_STATE_PATH=/data/progress.json
ENV FAILURE_SECONDS=15
ENV VICTORY_SECONDS=45

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('STATUS_PORT', '8080') + '/health', timeout=2).read()"

STOPSIGNAL SIGTERM

CMD ["python", "-m", "app.app"]
