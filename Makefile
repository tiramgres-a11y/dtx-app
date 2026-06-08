# ─────────────────────────────────────────────────────────────────────────────
# DTx Diabetes Prevention App — Development Launcher
# ─────────────────────────────────────────────────────────────────────────────
# Usage (from repo root):
#   make install       — install all dependencies (run once)
#   make backend       — start FastAPI server on port 8000
#   make frontend      — start Expo dev server
#   make test-backend  — run all Python test suites
#   make test-frontend — run all JavaScript test suites
#   make test          — run ALL tests (backend + frontend)
# ─────────────────────────────────────────────────────────────────────────────

PYTHON  := python
NODE    := node
NPM     := npm
ROOT    := $(CURDIR)

.PHONY: install install-backend install-frontend \
        backend frontend \
        test test-backend test-frontend

# ── Install ──────────────────────────────────────────────────────────────────

install: install-backend install-frontend
	@echo ""
	@echo "✅  All dependencies installed."
	@echo "    Run 'make backend'  in Terminal 1"
	@echo "    Run 'make frontend' in Terminal 2"

install-backend:
	@echo "→  Installing Python dependencies..."
	$(PYTHON) -m pip install -r backend/requirements.txt

install-frontend:
	@echo "→  Installing Node.js dependencies..."
	cd frontend && $(NPM) install

# ── Launch (open two terminal tabs manually — these block) ───────────────────

backend:
	@echo "🚀  Starting FastAPI backend on http://localhost:8000"
	@echo "    API docs: http://localhost:8000/docs"
	$(PYTHON) -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	@echo "🚀  Starting Expo frontend"
	@echo "    Press 'w' to open in browser | Scan QR code for Expo Go"
	cd frontend && npx expo start

# ── Tests ─────────────────────────────────────────────────────────────────────

test: test-backend test-frontend
	@echo ""
	@echo "✅  All test suites passed."

test-backend:
	@echo "▶  Backend tests..."
	PYTHONIOENCODING=utf-8 $(PYTHON) test_backend.py
	PYTHONIOENCODING=utf-8 $(PYTHON) test_sos.py
	PYTHONIOENCODING=utf-8 $(PYTHON) test_cognitive_engine.py
	PYTHONIOENCODING=utf-8 $(PYTHON) test_scheduler.py

test-frontend:
	@echo "▶  Frontend tests..."
	$(NODE) frontend/test_ui_toggle.js
	$(NODE) frontend/test_healthConnect.js
	$(NODE) frontend/test_network.js
	$(NODE) frontend/test_habit_card.js
	$(NODE) frontend/test_phase2_ui.js
