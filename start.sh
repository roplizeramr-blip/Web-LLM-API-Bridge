#!/usr/bin/env bash
set -euo pipefail

cd /app

export DISPLAY="${DISPLAY:-:99}"
export LLM_BRIDGE_HOST="127.0.0.1"
export LLM_BRIDGE_PORT="${LLM_BRIDGE_INTERNAL_PORT:-8000}"
export LLM_BRIDGE_VNC_DISPLAY="${LLM_BRIDGE_VNC_DISPLAY:-:99}"
export LLM_BRIDGE_VNC_PORT="${LLM_BRIDGE_VNC_PORT:-5900}"
export LLM_BRIDGE_NOVNC_PORT="${LLM_BRIDGE_NOVNC_PORT:-6080}"

# Generate an nginx reverse proxy at runtime because Railway supplies
# the public PORT dynamically.
PUBLIC_PORT="${PORT:-8080}"

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
            proxy_pass http://127.0.0.1:${LLM_BRIDGE_INTERNAL_PORT:-8000};
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

# Start FastAPI. Its lifespan starts Xvfb/x11vnc/websockify.
uvicorn app.main:app \
  --host "${LLM_BRIDGE_HOST}" \
  --port "${LLM_BRIDGE_INTERNAL_PORT:-8000}" \
  > /app/data/uvicorn.log 2>&1 &
APP_PID=$!

# Wait for FastAPI to start so its lifespan can initialize the browser/VNC.
for _ in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:${LLM_BRIDGE_INTERNAL_PORT:-8000}/" >/dev/null 2>&1; then
        break
    fi
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        cat /app/data/uvicorn.log >&2 || true
        exit 1
    fi
    sleep 1
done

nginx -c /tmp/nginx.conf -g 'daemon off;' &
NGINX_PID=$!

term_handler() {
    kill "$NGINX_PID" "$APP_PID" 2>/dev/null || true
    wait "$NGINX_PID" "$APP_PID" 2>/dev/null || true
}
trap term_handler SIGTERM SIGINT

wait "$APP_PID"
STATUS=$?
kill "$NGINX_PID" 2>/dev/null || true
exit "$STATUS"
