#!/usr/bin/env bash
set -euo pipefail

DISPLAY_ID="${DISPLAY:-${LLM_BRIDGE_VNC_DISPLAY:-:99}}"
SCREEN_SPEC="${LLM_BRIDGE_VNC_SCREEN:-1920x1080x24}"
VNC_PORT="${LLM_BRIDGE_VNC_PORT:-5900}"
NOVNC_PORT="${LLM_BRIDGE_NOVNC_PORT:-6080}"
APP_HOST="${LLM_BRIDGE_HOST:-0.0.0.0}"
APP_PORT="${LLM_BRIDGE_PORT:-9920}"
LOG_DIR="/app/data/vnc"

mkdir -p "${LOG_DIR}"
export DISPLAY="${DISPLAY_ID}"

display_number="${DISPLAY_ID#:}"
display_number="${display_number%%.*}"

if [ -e "/tmp/.X${display_number}-lock" ] && [ ! -S "/tmp/.X11-unix/X${display_number}" ]; then
  rm -f "/tmp/.X${display_number}-lock"
fi

Xvfb "${DISPLAY_ID}" -screen 0 "${SCREEN_SPEC}" -ac +extension RANDR \
  >"${LOG_DIR}/xvfb.log" 2>&1 &

for _ in $(seq 1 50); do
  if [ -S "/tmp/.X11-unix/X${display_number}" ]; then
    break
  fi
  sleep 0.1
done

if [ ! -S "/tmp/.X11-unix/X${display_number}" ]; then
  echo "Xvfb did not create ${DISPLAY_ID}" >&2
  exit 1
fi

x11vnc -display "${DISPLAY_ID}" -rfbport "${VNC_PORT}" -forever -shared -nopw \
  -xkb -noxdamage -repeat -listen 0.0.0.0 \
  >"${LOG_DIR}/x11vnc.log" 2>&1 &

websockify --web /app/novnc --log-file "${LOG_DIR}/websockify.log" \
  "0.0.0.0:${NOVNC_PORT}" "localhost:${VNC_PORT}" &

exec uvicorn app.main:app --host "${APP_HOST}" --port "${APP_PORT}"
