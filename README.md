# Web LLM API Bridge — Turn free web-based LLM chat pages into an OpenAI-compatible API

Web LLM API Bridge, also called Web-LLM-Bridge, runs a real browser in the
background, opens web LLM chat pages, and exposes them through a local
OpenAI-compatible REST API.

Instead of paying for API keys, you can point OpenAI-compatible tools at this
bridge and let Playwright drive ChatGPT, Gemini, ChatJimmy, Claude, DeepSeek, or
any compatible web chat UI.

```
Local tool / app -> OpenAI API format -> Web LLM API Bridge -> Browser chat page
```

## What It Is

Web LLM API Bridge is a local FastAPI application that controls persistent
Playwright Chromium browser contexts. Each provider is just a web chat page plus
a small selector configuration that tells the bridge where to type prompts, how
to send them, and where to read responses.

The bridge exposes familiar OpenAI-compatible endpoints, including
`/v1/chat/completions`, so tools that already support the OpenAI API can use web
LLM chat pages without vendor-specific integrations.

## Why

Most LLM tools expect an API key. Many powerful LLMs also have free or
account-based web chat interfaces. This project connects those two worlds:

- Use free web LLM chat pages from API-based tools.
- Keep browser sessions logged in across restarts.
- Watch and control the browsers through an embedded VNC viewer.
- Add new providers without changing Python code.

It is useful for local experimentation, quick integrations, and API-compatible
workflows where a browser-backed provider is good enough.

## Features

- OpenAI-compatible `/v1/chat/completions` endpoint.
- Streaming and non-streaming chat completion responses.
- Multiple built-in providers: ChatGPT, Gemini, ChatJimmy, Claude, and DeepSeek.
- Add any web LLM chat page as a custom provider.
- Embedded VNC viewer to see and control browsers for login, captchas, and
  provider setup.
- No login required for providers that support anonymous or free web usage.
- Session persistence so logged-in providers stay logged in across restarts.
- Browser fingerprint settings for user agent, platform, locale, timezone, and
  HTTP headers to reduce bot-detection friction.
- Dashboard Chat tab to test enabled providers directly.
- Enable, disable, and delete providers from the dashboard.
- Runs as a single FastAPI app with a Python virtual environment only.

## Quick Start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

The app also uses Xvfb, x11vnc, and noVNC for the embedded browser viewer. On a
minimal Linux system, install the system packages first:

```bash
sudo apt-get update
sudo apt-get install -y xvfb x11vnc xdotool
```

### 3. Run the bridge

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 9920
```

### 4. Open the dashboard

Visit:

```text
http://127.0.0.1:9920/
```

From there you can open browser sessions, log in to providers when needed, test
chat completions, add custom providers, and tune browser settings.

## API Usage

The default base URL is:

```text
http://127.0.0.1:9920
```

Enabled providers are exposed as model IDs. You can list them with:

```bash
curl http://127.0.0.1:9920/v1/models
```

### Non-Streaming Chat Completion

```bash
curl http://127.0.0.1:9920/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "chatgpt",
    "messages": [
      {"role": "user", "content": "Write a one-sentence project description."}
    ]
  }'
```

Example shape:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 0,
  "model": "chatgpt",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

### Streaming Chat Completion

```bash
curl -N http://127.0.0.1:9920/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemini",
    "stream": true,
    "messages": [
      {"role": "user", "content": "Give me three concise debugging tips."}
    ]
  }'
```

Streaming responses are returned as server-sent events using the same basic
chunk format expected by OpenAI-compatible clients:

```text
data: {"id":"chatcmpl-...","object":"chat.completion.chunk",...}
data: [DONE]
```

## Dashboard

Open `http://127.0.0.1:9920/` to use the built-in dashboard.

- **Providers**: View provider status, open browser sessions, save sessions,
  enable or disable providers, delete providers, and launch the embedded VNC
  browser viewer.
