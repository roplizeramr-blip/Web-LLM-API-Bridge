FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LLM_BRIDGE_HOST=0.0.0.0 \
    LLM_BRIDGE_PORT=9920 \
    DISPLAY=:99

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        pip \
        python3 \
        python3-pip \
        websockify \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/chromium /usr/bin/chromium-browser

COPY requirements.txt ./
RUN pip install --break-system-packages -r requirements.txt \
    && playwright install chromium

COPY . .
RUN chmod +x /app/start.sh /app/app/vnc_setup.sh

EXPOSE 9920 6080

CMD ["/app/start.sh"]
