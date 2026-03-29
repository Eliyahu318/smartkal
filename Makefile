.PHONY: install install-backend install-frontend dev dev-backend dev-frontend test test-backend lint typecheck db-up db-down

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

# Development servers
dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# Testing
test: test-backend

test-backend:
	cd backend && python -m pytest --cov=app tests/

# Linting
lint:
	cd backend && ruff check . && ruff format --check .

# Type checking
typecheck:
	cd backend && mypy app/
	cd frontend && npm run typecheck

# Database
db-up:
	docker compose up -d db

db-down:
	docker compose down
