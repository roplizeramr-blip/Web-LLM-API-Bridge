# Web LLM API Bridge

Web LLM API Bridge, short form Web-LLM-Bridge, is a local FastAPI bridge that opens web LLM chat providers in persistent Playwright Chromium contexts and exposes an OpenAI-compatible API on `localhost:9920`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 9920
```

Open `http://127.0.0.1:9920/`, click login for a provider, complete login in the headed Chromium window, then call:

```bash
curl http://127.0.0.1:9920/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"chatgpt","messages":[{"role":"user","content":"Hello"}]}'
```

Provider definitions live in `data/providers/*.json`. Login/browser state is kept under `data/sessions/` and `data/browser/`.

## No Login Required (Free Providers)

- Login to ChatGPT, Gemini, etc. is optional. The bridge works with providers that allow anonymous / free usage.
- Many free public LLM web pages work without any account - just open a session and chat.
- If you want to use providers that require an account, such as ChatGPT or Claude, you can log in once via the VNC browser and the session is saved. For quick testing or free-tier providers, no login is needed.
- The bridge drives the browser in the background. Any web LLM chat page can be added as a provider via the "Add Provider" form.
