#!/usr/bin/env bash
set -euo pipefail

cd /app

export DISPLAY="${DISPLAY:-:99}"

export LLM_BRIDGE_HOST="127.0.0.1"
export LLM_BRIDGE_INTERNAL_PORT="${LLM_BRIDGE_INTERNAL_PORT:-9000}"
export LLM_BRIDGE_PORT="${LLM_BRIDGE_INTERNAL_PORT}"

export LLM_BRIDGE_VNC_DISPLAY="${LLM_BRIDGE_VNC_DISPLAY:-:99}"
export LLM_BRIDGE_VNC_PORT="${LLM_BRIDGE_VNC_PORT:-5900}"
export LLM_BRIDGE_NOVNC_PORT="${LLM_BRIDGE_NOVNC_PORT:-6080}"

PUBLIC_PORT="${PORT:-8000}"

cat > /tmp/nginx.conf <<EOF
worker_processes 1;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;

    map \$http_upgrade \$connection_upgrade {
        default upgrade;
        '' close;
    }

    server {
        listen ${PUBLIC_PORT};
        server_name _;

        client_max_body_size 25m;

        location /websockify {
            proxy_pass http://127.0.0.1:${LLM_BRIDGE_NOVNC_PORT};
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_set_header Host \$host;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }

        location / {
            proxy_pass http://127.0.0.1:${LLM_BRIDGE_INTERNAL_PORT};
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }
    }
}
EOF

echo "Starting FastAPI on internal port ${LLM_BRIDGE_INTERNAL_PORT}..."

uvicorn app.main:app \
    --host "${LLM_BRIDGE_HOST}" \
    --port "${LLM_BRIDGE_INTERNAL_PORT}" \
    > /app/data/uvicorn.log 2>&1 &

APP_PID=$!

echo "Waiting for FastAPI startup..."

READY=0

for _ in $(seq 1 180); do
    if curl -fsS \
        "http://127.0.0.1:${LLM_BRIDGE_INTERNAL_PORT}/" \
        >/dev/null 2>&1; then

        READY=1
        break
    fi

    if ! kill -0 "$APP_PID" 2>/dev/null; then
        echo "FastAPI crashed during startup."
        echo "========== uvicorn.log =========="
        cat /app/data/uvicorn.log || true
        echo "================================="
        exit 1
    fi

    sleep 1
done

if [ "$READY" -ne 1 ]; then
    echo "FastAPI did not become ready."
    echo "========== uvicorn.log =========="
    cat /app/data/uvicorn.log || true
    echo "================================="
    exit 1
fi

echo "FastAPI is ready."

echo "Starting nginx on public port ${PUBLIC_PORT}..."

nginx -t -c /tmp/nginx.conf

nginx -c /tmp/nginx.conf -g 'daemon off;' &
NGINX_PID=$!

sleep 2

if ! kill -0 "$NGINX_PID" 2>/dev/null; then
    echo "NGINX FAILED TO START"
    exit 1
fi

echo "NGINX IS RUNNING PID=${NGINX_PID}"
echo "Public port: ${PUBLIC_PORT}"
echo "FastAPI: ${LLM_BRIDGE_INTERNAL_PORT}"
echo "Websockify: ${LLM_BRIDGE_NOVNC_PORT}"
echo "x11vnc: ${LLM_BRIDGE_VNC_PORT}"

term_handler() {
    echo "Stopping services..."

    kill "$NGINX_PID" 2>/dev/null || true
    kill "$APP_PID" 2>/dev/null || true

    wait "$NGINX_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
}

trap term_handler SIGTERM SIGINT

wait "$APP_PID"
STATUS=$?

kill "$NGINX_PID" 2>/dev/null || true

exit "$STATUS"
