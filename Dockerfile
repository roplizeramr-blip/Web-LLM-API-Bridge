FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    LLM_BRIDGE_HOST=127.0.0.1 \
    LLM_BRIDGE_PORT=8000 \
    LLM_BRIDGE_VNC_DISPLAY=:99 \
    LLM_BRIDGE_VNC_PORT=5900 \
    LLM_BRIDGE_NOVNC_PORT=6080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/providers /app/data/sessions /app/data/browser /app/data/vnc \
    && chmod +x /app/app/vnc_setup.sh /app/start.sh

EXPOSE 8080

CMD ["/app/start.sh"]
