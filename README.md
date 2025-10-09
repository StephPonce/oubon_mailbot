# Oubon MailBot

FastAPI-based Gmail automation for Oubon. Handles classification, auto-replies (OpenAI), and priority alerts.

**Created:** 2025-10-08T05:23:05.495860Z

## Quick start (uv)

```bash
cd oubon_mailbot
uv sync
mkdir -p .secrets data
cp .env.example .env
# Put your Google OAuth client JSON into: .secrets/credentials.json

uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# open: http://127.0.0.1:8000/docs
```

## Google API setup

1. Create a Google Cloud project → Enable **Gmail API**.
2. Create **OAuth client (Web application)** with redirect:
   - http://localhost:8000/oauth2callback
3. Download the JSON and save as `.secrets/credentials.json`.
4. Start the app and visit `/auth/url` to get the consent URL; complete the flow to create `.secrets/gmail_token.json`.
