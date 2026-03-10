# CLAUDE.md — AI 開發上下文

## 專案概覽

SRE Alert Tracking System v1.2.0 — 團隊值班 alert 追蹤紀錄表。自動拉取多座 K8s cluster 的 alert，提供人工填寫處理紀錄、週報管理、趨勢分析。

**技術棧：** FastAPI + React + TailwindCSS v4 + Vite + SQLAlchemy | SQLite / MariaDB | Docker + K8s

## 核心機制

| 概念 | 機制 |
|------|------|
| Alert 拉取 | Alertmanager API (主) + Prometheus query_range (補歷史)，APScheduler 定時觸發 |
| Dedup | fingerprint 為 unique key，同週期同 fingerprint 只更新 occurrence_count。DB 層 UniqueConstraint + ORM 層 `with_for_update()` 雙重防禦 |
| 過濾 | Whitelist/Blacklist on alertname/group/severity |
| 週報框架 | 每週一自動建立 shift_report + 7 daily_sections（display timezone 基準） |
| 時區 | DB 存 UTC；`AT_DISPLAY_TIMEZONE=Asia/Taipei` 控制介面顯示與交接日期 |
| Annotation 映射 | Poller 自動將 `annotations.summary` → `phenomenon`、`description` → `impact` |
| 認證 | `AT_AUTH_MODE=oauth2-proxy` → `X-Forwarded-User`；`none` = Lab |
| Admin 權限 | `AT_ADMIN_USERS` 限制 `/api/admin/*` 端點存取；空值 = 所有認證用戶 |
| URL 驗證 | Cluster URL 防 SSRF（封鎖 metadata endpoints、link-local、非 http(s) scheme） |
| 歷史比對 | fingerprint-first + alert_name fallback，只回傳有 action_taken 的歷史紀錄 |
| Alert 關聯 | Sweep-line interval overlap 分析，找出同時段重疊的 alert 群組 |
| AIOps 建議 | 可選 LLM 整合（`AT_LLM_PROVIDER`），基於歷史處理紀錄生成建議 |

## 目錄結構

```
backend/
  main.py              # FastAPI entry + StaticFiles + APScheduler
  config.py            # Settings (AT_* env vars + clusters.yaml)
  database.py          # SQLAlchemy engine + session
  alembic/             # DB migration scripts (env.py + versions/)
  models/              # 10 files, 12 tables (含 association tables)
  routers/             # 12 files, 13 routers (含 test_seed Lab-only)
  services/            # 10 files: alert_poller, alert_query, dedup, filter_engine, report_generator, cluster_health, export_service, retention_manager, timezone_utils, llm_service
  middleware/auth.py   # Auth middleware
  schemas/             # 8 files, Pydantic models
frontend/
  src/pages/           # 6 pages (ReportList, ReportDetail, AlertDetail, Search, Dashboard, Settings)
  src/components/      # 8 components (AlertCard, CorrelationSection, ErrorBoundary, ExportButton, LabelTag, LabelTagInput, Navbar, SeverityBadge)
  src/api/client.js    # Axios API wrapper
tests/                 # 28 test files, 184 passed
tests/e2e/             # Playwright E2E 瀏覽器測試
scripts/bump_version.py # 版號管理工具
VERSION                # 版號單一來源
config/clusters.yaml   # Cluster endpoint 清單 (ConfigMap)
lab/                   # Fake Prometheus + Alertmanager
k8s/                   # deployment, service, pvc, configmap, ingress
.github/workflows/     # CI: release.yaml (test → build → release)
```

## 資料模型

