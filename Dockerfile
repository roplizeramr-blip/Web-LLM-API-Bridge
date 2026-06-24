FROM ubuntu:24.04

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    LLM_BRIDGE_HOST=0.0.0.0 \
    LLM_BRIDGE_PORT=9920 \
    DISPLAY=:99

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    xvfb \
    x11vnc \
    websockify \
    xdotool \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv .venv

COPY requirements.txt ./
RUN .venv/bin/pip install -r requirements.txt \
    && .venv/bin/python -m playwright install --with-deps chromium

COPY . ./

RUN chmod +x /app/start.sh /app/app/vnc_setup.sh 2>/dev/null || true

EXPOSE 9920 6080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9920"]
