# CLAUDE.md — AI 開發上下文

## 專案概覽

SRE Alert Tracking System v1.2.1 — 團隊值班 alert 追蹤紀錄表。自動拉取多座 K8s cluster 的 alert，提供人工填寫處理紀錄、週報管理、趨勢分析。

**技術棧：** FastAPI + React + TailwindCSS v4 + Vite + SQLAlchemy | SQLite / MariaDB | Docker + K8s

## 核心機制

| 概念 | 機制 |
|------|------|
| Alert 拉取 | Alertmanager API (主) + Prometheus query_range (補歷史)，APScheduler 定時 |
| Dedup | fingerprint unique key，DB UniqueConstraint + ORM `with_for_update()` 雙重防禦 |
| 過濾 | Whitelist/Blacklist on alertname/group/severity |
| 週報框架 | 每週一自動建立 shift_report + 7 daily_sections（display timezone 基準） |
| 時區 | DB 存 UTC；`AT_DISPLAY_TIMEZONE=Asia/Taipei` 控制介面與交接日期 |
| Annotation 映射 | Poller 自動 `annotations.summary` → `phenomenon`、`description` → `impact` |
| 認證 | `AT_AUTH_MODE=oauth2-proxy` → `X-Forwarded-User`；`none` = Lab |
| Admin 權限 | `AT_ADMIN_USERS` 限制 `/api/admin/*`；空值 = 全開放 |
| URL 驗證 | Cluster URL 防 SSRF（metadata endpoints、link-local、非 http(s)） |
| 歷史比對 | fingerprint-first + alert_name fallback，只回傳有 action_taken 的紀錄 |
| Alert 關聯 | Sweep-line interval overlap，找出同時段重疊 alert 群組 |
| AIOps 建議 | 可選 LLM 整合（`AT_LLM_PROVIDER`），基於歷史紀錄生成建議 |

## 目錄結構（概要）

```
backend/     main.py(entry) | config.py(env) | database.py | alembic/
             models/(10) | routers/(12) | services/(10) | schemas/(8) | middleware/
frontend/    src/pages/(6) | src/components/(8) | src/api/client.js
tests/       26 unit test files + e2e/ (Playwright)
scripts/     bump_version.py    config/  clusters.yaml
lab/         Fake Prom + AM     k8s/     K8s manifests
```

> 完整目錄結構、資料模型 (12 tables)、API 端點 (14 分類) → [architecture-design.md](docs/architecture-design.md) §3, §4, §12

## 開發規範

1. **API-First** — 後端 REST API 先行，前端僅為 consumer
2. **ORM only** — SQLAlchemy，禁 raw SQL；SQLite/MariaDB 共用 schema
3. **Pydantic** — 所有 request/response 定義 schema
4. **SAST** — `open()` 帶 `encoding="utf-8"`；`subprocess` 禁 `shell=True`
5. **環境變數** — 全大寫底線分隔，前綴 `AT_`
6. **Doc-as-Code** — 功能變更同步更新 CHANGELOG / CLAUDE.md / README
7. **測試** — 每個 router 至少 CRUD 測試；核心邏輯需單元測試

## 常用指令

```bash
# Lab 環境
docker compose up -d              # 完整環境（App:8000 + Prom:9090 + AM:9093）
make dev-local                    # 本機直跑後端（auto-reload，純 API 開發）
make dev-fe                       # 前端 Vite HMR（proxy → :8000）

# 測試
make test                         # 單元測試（排除 e2e）
make test-quick                   # 快速模式（-x -q）
make test-e2e                     # E2E 瀏覽器測試（需先 make dev）

# 版號與發版（詳見 github-release-playbook）
make version-check                # 全 repo 版號一致性
make bump V=patch                 # 遞增 patch
make release V=1.2.1              # bump + commit + tag
```

## CI/CD

`.github/workflows/release.yaml` — push `v*` tag → test → build (GHCR) → GitHub Release。
Image tags：`<version>`、`<major>.<minor>`、`<sha>`。

## 文件導覽

| 文件 | 用途 |
|------|------|
| [`README.md`](README.md) | 專案概覽、快速開始、環境變數 |
| [`docs/architecture-design.md`](docs/architecture-design.md) | 完整架構、資料模型、API、AIOps 機制 |
| [`docs/deployment-guide.md`](docs/deployment-guide.md) | Lab / Testing / Production 部署指南 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本變更日誌 |

## AI Agent 注意事項

### Playbook-First 工作模式

**核心原則：遇到問題先查 playbook，不要從零摸索。** `docs/internal/` 是歷次開發累積的實戰經驗。

| Playbook | 什麼時候該讀 |
|----------|-------------|
| [`testing-playbook.md`](docs/internal/testing-playbook.md) | 跑測試、寫新測試、code review 前 |
| [`github-release-playbook.md`](docs/internal/github-release-playbook.md) | 發版、tag/push 前 |
| [`windows-mcp-playbook.md`](docs/internal/windows-mcp-playbook.md) | git push / GitHub API / npm build 前 |

### 快速查閱

- **跑測試** → testing-playbook：`TESTING=1` 必帶、Pydantic mock 用 `model_validator`、httpx mock 路徑 `services.llm_service.httpx`
- **發版** → github-release-playbook + windows-mcp-playbook：兩段式 commit（功能 → bump + tag）、VM `git push`（`~/.git-credentials`）為首選
- **前端 build** → windows-mcp-playbook：VM 可能 OOM，走 Windows MCP 完整路徑 npm
- **GitHub API** → windows-mcp-playbook：VM sandbox 擋 `api.github.com`，走 Windows MCP PowerShell

### 環境速查

| 操作 | 環境 | 注意 |
|------|------|------|
| Python tests | Cowork VM | `TESTING=1` 跳過 APScheduler startup |
| 前端 build | Windows MCP（首選）或 VM | output → `backend/static/` |
| git commit / tag | Cowork VM | 掛載目錄共享 |
| git push | Cowork VM（首選） | 需設 `~/.git-credentials`；Windows MCP 備用 |
| GitHub API | Windows MCP | PowerShell `Invoke-RestMethod` |
| 檔案刪除 | Cowork VM | 掛載路徑需 `allow_cowork_file_delete` |

### 擴充新領域

新的領域知識（DB migration、監控整合、外部 API 對接等）以 playbook 形式記錄到 `docs/internal/`：

1. 適用範圍與相關文件連結
2. 環境/工具分工表格
3. 操作步驟（含可複製指令）
4. 已知陷阱表格（編號、問題、解法）
5. 回來更新本節 Playbook 表格
