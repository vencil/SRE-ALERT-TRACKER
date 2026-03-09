# Changelog

All notable changes to the **SRE Alert Tracking System** will be documented in this file.

## [v1.0.0] — 2026-03-08

完整功能實作 + 三輪自檢 + E2E 測試 + K8s 安全加固。

### Alert 拉取引擎

- 雙引擎 Poller：Alertmanager API（當前 firing）+ Prometheus query_range（歷史補充）
- Fingerprint dedup：同週期同 alert 只更新 occurrence_count
- Whitelist / Blacklist 過濾引擎（alertname / group / severity，支援 wildcard）
- Cluster health check（Prometheus + Alertmanager `/-/healthy`）
- 啟動時從 `clusters.yaml` sync 至 DB
- asyncio.Lock 併發保護、JSON parse 容錯

### 週報與紀錄

- 每週一 APScheduler 自動建立 shift_report + 7 daily_sections
- Alert 自動分配至對應 daily_section
- 值班人員填寫：phenomenon / impact / action_taken（debounced auto-save）
- 自訂 Label 標記（autocomplete、合併、soft delete）
- 每週例行任務 checklist（動態 CRUD + 報表指派）

### 前端（React + TailwindCSS v4 + Vite）

- 6 頁面：ReportList、ReportDetail、AlertDetail、Search、Dashboard、Settings
- 7 元件：AlertCard、ErrorBoundary、LabelTagInput、LabelTag、SeverityBadge、ExportButton、Navbar
- Dashboard：Recharts 趨勢折線圖、Top-N 柱狀圖、Severity 圓餅圖
- 匯出：瀏覽器列印 PDF（`@media print`）+ CSV/JSON API 下載
- ErrorBoundary 攔截未捕獲錯誤，避免白屏

### 後端 API（FastAPI + SQLAlchemy）

- 13 routers：reports, sections, alerts, labels, clusters, filters, poller, tasks, export, dashboard, maintenance, admin, test_seed (Lab-only)
- 7 services：alert_poller, dedup, filter_engine, report_generator, cluster_health, export_service, retention_manager
- Pydantic schema 驗證、SQLAlchemy eager loading（joinedload + subqueryload）
- Retention 管理：月數設定 + 排程/手動 purge + rollback 保護
- Alembic migration baseline（12 tables autogenerate）
- `config.py` import 時不建立目錄（避免非 Docker 環境 PermissionError）

### 認證與部署

- Auth middleware：`AT_AUTH_MODE=oauth2-proxy`（X-Forwarded-User）/ `none`（Lab）
- Dockerfile multi-stage build（Node frontend → Python backend），non-root user，HEALTHCHECK
- Lab 環境：docker-compose 一鍵啟動（App + Fake Prometheus + Fake Alertmanager）

### K8s 部署與安全加固

- Deployment：Alembic init-container 自動 migration、Recreate strategy（避免 SQLite dual-write）
- SecurityContext：runAsNonRoot、readOnlyRootFilesystem、drop ALL capabilities
- Probes：liveness + readiness + startupProbe
- Ingress：TLS 區塊、oauth2-proxy annotations
- envFrom secretRef 支援外部注入敏感 env
- emptyDir /tmp（readOnlyRootFilesystem 下 Python cache 可寫）

### 測試

- 單元測試：16 files, 112 passed（含 seed 端點測試）
- E2E 瀏覽器測試：pytest-playwright，3 classes / 9 tests（報表導航 → AlertCard → debounce 自動儲存）
- Lab-only `POST /api/test/seed` 端點供 E2E seed 資料

### 文件

- README.md：痛點分析、功能概覽、快速開始、K8s 部署指南、Swagger API Docs
- docs/architecture-design.md：完整架構設計
- docs/internal/：testing / github-release / windows-mcp playbooks
- CLAUDE.md：AI Agent 開發上下文速查