- **Chat**: Send test messages to any enabled provider and watch streamed
  responses in the dashboard.
- **Add Provider**: Register a new web chat page by entering its URL and CSS
  selectors.
- **Settings**: Configure browser fingerprint values such as user agent,
  platform, timezone, locale, and extra headers.
- **Help**: View provider setup hints and selector examples.

## Adding a Custom Provider

Custom providers are stored as JSON files in `data/providers/`. The dashboard
can create them for you.

1. Open the dashboard and select **Add Provider**.
2. Enter a short provider name, display name, and web chat URL.
3. Add an input selector for the prompt field, such as `textarea` or
   `[contenteditable="true"]`.
4. Add a send button selector if the site has a reliable send button. If this is
   blank, the bridge falls back to pressing Enter.
5. Add a response selector that matches assistant messages.
6. Optionally add a response text selector when the outer response element
   contains extra UI text.
7. Save the provider, open it from **Providers**, complete any setup in VNC, and
   test it from **Chat** or `/v1/chat/completions`.

Provider names become OpenAI model IDs. For example, a provider named
`myllm` can be used with:

```json
{
  "model": "myllm",
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

Example provider file:

```json
{
  "name": "myllm",
  "display_name": "My LLM",
  "url": "https://example.com/chat",
  "mode": "dom",
  "input_selector": "textarea, [contenteditable='true']",
  "send_button_selector": "button[type='submit']",
  "response_selector": ".assistant-message",
  "response_text_selector": ".assistant-message .markdown"
}
```

## No Login Required (Free Providers)

- Login to ChatGPT, Gemini, etc. is optional. The bridge works with providers
  that allow anonymous / free usage.
- Many free public LLM web pages work without any account - just open a session
  and chat.
- If you want to use providers that require an account, such as ChatGPT or
  Claude, you can log in once via the VNC browser and the session is saved. For
  quick testing or free-tier providers, no login is needed.
- The bridge drives the browser in the background. Any web LLM chat page can be
  added as a provider via the "Add Provider" form.

## Project Structure

```text
app/
  main.py              FastAPI app, dashboard routes, provider APIs, OpenAI API
  browser_engine.py    Playwright browser lifecycle, prompt sending, streaming
  models.py            Pydantic request, provider, and runtime models
  provider_store.py    JSON-backed provider storage
  settings.py          App settings, data paths, browser fingerprint settings
  dashboard.html       Built-in dashboard UI
  vnc_setup.sh         Xvfb, x11vnc, and noVNC startup script

data/
  providers/           Provider JSON definitions
  sessions/            Saved browser storage state
  browser/             Persistent Chromium user data directories

novnc/                 Embedded noVNC assets
requirements.txt       Python dependencies
```

## Tech Stack

- **FastAPI** for the local REST API and dashboard server.
- **Playwright** for browser automation.
- **Chromium** as the controlled browser runtime.
- **Xvfb** for a virtual Linux display.
- **x11vnc** for browser remote control.
- **noVNC** for the embedded web-based VNC viewer.

## Configuration

Runtime settings can be provided through environment variables with the
`LLM_BRIDGE_` prefix or a local `.env` file.

Common settings:

```text
LLM_BRIDGE_HOST=127.0.0.1
LLM_BRIDGE_PORT=9920
LLM_BRIDGE_DEFAULT_MODEL=chatgpt
LLM_BRIDGE_RESPONSE_IDLE_SECONDS=1.5
LLM_BRIDGE_RESPONSE_TIMEOUT_SECONDS=180
```

Browser fingerprint settings can also be edited from the dashboard and are saved
to `data/browser_settings.json`.

## Notes

- Web chat pages change frequently. If a provider stops working, update its CSS
  selectors in the dashboard or the matching `data/providers/*.json` file.
- Some providers may require login, captchas, rate limits, or manual browser
  interaction.
- This bridge is intended for local use. If you expose it to a network, put it
  behind your own authentication and access controls.

## License

MIT
