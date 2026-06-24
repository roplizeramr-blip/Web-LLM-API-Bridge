# LLM API Bridge

LLM API Bridge, short form LLM-Bridge, is a local FastAPI bridge that opens LLM web chat providers in persistent Playwright Chromium contexts and exposes an OpenAI-compatible API on `localhost:9920`.

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
