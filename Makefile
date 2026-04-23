.PHONY: help install dev dev-api test lint format typecheck migrate revision up down logs clean

BACKEND_DIR := backend
COMPOSE_FILE := infra/docker-compose.yml

help:
	@echo "사용 가능한 타겟:"
	@echo "  install            - 백엔드 의존성 설치 (pip + dev)"
	@echo "  dev                - Docker Compose 로 전체 스택 기동"
	@echo "  dev-api            - 로컬 uvicorn 기동"
	@echo "  test               - pytest + 커버리지"
	@echo "  lint               - ruff check"
	@echo "  format             - ruff format"
	@echo "  typecheck          - mypy"
	@echo "  migrate            - alembic upgrade head"
	@echo "  revision           - alembic revision (MSG 필요)"
	@echo "  up                 - docker compose up -d"
	@echo "  down               - docker compose down"
	@echo "  logs               - docker compose logs -f"
	@echo "  clean              - pyc/cache 삭제"

install:
	cd $(BACKEND_DIR) && pip install -e '.[dev]'

dev: up
	@echo "스택 기동 완료. API: http://localhost:8000"

dev-api:
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd $(BACKEND_DIR) && pytest --cov=app --cov-report=term-missing --cov-report=html

lint:
	cd $(BACKEND_DIR) && ruff check app tests

format:
	cd $(BACKEND_DIR) && ruff format app tests

typecheck:
	cd $(BACKEND_DIR) && mypy app

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
