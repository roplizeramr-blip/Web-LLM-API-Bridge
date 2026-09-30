# Railway setup

Replace the corresponding files in the repository with these files.

## Required Railway configuration

Create a Railway Volume and mount it at:

/app/data

This is required if browser sessions, provider configuration, and browser profiles must survive restarts/redeploys.

## Public port

Do not manually hard-code the Railway public port. Railway supplies `PORT`; `start.sh` uses it automatically.

The public service is:

- `/` dashboard
- `/v1/models`
- `/v1/chat/completions`
- `/websockify` WebSocket endpoint for noVNC

## Important dashboard change

The existing `app/dashboard.html` currently builds the noVNC URL with port `6080`:

`/novnc/vnc_lite.html?host=...&port=6080&path=websockify&scale=true`

For Railway, change that line to:

`const vncUrl = \`/novnc/vnc_lite.html?host=${encodeURIComponent(window.location.hostname || "127.0.0.1")}&port=${encodeURIComponent(window.location.port || (window.location.protocol === "https:" ? "443" : "80"))}&path=websockify&scale=true\`;`

This makes the browser connect through the same public Railway origin instead of trying to reach internal port 6080.

## Security note

The original project exposes VNC with `-nopw`. In this Railway layout, x11vnc and websockify listen only on `127.0.0.1`; only the nginx proxy is public. Add application authentication before exposing the dashboard/API to untrusted users.
