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

**conftest.py** 提供：SQLite in-memory DB fixture (`db`)、TestClient fixture (`client`)。

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

目前：108 passed, 3 skipped。

## Integration Testing（規劃）

單元測試用 SQLite in-memory + mock httpx。整合測試需驗證真實元件互動：

**Layer 1 — Docker Compose Lab 驗證：**
```bash
docker compose up -d --build
# 等 app 啟動
curl http://localhost:8000/api/health
# 觸發 poller（從 fake Prometheus + Alertmanager 拉取）
curl -X POST http://localhost:8000/api/poller/trigger
# 驗證 alert 寫入
curl http://localhost:8000/api/reports | python3 -m json.tool
docker compose down
```

**Layer 2 — API 端到端測試：**
- 用 `requests` 或 `httpx` 對 running app 做完整 CRUD 流程
- 驗證 poller → dedup → report 的完整資料流
- 驗證 filter rules 實際過濾效果

**Layer 3 — MariaDB 相容性：**
```bash
docker compose --profile mariadb up -d
# 設定 AT_DATABASE_URL=mysql+pymysql://root:devpass@localhost:3306/alert_tracker
# 跑相同的 API 端到端測試
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
