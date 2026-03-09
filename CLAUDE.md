# CLAUDE.md — AI 開發上下文

## 專案概覽

SRE Alert Tracking System v1.0.0 — 團隊值班 alert 追蹤紀錄表。自動拉取多座 K8s cluster 的 alert，提供人工填寫處理紀錄、週報管理、趨勢分析。

**技術棧：** FastAPI + React + TailwindCSS v4 + Vite + SQLAlchemy | SQLite / MariaDB | Docker + K8s

## 核心機制

| 概念 | 機制 |
|------|------|
| Alert 拉取 | Alertmanager API (主) + Prometheus query_range (補歷史)，APScheduler 定時觸發 |
| Dedup | fingerprint 為 unique key，同週期同 fingerprint 只更新 occurrence_count |
| 過濾 | Whitelist/Blacklist on alertname/group/severity |
| 週報框架 | 每週一自動建立 shift_report + 7 daily_sections |
| 認證 | `AT_AUTH_MODE=oauth2-proxy` → `X-Forwarded-User`；`none` = Lab |

## 目錄結構

```
backend/
  main.py              # FastAPI entry + StaticFiles + APScheduler
  config.py            # Settings (AT_* env vars + clusters.yaml)
  database.py          # SQLAlchemy engine + session
  alembic/             # DB migration scripts (env.py + versions/)
  models/              # 10 files, 12 tables (含 association tables)
  routers/             # 12 files, 13 routers (含 test_seed Lab-only)
  services/            # 7 files (alert_poller, dedup, filter_engine, report_generator, cluster_health, export_service, retention_manager)
  middleware/auth.py   # Auth middleware
  schemas/             # 8 files, Pydantic models
frontend/
  src/pages/           # 6 pages (ReportList, ReportDetail, AlertDetail, Search, Dashboard, Settings)
  src/components/      # 7 components (AlertCard, ErrorBoundary, LabelTagInput, LabelTag, SeverityBadge, ExportButton, Navbar)
  src/api/client.js    # Axios API wrapper
tests/                 # 16 test files, 112 passed
tests/e2e/             # Playwright E2E 瀏覽器測試
scripts/bump_version.py # 版號管理工具
VERSION                # 版號單一來源
config/clusters.yaml   # Cluster endpoint 清單 (ConfigMap)
lab/                   # Fake Prometheus + Alertmanager
k8s/                   # deployment, service, pvc, configmap, ingress
```

## 資料模型

| Table | 重要欄位 | 關聯 |
|-------|---------|------|
| clusters | name (UK), prometheus_url, alertmanager_url, status | → alert_records |
| shift_reports | year, week_number, operator_name | → daily_sections, ↔ weekly_tasks |
| daily_sections | report_id (FK), section_date | → alert_records |
| alert_records | fingerprint, alert_name, severity, cluster_id, phenomenon, impact, action_taken, occurrence_count | ↔ labels (M:N) |
| labels | name (UK), is_active | ↔ alert_records |
| weekly_tasks | title, is_active, sort_order | ↔ shift_reports (via report_task_assignments) |
| alert_filter_rules | rule_type, filter_field, filter_value | — |
| maintenance_windows | cluster_id, start_time, end_time, reason | — |
| poller_configs | interval_hours, lookback_hours | — |
| retention_configs | retention_months, purge_cron | — |

## API 端點

