FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg wget && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY app ./app

RUN mkdir -p /app/downloads /app/shared

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=7421 \
    DOWNLOAD_DIR=/app/downloads \
    MAX_FILE_SIZE_MB=50

CMD ["python", "-m", "app.main"]
