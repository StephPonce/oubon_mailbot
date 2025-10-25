# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Oubon MailBot** is a FastAPI-based Gmail automation service for Oubon e-commerce. It handles email classification, auto-replies (using OpenAI), priority alerts, and order tracking integration.

The repository contains two separate FastAPI applications:
1. **Legacy app** (`main.py`) - Original MailBot implementation
2. **OspraOS** (`ospra_os/main.py`) - Newer modular architecture with Gmail OAuth and TikTok integration

## Development Commands

### Setup and Installation
```bash
# Install dependencies using uv
uv sync

# Create required directories
mkdir -p .secrets data

# Copy environment template and configure
cp .env.example .env
```

### Running the Applications

```bash
# Run legacy MailBot (default on port 8000)
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Run OspraOS application
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

### Testing and Code Quality

```bash
# Run tests with pytest
uv run pytest

# Lint and format with ruff
uv run ruff check .
uv run ruff format .
```

## Architecture Overview

### Dual Application Structure

The codebase maintains two separate FastAPI applications that serve different purposes:

**Legacy MailBot (`main.py`)**: Monolithic application with all features in a single file. Contains the complete email processing pipeline including:
- Gmail OAuth flow (`/auth/url`, `/oauth2callback`)
- Email ingestion and sending (`/gmail/ingest`, `/gmail/send-demo`)
- Rule-based classification and auto-reply (`/gmail/process-inbox`, `/gmail/process-inbox2`)
- Template and rules management (`/templates/*`, `/rules/*`)
- AI-powered reply drafting (`/ai/reply-draft`)

**OspraOS (`ospra_os/main.py`)**: Modular router-based architecture designed for expansion. Uses optional routers that fail gracefully if unavailable:
- `ospra_os/gmail/routes.py` - Gmail OAuth integration with state management
- `ospra_os/tiktok/routes.py` - TikTok integration (placeholder/disabled)
- Shared settings in `ospra_os/core/settings.py`

### Core Components (`app/` directory)

**`app/settings.py`**: Centralized configuration using pydantic-settings. Loads from `.env` file and supports:
- Google OAuth credentials and scopes
- OpenAI API keys for AI replies
- Database URLs (SQLite/PostgreSQL)
- Slack webhooks for alerts
- Shopify API integration (token, store URL, mode)

**`app/gmail_client.py`**: Gmail API wrapper class that handles:
- OAuth flow (authorization URL generation, token exchange)
- Credential persistence (`.secrets/gmail_token.json`)
- Service client creation with automatic credential loading
- Thread fetching and simple email sending

**`app/rules.py`**: Message classification engine using keyword matching:
- Classifies into: VIP, Orders, Important, Routine
- Priority order: VIP > Orders > Important > Routine
- Returns auto-reply rules and label assignments

**`app/ai_reply.py`**: OpenAI-powered response drafting:
- Uses GPT-4o-mini with custom system prompt
- Fallback to template-based reply if API key unavailable
- Configured for Oubon's support tone (warm, professional, modern)

**`app/db.py`**: Async database session manager:
- Supports both SQLite (aiosqlite) and PostgreSQL (asyncpg)
- SQLAlchemy async engine with session factory
- Database URL configurable via settings

### Email Processing Pipeline

The main processing logic (`/gmail/process-inbox` and `/gmail/process-inbox2`) follows this flow:

1. **Fetch messages**: Query Gmail API for unread/order-related messages
2. **Parse headers**: Extract subject, from, body from Gmail API response
3. **Classify**: Match message against rules (keywords in `data/rules.json`)
4. **Label**: Create/apply Gmail labels based on classification
5. **Auto-reply** (if enabled):
   - For "Orders" label: Parse order ID, lookup via Shopify API, send status update
   - For other labels: Use template from `data/templates.json`, replace variables

### Data Files

- `data/rules.json`: Classification rules (if_any keywords, apply_label, auto_reply_template)
- `data/templates.json`: Email templates with subject/body and variable substitution ({{name}}, {{ticket_id}}, {{order_id}})
- `data/orders.json`: Local order lookup (being replaced by Shopify API integration)

### Shopify Integration

Order lookup function (`lookup_order()` in `main.py:211-231`) queries Shopify Admin API:
- Requires `SHOPIFY_API_TOKEN` and `SHOPIFY_STORE` env vars
- Returns order status, carrier, tracking number, last update
- Used to provide real-time order information in auto-replies

## Google OAuth Setup

1. Create Google Cloud project and enable Gmail API
2. Create OAuth 2.0 Web Application credentials with redirect URI: `http://localhost:8000/oauth2callback`
3. Download client JSON and save to `.secrets/credentials.json`
4. Start app and visit `/auth/url` to get consent URL
5. Complete OAuth flow to generate `.secrets/gmail_token.json`

## Key Design Patterns

**Settings injection**: Use `Depends(get_settings)` in route handlers to access configuration
**Lazy service initialization**: GmailClient loads credentials on first service access
**Template-based replies**: Jinja2-style variable substitution ({{var_name}})
**Graceful degradation**: AI replies fall back to templates if OpenAI unavailable
**Dynamic label creation**: Labels are created on-demand if they don't exist

## Development Notes

- The repo uses `uv` for dependency management (modern pip replacement)
- Two separate entry points exist; determine which to modify based on feature scope
- OspraOS routers print loading status to console on startup
- Email bodies are base64-encoded in Gmail API responses
- The `/gmail/process-inbox2` endpoint is a refactored version fixing the `from_hdr` bug
