<wizard-report>
# PostHog post-wizard report

The wizard has completed a deep integration of PostHog analytics into Ospra OS. The project already had a solid PostHog foundation (`ospra_os/observability/posthog_client.py` with the `FunnelEvent` enum, `setup_posthog`, `capture`, `identify`, and `shutdown` helpers). The SDK is initialized in the FastAPI lifespan handler and flushed on shutdown. This pass extended that foundation by wiring the remaining funnel steps — login, discovery, deployment, Shopify connection, and subscription lifecycle — and set the required environment variables.

| Event name | Description | File |
|---|---|---|
| `user_signup` | Fires when a new user registers (pre-existing) | `ospra_os/api/auth_routes.py` |
| `user_logged_in` | Fires when a user successfully logs in with email/password | `ospra_os/api/auth_routes.py` |
| `first_discovery_run` | Fires when a user triggers the product discovery pipeline | `ospra_os/api/task_routes.py` |
| `first_product_deployed` | Fires when a product is successfully deployed to Shopify | `ospra_os/api/deployment_routes.py` |
| `shopify_connected` | Fires when a user completes the Shopify OAuth flow | `ospra_os/api/shopify_oauth_routes.py` |
| `subscription_started` | Fires when a LemonSqueezy subscription is activated | `ospra_os/api/webhook_routes.py` |
| `subscription_cancelled` | Fires when a subscription is cancelled or expires | `ospra_os/api/webhook_routes.py` |

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

- **Dashboard — Analytics basics (wizard):** https://us.posthog.com/project/501935/dashboard/1811498
- **Activation funnel: Signup → Discovery → Deploy:** https://us.posthog.com/project/501935/insights/eT2tib6U
- **User signups & logins over time:** https://us.posthog.com/project/501935/insights/kHdHfUc8
- **Subscription health: started vs cancelled:** https://us.posthog.com/project/501935/insights/1Pz59jKU
- **Shopify stores connected:** https://us.posthog.com/project/501935/insights/S8ke0mzj
- **Products deployed over time:** https://us.posthog.com/project/501935/insights/R1XAe3Bg

## LLM Analytics (AI Observability)

A second pass added PostHog AI Observability via OpenTelemetry auto-instrumentation. Every LLM call made through the project's AI provider abstraction (`ospra_os/ai/`) now automatically produces `$ai_generation` events in PostHog, with model name, latency, input/output tokens, and estimated cost attached.

### How it works

A new module `ospra_os/observability/llm_tracing.py` configures an OTel `TracerProvider` with `PostHogSpanProcessor` and calls the SDK-level instrumentors. Because these patch the Anthropic and OpenAI clients at the class level, **no changes are needed in individual provider files** — all callers are covered automatically.

| Provider | Instrumentor | SDKs covered |
|---|---|---|
| Anthropic (Claude) | `opentelemetry-instrumentation-anthropic` | `anthropic.Anthropic`, `AsyncAnthropic` |
| OpenAI, Groq, xAI | `opentelemetry-instrumentation-openai-v2` | `openai.OpenAI` (Groq + xAI use the same client with a different base URL) |

### Files changed

| File | Change |
|---|---|
| `pyproject.toml` | Added `posthog[otel]`, `opentelemetry-sdk`, `opentelemetry-instrumentation-anthropic`, `opentelemetry-instrumentation-openai-v2` |
| `ospra_os/observability/llm_tracing.py` | New module — `setup_llm_tracing()` + graceful no-op when packages absent |
| `ospra_os/main.py` | Calls `setup_llm_tracing()` in startup, guarded by `POSTHOG_ENABLED` + `POSTHOG_API_KEY` |

View captured generations in PostHog: https://us.posthog.com/project/501935/ai-observability/generations

## Verify before merging

- [ ] Run a full production build (the wizard only verified the files it touched) and fix any lint or type errors introduced by the generated code.
- [ ] Run the test suite — call sites that were rewritten or instrumented may need updated mocks or fixtures.
- [ ] Add `POSTHOG_API_KEY` and `POSTHOG_HOST` to `.env.example` and any environment bootstrap scripts so collaborators know what to set.
- [ ] Run `uv sync` to install the `posthog` SDK into the virtualenv (it is declared in `pyproject.toml` but the sandbox blocked the automatic install).
- [ ] Confirm the returning-visitor path also calls `identify`
- [ ] Trigger an LLM call path (e.g. product analysis or Oi assistant) and confirm `$ai_generation` events appear under **AI Observability → Generations** in PostHog. The OTel packages must be installed first (`uv sync`). — currently `posthog_identify` is called on registration and login; ensure any session-resume or token-refresh path that creates a PostHog context also re-identifies the user so backend events stay correlated.

### Agent skill

We've left an agent skill folder in your project. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.

</wizard-report>
