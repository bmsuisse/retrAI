.PHONY: test lint typecheck dev serve build-frontend check

## ── Development ─────────────────────────────────────────────────────

test:  ## Run all tests
	uv run pytest tests/ -x -q --tb=short

lint:  ## Run linter
	uv run ruff check retrai tests
	uv run ruff format --check retrai tests

typecheck:  ## Run type checker
	uv run pyright

check: lint typecheck test  ## Full quality gate (lint + typecheck + test)

dev:  ## Start dev TUI
	uv run retrai tui

serve:  ## Start web dashboard
	uv run retrai serve

## ── Frontend ────────────────────────────────────────────────────────

build-frontend:  ## Build frontend for production
	cd frontend && bun install && bun run build

frontend-check:  ## Typecheck frontend
	cd frontend && bun run check
