.PHONY: dev dev-down test test-backend lint build version-check bump help

## Lab 環境
dev:  ## 啟動 docker compose (Lab 模式)
	docker compose up -d --build

dev-down:  ## 停止 docker compose
	docker compose down

dev-logs:  ## 查看 app 日誌
	docker compose logs -f app

## 測試
test:  ## 執行全部 Python tests
	cd backend && python -m pytest ../tests/ -v --tb=short

test-backend:  ## 僅後端測試
	cd backend && python -m pytest ../tests/ -v --tb=short

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
