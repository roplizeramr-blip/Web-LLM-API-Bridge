FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    LLM_BRIDGE_HOST=127.0.0.1 \
    LLM_BRIDGE_PORT=9000 \
    LLM_BRIDGE_INTERNAL_PORT=9000 \
    LLM_BRIDGE_VNC_DISPLAY=:99 \
    LLM_BRIDGE_VNC_PORT=5900 \
    LLM_BRIDGE_NOVNC_PORT=6080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    xdotool \
    nginx \
    curl \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir websockify

COPY . .

RUN mkdir -p \
    /app/data/providers \
    /app/data/sessions \
    /app/data/browser \
    /app/data/vnc \
    && chmod +x /app/app/vnc_setup.sh \
    && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
