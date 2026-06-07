# Learning Hub — local dev. `make dev` is the one command that boots everything.
.DEFAULT_GOAL := dev
.PHONY: dev setup test test-frontend build typecheck clean

dev: ## Boot backend (:8000) + frontend (:5173) together
	./dev.sh

setup: ## Bootstrap venv + frontend deps without running
	./dev.sh setup

test: ## Run the backend test suite
	./dev.sh setup >/dev/null
	cd backend && ./.venv/bin/python -m pytest

test-frontend: ## Run the frontend (vitest) test suite
	cd frontend && npm test

typecheck: ## Type-check the frontend
	cd frontend && npm run typecheck

build: ## Production build of the frontend
	cd frontend && npm run build

clean: ## Remove local build/venv/node_modules + hub data (keeps sidecars untouched)
	rm -rf frontend/node_modules frontend/dist backend/.venv backend/data
