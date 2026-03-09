# Assured Express — Developer Makefile
# Usage: make <target>

.PHONY: help up down logs shell migrate seed test lint fmt postman-test postman-test-docker

help:
	@echo "Available commands:"
	@echo "  make up       — Start all services via Docker Compose"
	@echo "  make down     — Stop all services"
	@echo "  make logs     — Tail all container logs"
	@echo "  make shell    — Django shell in running backend container"
	@echo "  make migrate  — Run database migrations"
	@echo "  make seed     — Seed database with demo data (--clear resets)"
	@echo "  make test     — Run pytest test suite"
	@echo "  make lint     — Run flake8 linter"
	@echo "  make fmt      — Auto-format with black"
	@echo "  make urls     — Print all API URL patterns"
	@echo "  make postman-test — Run Newman collection against local API"
	@echo "  make postman-test-docker — Run Newman collection against Docker API"

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# ── Backend helpers ───────────────────────────────────────────────────────────
shell:
	docker compose exec backend python manage.py shell

migrate:
	docker compose exec backend python manage.py migrate

seed:
	docker compose exec backend python manage.py seed_data

seed-clear:
	docker compose exec backend python manage.py seed_data --clear

urls:
	docker compose exec backend python manage.py show_urls

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	cd backend && pytest tests/ -v

test-cov:
	cd backend && pytest tests/ --cov=apps --cov-report=html -v
	@echo "Coverage report: backend/htmlcov/index.html"

# ── Code quality ─────────────────────────────────────────────────────────────
lint:
	cd backend && flake8 apps/ --max-line-length=110 --exclude=migrations

fmt:
	cd backend && black apps/ tests/

# ── Frontend helpers ──────────────────────────────────────────────────────────
fe-install:
	cd frontend && npm install

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

# ── API contract tests (Postman/Newman) ─────────────────────────────────────
postman-test:
	@command -v newman >/dev/null 2>&1 || { \
		echo "Newman is required. Install with: npm install -g newman"; \
		exit 1; \
	}
	@BASE_URL="$${BASE_URL:-http://127.0.0.1:8000}"; \
	USERNAME="$${USERNAME:-admin}"; \
	PASSWORD="$${PASSWORD:-admin123}"; \
	RIDER_USERNAME="$${RIDER_USERNAME:-rider_user}"; \
	RIDER_PASSWORD="$${RIDER_PASSWORD:-strongpass99}"; \
	echo "Running Newman against $$BASE_URL"; \
	newman run postman/AssuredExpress_Full_API.postman_collection.json \
		-e postman/AssuredExpress_Local.postman_environment.json \
		--env-var "baseUrl=$$BASE_URL" \
		--env-var "username=$$USERNAME" \
		--env-var "password=$$PASSWORD" \
		--env-var "riderUsername=$$RIDER_USERNAME" \
		--env-var "riderPassword=$$RIDER_PASSWORD"

postman-test-docker:
	@$(MAKE) postman-test BASE_URL=http://localhost:18000
