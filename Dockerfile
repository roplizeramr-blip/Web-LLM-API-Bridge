FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV LLM_BRIDGE_HOST=0.0.0.0
ENV LLM_BRIDGE_PORT=9920

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    xdotool \
    wget \
    curl \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright
RUN playwright install chromium

# Copy application
COPY . .

# Create persistent runtime directories
RUN mkdir -p \
    /app/data/browser \
    /app/data/sessions \
    /app/data/providers

EXPOSE 9920

# Start virtual display and API server
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x800x24 -ac >/tmp/xvfb.log 2>&1 & export DISPLAY=:99 && x11vnc -display :99 -forever -shared -rfbport 5900 -nopw >/tmp/x11vnc.log 2>&1 & exec uvicorn app.main:app --host 0.0.0.0 --port 9920"]