| 分類 | Endpoints |
|------|-----------|
| Reports | `GET/POST/PATCH /api/reports`, `GET /api/reports/{id}` |
| Sections | `PATCH /api/sections/{id}` |
| Alerts | `GET/PATCH /api/alerts`, `POST/DELETE /api/alerts/{id}/labels` |
| Labels | `GET/POST/PATCH /api/labels`, `POST /api/labels/merge`, `DELETE /api/labels/{id}` |
| Clusters | `GET /api/clusters`, `POST /api/clusters/health-check` |
| Filters | `GET/POST /api/filters`, `DELETE /api/filters/{id}` (204) |
| Poller | `GET /api/poller/status`, `POST /api/poller/trigger` |
| Tasks | `GET/POST/PATCH /api/tasks`, `PATCH /api/reports/{id}/tasks/{task_id}` |
| Export | `GET /api/export/report/{id}`, `GET /api/export/alerts` |
| Dashboard | `GET /api/dashboard/{trends,top-alerts,severity-distribution}` |
| Admin | `POST /api/admin/purge`, `GET/PATCH /api/admin/retention` |
| Maintenance | `GET/POST/PATCH/DELETE /api/maintenance` |
| Auth | `GET /api/me` |
| Test (Lab) | `POST /api/test/seed` (僅 `AT_AUTH_MODE=none`) |

## 開發規範

1. **API-First** — 後端 REST API 先行，前端僅為 consumer
2. **ORM only** — SQLAlchemy，禁止 raw SQL 拼接；SQLite/MariaDB 共用 schema
3. **Pydantic** — 所有 request/response 定義 schema
4. **SAST** — `open()` 帶 `encoding="utf-8"`；`subprocess` 禁止 `shell=True`
5. **環境變數** — 全大寫底線分隔，前綴 `AT_`
6. **Doc-as-Code** — 功能變更同步更新 CHANGELOG / CLAUDE.md / README
7. **測試** — 每個 router 至少 CRUD 測試；核心邏輯需單元測試

## Lab 環境

```bash
docker compose up -d          # App(8000) + Prometheus(9090) + Alertmanager(9093)
docker compose down            # 停止
docker compose --profile mariadb up -d  # 加入 MariaDB(3306)
```

Lab 預設：`AT_AUTH_MODE=none`、poller interval=1h、lookback=2h。

## 測試

```bash
cd backend && TESTING=1 python -m pytest ../tests/ -x -q    # 單元測試（快速）
TESTING=1 python -m pytest tests/ -v --tb=short             # 單元測試（詳細）
make test-e2e                                                # E2E 瀏覽器測試（需先 make dev）
```

`make test` 自動排除 `tests/e2e/`（需 playwright），兩者互不干擾。

E2E 用 pytest-playwright (sync_api)，透過 `POST /api/test/seed` 建立測試資料。

## 版號管理

單一來源：`VERSION` 檔案。`main.py` 啟動時讀取。

```bash
make version-check          # 檢查全 repo 版號一致性
make bump V=patch           # 遞增 patch (1.0.0 → 1.0.1)
make bump V=1.2.0           # 指定版號
make release V=1.2.0        # bump + git commit + git tag v1.2.0
```

bump 會自動同步：VERSION → Dockerfile LABEL → README.md → CLAUDE.md。
`make release` = bump → commit → tag（tag 永遠指向含新版號的 commit）。
CHANGELOG.md 需手動更新 release notes（在 `make release` 前完成）。

## Makefile

`make dev` / `make dev-down` / `make test` / `make test-e2e` / `make lint` / `make build` / `make version-check` / `make bump` / `make release` / `make help`

## 文件導覽

| 文件 | 用途 |
|------|------|
| `README.md` | 專案概覽、快速開始 |
| `docs/deployment-guide.md` | K8s 部署指南（Testing vs Production） |
| `docs/architecture-design.md` | 完整架構設計 |
| `docs/internal/testing-playbook.md` | 測試執行、整合測試規劃 |
| `docs/internal/github-release-playbook.md` | Git push + Release 流程 |
| `docs/internal/windows-mcp-playbook.md` | Cowork VM + Windows MCP 限制 |

## AI Agent 注意事項

- **Python tests** 在 Cowork VM 直接跑，`TESTING=1` 跳過 startup 副作用
- **前端 build** 需在有 `node_modules` 的目錄跑 `npm run build`，output 放 `backend/static/`
- **掛載路徑** 無法 `rm` 刪除檔案 → 清空內容或 docker exec rm
- **GitHub API** 被 sandbox 擋 → 改走 Windows MCP（詳見 playbook）
