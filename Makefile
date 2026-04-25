# Ospra OS — local development tasks.
#
# Tab indentation is required by GNU make. Each target is the smallest
# correct command for the job. Why a Makefile and not a shell script:
# every target is one-line, self-documenting via ``make help``, and the
# ``.PHONY`` declaration prevents make from getting confused with a file
# of the same name.

# Defaults override-able from the environment so you can do
#   PORT=8001 make dev
# when something else is squatting :8000.
PORT      ?= 8000
HOST      ?= 127.0.0.1
PYTHON    ?= python3
UV        ?= uv

.PHONY: help
help:  ## Show this help.
	@printf "Ospra OS — make targets\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: install
install:  ## Sync deps with uv (also rebuilds .venv if needed).
	$(UV) sync

.PHONY: install-frontend
install-frontend:  ## Install frontend deps.
	cd frontend && npm install

# ---------------------------------------------------------------------------
# Dev — backend
# ---------------------------------------------------------------------------

.PHONY: kill-port
kill-port:  ## Free :$(PORT) if a stale uvicorn is squatting on it.
	@pids=$$(lsof -ti tcp:$(PORT) 2>/dev/null); \
	if [ -n "$$pids" ]; then \
	  echo "Killing stale process(es) on :$(PORT) → $$pids"; \
	  kill -9 $$pids 2>/dev/null || true; \
	  sleep 1; \
	else \
	  echo ":$(PORT) is already free"; \
	fi

.PHONY: dev
dev: kill-port  ## Start the backend with auto-reload (kills stale port first).
	@echo "Starting backend on http://$(HOST):$(PORT) (Ctrl-C to stop)"
	$(UV) run uvicorn ospra_os.main:app --reload --host $(HOST) --port $(PORT)

.PHONY: dev-local
dev-local: kill-port  ## Start backend forced into LOCAL SQLite mode (ignores .env DATABASE_URL).
	@echo "Starting backend in LOCAL SQLite mode"
	@echo "Tables auto-create at ./data/ospra_local.db — no network, no schema drift."
	@OSPRA_FORCE_LOCAL_SQLITE=1 $(UV) run uvicorn ospra_os.main:app --reload --host $(HOST) --port $(PORT)

.PHONY: dev-no-reload
dev-no-reload: kill-port  ## Like ``dev`` but without --reload (for profiling startup).
	$(UV) run uvicorn ospra_os.main:app --host $(HOST) --port $(PORT)

.PHONY: doctor
doctor:  ## Diagnose the most common local-dev failures in one shot.
	@$(UV) run python -m ospra_os.tools.doctor

# ---------------------------------------------------------------------------
# Dev — frontend
# ---------------------------------------------------------------------------

.PHONY: frontend
frontend:  ## Start the frontend dev server (vite, :5173).
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test
test:  ## Run the full test suite.
	$(UV) run pytest

.PHONY: test-fast
test-fast:  ## Run tests without coverage (faster, for tight feedback loops).
	$(UV) run pytest --no-cov -p no:cacheprovider

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

.PHONY: db-local
db-local:  ## Print instructions for switching to local SQLite.
	@echo "Local SQLite mode:"
	@echo "  1. Comment out DATABASE_URL in .env"
	@echo "  2. Restart the backend (make dev)"
	@echo "  Tables auto-create at ./data/ospra_local.db"
	@echo ""
	@echo "Remote Neon mode:"
	@echo "  1. Uncomment DATABASE_URL in .env"
	@echo "  2. Restart the backend"

.PHONY: schema-check
schema-check:  ## Compare ORM models against the live DB. Reports drift.
	$(UV) run python -m ospra_os.database.schema_drift

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

.PHONY: health
health:  ## curl the backend /health endpoint.
	@curl -sf http://$(HOST):$(PORT)/health | $(PYTHON) -m json.tool || \
	  echo "Backend not responding on :$(PORT). Try ``make dev``."