| Table | 重要欄位 | 關聯 |
|-------|---------|------|
| clusters | name (UK), prometheus_url, alertmanager_url, status | → alert_records |
| shift_reports | year, week_number, operator_name | → daily_sections, ↔ weekly_tasks |
| daily_sections | report_id (FK), section_date | → alert_records |
| alert_records | fingerprint, alert_name, severity, cluster_id, raw_labels (JSON), raw_annotations (JSON), phenomenon, impact, action_taken, occurrence_count | ↔ labels (M:N) |
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
| Alerts | `GET/PATCH /api/alerts`, `POST/DELETE /api/alerts/{id}/labels`, `GET /api/alerts/{id}/history`, `POST /api/alerts/{id}/suggest` |
| Labels | `GET/POST/PATCH /api/labels`, `POST /api/labels/merge`, `DELETE /api/labels/{id}` |
| Clusters | `GET /api/clusters`, `POST /api/clusters/health-check` |
| Filters | `GET/POST /api/filters`, `DELETE /api/filters/{id}` (204) |
| Poller | `GET /api/poller/status`, `POST /api/poller/trigger` |
| Tasks | `GET/POST/PATCH /api/tasks`, `PATCH /api/reports/{id}/tasks/{task_id}` |
| Export | `GET /api/export/report/{id}?format=csv\|json\|md`, `GET /api/export/alerts` |
| Dashboard | `GET /api/dashboard/{trends,top-alerts,severity-distribution,correlation}` |
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

## CI/CD

`.github/workflows/release.yaml` — push `v*` tag 自動觸發：

1. **test** — Python 3.12 + `pytest`（排除 e2e）
2. **build** — Docker multi-stage build → Push to GHCR (`ghcr.io/vencil/sre-alert-tracker:<version>`)
3. **release** — 從 CHANGELOG.md 擷取 release notes → 建立 GitHub Release

Image tags：`<version>`、`<major>.<minor>`、`<sha>`。

**建議未來 CI 擴充：** `pip audit` + `npm audit` 檢查已知漏洞依賴。

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

### Playbook-First 工作模式

本專案採用 **playbook 驅動** 的 AI 協作模式。`docs/internal/` 下的 playbook 是歷次開發累積的實戰經驗，涵蓋環境限制、已知陷阱、最佳實踐。

**核心原則：遇到問題先查 playbook，不要從零摸索。**

| Playbook | 涵蓋範圍 | 什麼時候該讀 |
|----------|---------|-------------|
| `testing-playbook.md` | 測試執行、mock 技巧、已知 gotcha、多 Agent 審查方法論 | 跑測試前、寫新測試前、做 code review 前 |
| `github-release-playbook.md` | 版號管理、兩段式 commit 模式、Release checklist、CI 監控 | 發版前、tag/push 操作前 |
| `windows-mcp-playbook.md` | Cowork VM vs Windows MCP 分工、PATH 問題、16 項已知陷阱 | 任何需要 git push / GitHub API / npm build 的操作前 |

### 快速查閱指引

- **跑測試** → `testing-playbook.md`：`TESTING=1` 必帶、Pydantic property mock 用 `model_validator`、httpx mock 路徑是 `services.llm_service.httpx`
- **發版 / push** → `github-release-playbook.md` + `windows-mcp-playbook.md`：兩段式 commit（功能 commit → bump commit + tag）、VM `git push` 搭配 `~/.git-credentials` 為首選
- **前端 build** → `windows-mcp-playbook.md`：VM 可能 OOM，改走 Windows MCP 完整路徑 npm
- **GitHub API** → `windows-mcp-playbook.md`：VM sandbox 擋 `api.github.com`，必須走 Windows MCP PowerShell

### 環境速查

| 操作 | 環境 | 注意 |
|------|------|------|
| Python tests | Cowork VM | `TESTING=1` 跳過 APScheduler startup |
| 前端 build | Windows MCP（首選）或 VM | `npm run build` output → `backend/static/` |
| git commit / tag | Cowork VM | 掛載目錄共享，兩邊可見 |
| git push | Cowork VM（首選） | 需設 `~/.git-credentials`；Windows MCP 為備用（常 timeout） |
| GitHub API | Windows MCP | PowerShell `Invoke-RestMethod`，CJK 需 UTF8 encode |
| 檔案刪除 | Cowork VM | 掛載路徑需 `allow_cowork_file_delete` 啟用權限 |

### 擴充新領域

若開發過程中產生新的領域知識（例如：DB migration 流程、監控整合、新的外部 API 對接），應以 playbook 形式記錄到 `docs/internal/`，格式參照現有 playbook：

1. 開頭寫明適用範圍與相關文件連結
2. 環境/工具分工表格
3. 操作步驟（含可直接複製的指令）
4. 已知陷阱表格（編號、問題、解法）
5. 更新本文件的「Playbook」表格與「快速查閱指引」
