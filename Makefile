.PHONY: dev-up dev-down db-init migrate test lint seed m1-smoke eval requirements-check pytest-check ruff-check mypy-check ci

# SSoT(12) 기반 표준 운영 명령어

# 개발 환경 시작 (hot-reload 포함)
dev-up:
	@echo "Starting development environment with hot-reloading..."
	docker-compose up --build

# 개발 환경 종료
dev-down:
	@echo "Stopping development environment..."
	docker-compose down

# (신규) 데이터베이스 테이블 생성
db-init:
	@echo "Initializing database tables..."
	docker-compose run --rm api python -m scripts.init_db

# 스키마 마이그레이션 롤아웃
migrate:
	@echo "Running schema migration..."
	docker-compose run --rm api python -m scripts.migrate_schema

# 유닛 테스트 실행
test:
	@echo "Running pytest suite..."
	./scripts/ci_tmp_env.sh docker-compose run --rm api pytest -q

# 코드 린트 및 포맷팅
lint: requirements-check
	@echo "Linting and formatting code..."
	docker-compose run --rm api ruff check .
	docker-compose run --rm api ruff format .

requirements-check:
	@echo "Ensuring requirements.txt is up to date..."
	pip-compile --annotate --output-file requirements.txt requirements.in
	git diff --exit-code requirements.txt

pytest-check:
	@echo "Running pytest -q ..."
	./scripts/ci_tmp_env.sh docker-compose run --rm api pytest -q

ruff-check:
	@echo "Running ruff check ..."
	docker-compose run --rm api ruff check .

mypy-check:
	@echo "Running mypy ..."
	docker-compose run --rm api mypy .

ci: requirements-check pytest-check ruff-check mypy-check
	@echo "CI checks completed successfully."

# 샘플 데이터 적재 (Celery 워커 필요)
seed:
	@echo "Seeding database with sample filings and news..."
	docker-compose run --rm api python -m scripts.seed_data --days-back 3
	docker-compose run --rm api python -m scripts.seed_news

# M1 파이프라인 스모크 (공시 → 분석 → RAG)
m1-smoke:
	@echo "Triggering M1 smoke pipeline (ensure celery worker is running)..."
	docker-compose run --rm api python scripts/seed_data.py --days-back 3

# (TODO) 모델 평가 실행
eval:
	@echo "Running model evaluations..."
	python -m scripts.run_eval $(EVAL_ARGS)
