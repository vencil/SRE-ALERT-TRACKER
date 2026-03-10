# Changelog

All notable changes to the **SRE Alert Tracking System** will be documented in this file.

## [v1.2.0] — 2026-03-10

### 新增功能

- **Alert 歷史比對：** `GET /api/alerts/{id}/history` — fingerprint-first + alert_name fallback 雙層查詢，只回傳有 action_taken 的歷史紀錄。前端 AlertDetail 頁新增可展開的「歷史紀錄」區塊，顯示精準/同名匹配標籤、處理作法、值班人員
- **Alert 關聯分析：** `GET /api/dashboard/correlation` — sweep-line interval overlap 演算法分析同時段重疊的 alert 群組。前端 Dashboard 頁新增「Alert 關聯分析」區塊，支援按週選擇、展開群組詳情含 mini Gantt timeline
- **AIOps 處理建議：** `POST /api/alerts/{id}/suggest` — 可選 LLM 整合（`AT_LLM_PROVIDER` + `AT_LLM_API_KEY`），基於 alert 資訊與歷史處理紀錄生成建議。前端 AlertDetail 頁新增 AI 建議區塊，含 skeleton loading、disclaimer、一鍵套用。預設停用（`AT_LLM_PROVIDER=none`），不影響核心功能

### 安全性改善

- **Admin 端點權限控管：** `/api/admin/*` 新增 `require_admin` dependency，透過 `AT_ADMIN_USERS` 環境變數限制存取（Lab mode 全開放）
- **Cluster URL SSRF 防禦：** `clusters.yaml` 載入時驗證 URL scheme（僅 http/https）、封鎖 AWS/GCP metadata endpoints 與 link-local 位址
- **LLM API key 不外洩：** httpx 錯誤訊息經過 sanitize，不含 Authorization header；API 端點僅回傳通用錯誤訊息
- **Label merge 加鎖：** `with_for_update()` 防止高併發下的關聯遺失 race condition
- **Task assignment 容錯：** toggle endpoint 新增 IntegrityError 處理，應對 concurrent auto-create
- **OpenAPI 生產環境隱藏：** 新增 `AT_OPENAPI_ENABLED`（預設 true），production 可設為 false 隱藏 `/docs`、`/openapi.json`

### 前端改善

- **Dashboard CorrelationSection 重構：** 從 Dashboard.jsx 提取為獨立 component，修正 setState-in-render anti-pattern 改用 useEffect
- **Search.jsx 錯誤處理：** 初始載入 clusters/labels 的 Promise 加上 `.catch()` 防止 unhandled rejection
- **共用常數提取：** 新增 `constants.js` 統一 severity 顏色（hex + Tailwind class）與 chart 調色盤，消除 Dashboard / CorrelationSection / SeverityBadge 間的重複定義

### 測試

- 新增 `test_alert_history.py`（7 tests）：fingerprint 優先、排除自身、過濾空 action_taken、limit、週資訊
- 新增 `test_correlation.py`（7 tests）：空週、重疊群組、孤立排除、窗口邊界、cluster filter、三方重疊
- 新增 `test_suggest.py`（4 tests）：501 disabled、404 not found、mocked LLM success、default disabled
- 新增 `test_security.py`（9 tests）：admin auth、SSRF validation、LLM key sanitization
- 全部 184 passed, 3 skipped

---

## [v1.1.1] — 2026-03-10

### Bug Fixes

- **APScheduler 首次拉取延遲：** `interval` trigger 預設等待一個完整 interval 才首次執行。加上 `next_run_time=datetime.now()` 確保啟動時立即拉取
- **CORS 設定違反 W3C 規範：** `allow_origins=["*"]` + `allow_credentials=True` 不合規。改為環境感知：Lab mode (`auth_mode=none`) 使用 wildcard + 禁用 credentials；Production mode 從 `AT_CORS_ORIGINS` 環境變數讀取白名單

### 改進

- **Dedup 防禦性 UniqueConstraint：** alert_records 新增 `UniqueConstraint("daily_section_id", "fingerprint")`，作為 ORM 層 `with_for_update()` 的 DB 層級防禦，防止極端 race condition 產生重複紀錄
- **前端截斷警告：** 週報明細頁在 alert 數量達 500 筆上限時顯示黃色警告橫幅，引導使用者透過 CSV 匯出查看完整紀錄

### 測試

- 新增 `tests/conftest.py` 共用 fixtures（`seed_cluster`、`seed_report_section`），消除 test_dedup / test_dedup_autofill 重複 seed 邏輯
- 新增 `test_poller_resilience.py`（8 tests）：Alertmanager/Prometheus HTTP 異常（timeout、connection error、500、malformed JSON）
- 新增 `test_timezone_boundaries.py`（9 tests）：freezegun 凍結時間驗證 Asia/Taipei 週/日邊界、ISO 跨年
- 新增 UniqueConstraint 驗證測試（2 tests）：IntegrityError + 跨 section 同 fingerprint 允許
- E2E 自動儲存測試合併為 `@pytest.mark.parametrize`（3→1 test function）
- 全部 153 passed, 3 skipped

### 文件

- 更新 `docs/internal/github-release-playbook.md`、`windows-mcp-playbook.md`（Cowork VM push 可行性、已知陷阱擴充）

### 依賴（dev）

- 新增 `freezegun` 測試依賴

---

## [v1.1.0] — 2026-03-10

### 新增功能

- **時區支援：** 環境變數 `AT_DISPLAY_TIMEZONE`（預設 `Asia/Taipei`），影響介面時間戳顯示與週報交接日期區間。DB 一律儲存 UTC，啟動時驗證 IANA 時區名稱
- **Markdown 匯出：** `GET /api/export/report/{id}?format=md` 新增 Markdown 格式輸出，含 severity icon、時區轉換時間戳、alert 統計
- **Raw Labels / Annotations 儲存：** alert_records 新增 `raw_labels`、`raw_annotations` JSON 欄位，保留 Alertmanager 完整原始資料供進階查詢
- **Annotation 自動映射：** Poller 自動將 `annotations.summary` → `phenomenon`、`annotations.description` → `impact`，減少人工填寫負擔。已手動編輯欄位不被覆蓋

### 改進

- **Retention manager：** 月數計算從 `timedelta(days=N*30)` 改為 `dateutil.relativedelta`，消除 2 月誤差。Purge 查詢改用 `MAX()` 聚合取代 correlated subquery
- **Config 驗證：** `AT_DISPLAY_TIMEZONE` 啟動時透過 `ZoneInfo` 驗證，無效時區名稱立即報錯
- **timezone_utils 集中化：** `utc_now()`、`to_display_tz()`、`get_display_tz()` 等工具統一時區處理邏輯，取代散落各處的手動轉換
- **test_seed 輸入驗證：** `target_date` 格式錯誤回傳 400 而非 500

### 架構圖修正

- oauth2-proxy 定位改為 Ingress 層級（nginx annotation），保護全站（靜態檔案 + API），而非僅連接 FastAPI

### 測試

- 新增 19 tests：timezone_utils (10)、markdown export (7)、dedup autofill + raw_labels (5)
- 全部 134 passed, 3 skipped

### 依賴

- 新增 `python-dateutil==2.9.0.post0`

### Migration

- `a1b2c3d4e5f6_add_raw_labels_annotations`：alert_records 新增 `raw_labels`、`raw_annotations` TEXT 欄位

---

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
