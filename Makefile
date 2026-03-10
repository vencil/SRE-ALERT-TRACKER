.PHONY: dev dev-down dev-local dev-fe test test-backend test-e2e lint build version-check bump help

## Lab 環境 — Docker (完整環境含 Prometheus + Alertmanager)
dev:  ## 啟動 docker compose (Lab 模式，首次或 Dockerfile 變更才需要)
	docker compose up -d --build

dev-up:  ## 啟動 docker compose（不重新 build，日常啟動用）
	docker compose up -d

dev-down:  ## 停止 docker compose
	docker compose down

dev-logs:  ## 查看 app 日誌
	docker compose logs -f app

## Lab 環境 — Local (快速迭代，不需 Docker)
dev-local:  ## 本機直跑後端（auto-reload），適合純 API 開發
	cd backend && AT_AUTH_MODE=none \
		AT_DATABASE_URL="" \
		AT_DATA_DIR=../data \
		AT_CONFIG_DIR=../config \
		AT_POLLER_INTERVAL_HOURS=1 \
		AT_POLLER_LOOKBACK_HOURS=2 \
		python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-fe:  ## 本機前端 dev server（Vite HMR，proxy 到 :8000 後端）
	cd frontend && npm run dev

## 測試
test:  ## 執行單元測試（不含 E2E）
	cd backend && TESTING=1 python -m pytest ../tests/ --ignore=../tests/e2e/ -v --tb=short

test-quick:  ## 快速單元測試（首個失敗即停）
	cd backend && TESTING=1 python -m pytest ../tests/ --ignore=../tests/e2e/ -x -q

test-backend:  ## 僅後端測試（同 test）
	cd backend && TESTING=1 python -m pytest ../tests/ --ignore=../tests/e2e/ -v --tb=short

test-e2e:  ## 執行 E2E 瀏覽器測試（需先 make dev）
	python -m pytest tests/e2e/ -v --tb=short

## 程式碼品質
lint:  ## Ruff linter
	cd backend && python -m ruff check .

format:  ## Ruff formatter
	cd backend && python -m ruff format .

## Docker
build:  ## Docker image build
	docker build -t alert-tracker:latest .

## 資料庫
migrate:  ## Alembic DB migration
	cd backend && python -m alembic upgrade head

## 版號管理
version-check:  ## 檢查全 repo 版號一致性
	python scripts/bump_version.py --check

bump:  ## 更新版號 (make bump V=1.1.0) 或 (make bump V=patch)
	python scripts/bump_version.py --bump $(V)

release:  ## 更新版號 + 建立 git tag (make release V=1.1.0)
	python scripts/bump_version.py --bump $(V) --tag

## 說明
help:  ## 顯示說明
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
