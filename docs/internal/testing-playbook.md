# Testing Playbook

> 測試執行方式、整合測試規劃、Lab 驗證流程。

## 單元測試

```bash
# Cowork VM 直接跑（不需 Docker）
cd backend && TESTING=1 python -m pytest ../tests/ -v --tb=short

# 快速跑（失敗即停）
TESTING=1 python -m pytest tests/ -x -q

# 單一測試檔
TESTING=1 python -m pytest tests/test_poller.py -v
```

**環境變數 `TESTING=1`**：跳過 APScheduler 啟動、clusters.yaml sync 等 startup 副作用。

**conftest.py** 提供：SQLite in-memory DB fixture (`db`)、TestClient fixture (`client`)、共用 seed fixtures（`seed_cluster`、`seed_report_section`）。

## 測試檔案對照

| 測試檔 | 對應模組 | 測試數 |
|--------|---------|--------|
| `test_reports.py` | routers/reports | CRUD + 列表 |
| `test_alerts.py` | routers/alerts | CRUD + labels |
| `test_labels.py` | routers/labels | CRUD |
| `test_filter.py` | filter_engine + routers/filters | 引擎邏輯 + API |
| `test_poller.py` | alert_poller + routers/poller | mock httpx + trigger |
| `test_dedup.py` | dedup 邏輯 | 新增/更新/fingerprint |
| `test_report_generator.py` | report_generator | 週報自動建立 |
| `test_dashboard.py` | routers/dashboard | trends/top/severity |
| `test_export.py` | routers/export | CSV/JSON 格式 |
| `test_tasks.py` | routers/tasks | CRUD + assignment |
| `test_maintenance.py` | routers/maintenance | CRUD + 驗證 |
| `test_label_advanced.py` | labels merge/delete | 合併 + soft delete |
| `test_health.py` | cluster_health | health check |
| `test_auth.py` | middleware/auth | none mode |
| `test_admin.py` | routers/admin | retention + purge |
| `test_seed.py` | routers/test_seed | seed 端點 CRUD |
| `test_dedup_autofill.py` | dedup + annotation 映射 | autofill + raw_labels |
| `test_poller_resilience.py` | alert_poller HTTP 異常 | timeout/connection error/500/malformed JSON |
| `test_timezone_boundaries.py` | timezone_utils + report_generator | freezegun 週/日邊界 + ISO 跨年 |
| `test_export_markdown.py` | routers/export | Markdown 匯出格式 |
| `test_timezone_utils.py` | services/timezone_utils | 時區轉換 helpers |
| `test_cascade_delete.py` | models cascade | ShiftReport → Section → Alert 級聯刪除 |
| `test_alert_history.py` | routers/alerts (history) | fingerprint 優先、排除自身、過濾空 action_taken、limit |
| `test_correlation.py` | routers/dashboard (correlation) | 空週、重疊群組、孤立排除、窗口邊界、三方重疊 |
| `test_suggest.py` | routers/alerts (suggest) + llm_service | 501 disabled、404 not found、mocked LLM、default disabled |
| `test_security.py` | admin auth + SSRF + LLM sanitize | admin 權限、URL 驗證、錯誤訊息不洩漏 API key |

目前：28 files, 184 passed, 3 skipped。

## E2E 瀏覽器測試

使用 pytest-playwright (sync_api) 驗證核心使用者路徑。

**前置條件：**
```bash
make dev                            # 啟動 Lab（App + Prometheus + Alertmanager）
pip install pytest-playwright       # 安裝 playwright pytest plugin
playwright install chromium         # 安裝瀏覽器
```

**執行：**
```bash
make test-e2e                       # 跑 E2E（預設 http://localhost:8000）
E2E_BASE_URL=http://localhost:3000 make test-e2e  # 自訂 URL
```

