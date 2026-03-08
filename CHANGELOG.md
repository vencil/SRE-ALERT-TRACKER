# Changelog

All notable changes to the **SRE Alert Tracking System** will be documented in this file.

## [v1.0.0] — Initial Release (2026-03-08)

完整功能實作 + 三輪自檢。

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
- 6 元件：AlertCard、LabelTagInput、LabelTag、SeverityBadge、ExportButton、Navbar
- Dashboard：Recharts 趨勢折線圖、Top-N 柱狀圖、Severity 圓餅圖
- 匯出：瀏覽器列印 PDF（`@media print`）+ CSV/JSON API 下載
- Promise.allSettled 錯誤隔離、useMemo 優化

### 後端 API（FastAPI + SQLAlchemy）

- 12 routers：reports, sections, alerts, labels, clusters, filters, poller, tasks, export, dashboard, maintenance, admin
- 7 services：alert_poller, dedup, filter_engine, report_generator, cluster_health, export_service, retention_manager
- Pydantic schema 驗證、SQLAlchemy eager loading（joinedload + subqueryload）
- Retention 管理：月數設定 + 排程/手動 purge + rollback 保護

### 認證與部署

- Auth middleware：`AT_AUTH_MODE=oauth2-proxy`（X-Forwarded-User）/ `none`（Lab）
- Dockerfile multi-stage build（Node frontend → Python backend），non-root user，HEALTHCHECK
- K8s manifests：Deployment + Service + PVC + ConfigMap + Ingress
- Lab 環境：docker-compose 一鍵啟動（App + Fake Prometheus + Fake Alertmanager）

### 測試

- 15 test files, 108 passed, 3 skipped
- 覆蓋：全部 routers CRUD + 核心邏輯（dedup, filter, report_generator, poller mock）

### 文件

- README.md：痛點分析、功能概覽、快速開始、K8s 部署指南
- docs/architecture-design.md：完整架構設計
- docs/internal/：testing / github-release / windows-mcp playbooks
- CLAUDE.md：AI Agent 開發上下文速查
