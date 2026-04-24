.PHONY: help install install-ui dev dev-ui dev-api test test-ui lint format typecheck typecheck-ui build-ui migrate revision up down logs clean

BACKEND_DIR := backend
FRONTEND_DIR := ops-admin
COMPOSE_FILE := infra/docker-compose.yml

help:
	@echo "사용 가능한 타겟:"
	@echo "  install            - 백엔드 의존성 설치 (pip + dev)"
	@echo "  install-ui         - Ops Admin 웹 의존성 설치 (pnpm)"
	@echo "  dev                - Docker Compose 로 전체 스택 기동"
	@echo "  dev-ui             - Ops Admin 웹 Next.js 개발 서버 기동 (127.0.0.1:5174)"
	@echo "  dev-api            - 로컬 uvicorn 기동"
	@echo "  test               - pytest + 커버리지"
	@echo "  test-ui            - UI unit tests (vitest)"
	@echo "  lint               - ruff check"
	@echo "  format             - ruff format"
	@echo "  typecheck          - mypy"
	@echo "  typecheck-ui       - UI TypeScript typecheck"
	@echo "  build-ui           - UI production build"
	@echo "  migrate            - alembic upgrade head"
	@echo "  revision           - alembic revision (MSG 필요)"
	@echo "  up                 - docker compose up -d"
	@echo "  down               - docker compose down"
	@echo "  logs               - docker compose logs -f"
	@echo "  clean              - pyc/cache 삭제"

install:
	cd $(BACKEND_DIR) && pip install -e '.[dev]'

install-ui:
	cd $(FRONTEND_DIR) && pnpm install

dev: up
	@echo "스택 기동 완료. API: http://localhost:8000"

dev-ui:
	cd $(FRONTEND_DIR) && pnpm dev

dev-api:
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd $(BACKEND_DIR) && pytest --cov=app --cov-report=term-missing --cov-report=html

test-ui:
	cd $(FRONTEND_DIR) && pnpm test

lint:
	cd $(BACKEND_DIR) && ruff check app tests

format:
	cd $(BACKEND_DIR) && ruff format app tests

typecheck:
	cd $(BACKEND_DIR) && mypy app

typecheck-ui:
	cd $(FRONTEND_DIR) && pnpm typecheck

build-ui:
	cd $(FRONTEND_DIR) && pnpm build

migrate:
	cd $(BACKEND_DIR) && alembic upgrade head

revision:
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)"

up:
	docker compose -f $(COMPOSE_FILE) up -d

down:
	docker compose -f $(COMPOSE_FILE) down

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/.coverage
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/coverage