**測試範圍（`tests/e2e/test_critical_workflow.py`）：**
- 報表列表 → 點擊報表連結 → 報表明細頁
- AlertCard 可見性 + textarea placeholder 驗證
- Debounce 自動儲存：填寫 → saved 指示器 → reload 持久化

**資料 seed：** `POST /api/test/seed`（Lab-only），由 `conftest.py` 的 `seeded_report` fixture 自動呼叫。

**注意事項：**
- `make test` 只跑單元測試（`tests/` 根目錄），不含 E2E
- `make test-e2e` 只跑 `tests/e2e/`，兩者互不干擾

## Integration Testing（規劃）

單元測試用 SQLite in-memory + mock httpx。整合測試需驗證真實元件互動：

**Layer 1 — Docker Compose Lab 驗證：**
```bash
docker compose up -d --build
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/poller/trigger
curl http://localhost:8000/api/reports | python3 -m json.tool
docker compose down
```

**Layer 2 — MariaDB 相容性：**
```bash
docker compose --profile mariadb up -d
# 設定 AT_DATABASE_URL=mysql+pymysql://root:devpass@localhost:3306/alert_tracker
# 跑相同測試驗證 ORM 相容
```

## Lab 環境驗證 Checklist

- [ ] `docker compose up -d` 三個 container 都 healthy
- [ ] `http://localhost:8000` 可開啟前端
- [ ] `POST /api/poller/trigger` 成功拉取 fake alerts
- [ ] 拉取後 Reports 列表有當週報表
- [ ] Alert 的 phenomenon/impact/action_taken 可編輯儲存
- [ ] Filter 規則可新增/刪除，重新拉取後生效
- [ ] Dashboard 圖表有資料

## 自檢方法論

功能完成後執行兩輪自檢：

**第一輪（正確性）：** 逐檔重讀 → 確認邏輯正確 → 測試 fixture 與真實行為一致 → 交叉比對 CLAUDE.md / CHANGELOG / README 計數

**第二輪（完整性）：** edge case 補充 → 跨文件一致性（版號、計數、引用）→ `pytest -v` 全過 → 文件更新

## 已知測試陷阱

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | `TESTING=1` 漏設 | Makefile `test` / `test-quick` 必須帶 `TESTING=1`，否則 APScheduler startup 副作用干擾測試 |
| 2 | Pydantic Settings `@property` 無法 mock | `config.settings.llm_enabled` 是 `@property`，`unittest.mock.patch` 會失敗。改 patch 底層欄位：`patch.object(settings, "llm_provider", "openai-compatible")` + `patch.object(settings, "llm_api_key", "sk-test")` |
| 3 | httpx mock 路徑要精確 | `patch("services.llm_service.httpx.AsyncClient")` — mock 使用處，不是定義處 |
| 4 | SQLite in-memory 不支援 `with_for_update()` | conftest 的 `get_db()` override 用 `StaticPool`；`with_for_update()` 在 SQLite 靜默忽略，不影響測試正確性但無法驗證 row-level locking |
| 5 | freezegun 與 APScheduler 衝突 | `TESTING=1` 關閉 scheduler 後才能安全使用 `@freeze_time` |

## 多 Agent Review 方法論（v1.2.0 經驗）

大功能完成後的品質審查流程：

**四路平行 review（Agent tool）：**
1. Backend agent — 正確性、race condition、error handling
2. Frontend agent — React anti-pattern、lint、效能
3. Tests agent — 覆蓋率缺口、fixture 正確性
4. Docs+Security agent — 文件一致性、env vars、SSRF、auth

**三波修正：**
- Wave 1 (P0): 安全性 + 正確性（admin auth、SSRF、key exposure、race condition）
- Wave 2 (P1): 文件同步 + 生產配置（CHANGELOG、README、architecture、OpenAPI toggle）
- Wave 3 (P2): 程式碼整潔（共用常數提取、component 拆分、dead code 移除）

每波修完跑 `make test` + `make lint` 確認不回歸。
