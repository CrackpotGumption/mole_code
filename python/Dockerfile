FROM python:3.12-slim AS audio-build
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY fx /build/fx
COPY tools/prepare_audio.py /build/prepare_audio.py
RUN python /build/prepare_audio.py /build/fx /build/audio

FROM python:3.12-slim AS firmware-build
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN case "$TARGETARCH" in amd64) cli_arch=64bit ;; arm64) cli_arch=ARM64 ;; *) exit 1 ;; esac; \
    curl -fsSL --retry 3 "https://downloads.arduino.cc/arduino-cli/arduino-cli_1.2.2_Linux_${cli_arch}.tar.gz" \
    | tar -xz -C /usr/local/bin arduino-cli
RUN arduino-cli core update-index \
    && arduino-cli core install arduino:avr@1.8.6 \
    && arduino-cli lib install "Adafruit BusIO@1.17.4" "Adafruit NeoPixel@1.12.3" "Adafruit MCP23017 Arduino Library@2.3.2" "MFRC522@1.4.12"
COPY tools/prepare_firmware.py /build/prepare_firmware.py
COPY arduino/MOLE_FINAL_V3 /build/source
RUN python /build/prepare_firmware.py /build/source /build/firmware \
    && arduino-cli compile --fqbn arduino:avr:mega --output-dir /build/firmware \
       /build/firmware/MOLE_FINAL_V3

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends alsa-utils avrdude \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so Docker can cache them.
COPY python/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python package into the container.
COPY python/app ./app
COPY --from=audio-build /build/audio /app/app/fx
COPY tools/prepare_app.py /app/prepare_app.py
ARG APP_REVISION
RUN APP_REVISION="$APP_REVISION" PYTHONPATH=/app python /app/prepare_app.py
COPY --from=firmware-build /build/firmware/manifest.json /opt/mole-firmware/manifest.json
COPY --from=firmware-build /build/firmware/MOLE_FINAL_V3.ino.hex /opt/mole-firmware/MOLE_FINAL_V3.ino.hex

# Your status HTTP service runs on 8080.
EXPOSE 8080

# Don't buffer stdout/stderr so Arduino/game logs appear immediately.
ENV PYTHONUNBUFFERED=1
ENV GAME_LOG_PATH=/data/game-events.jsonl
ENV FAILURE_SECONDS=15

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('STATUS_PORT', '8080') + '/health', timeout=2).read()"

STOPSIGNAL SIGTERM

CMD ["python", "-m", "app.app"]
