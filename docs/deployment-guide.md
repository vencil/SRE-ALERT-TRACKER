# Deployment Guide

> SRE Alert Tracking System — Lab / Testing / Production 部署指南。

---

## 環境總覽

| 項目 | Lab (本機) | Testing (K8s) | Production (K8s) |
|------|-----------|---------------|-------------------|
| 啟動方式 | `make dev-local` 或 `docker compose` | `kubectl apply` | `kubectl apply` |
| 認證 | `AT_AUTH_MODE=none` | `none` | `oauth2-proxy` (必須) |
| Admin 限制 | 無（Lab 全開放） | 無 | `AT_ADMIN_USERS` 限制 |
| 資料庫 | SQLite (本機 `./data/`) | SQLite (PVC) | SQLite (PVC) 或 MariaDB |
| Poller | 1h / 2h | 4h / 6h | 8h / 12h |
| TLS | 無 | 可選 | 必須 |
| OpenAPI Docs | 啟用 | 啟用 | `AT_OPENAPI_ENABLED=false` 建議關閉 |
| Security Context | 無 | 建議啟用 | 必須啟用 |
| Seed 端點 | 可用 | 可用 (若 auth=none) | 不可用 |
| LLM / AIOps | 可選 | 可選 | 可選 (`AT_LLM_PROVIDER`) |

---

## 1. Lab 本機開發（最快上手）

兩種方式任選：

### 方式 A — 直接跑 Python（秒級 hot-reload，推薦日常開發）

```bash
# 安裝 Python 依賴（首次）
cd backend && pip install -r requirements.txt

# 啟動後端（改 code 自動 reload）
make dev-local
# → http://localhost:8000  (API + Swagger)

# （可選）另開 terminal 啟動前端 Vite dev server
make dev-fe
# → http://localhost:3000  (HMR，proxy /api → :8000)
```

> **注意：** 這個模式下沒有 Prometheus / Alertmanager，Poller 拉取會失敗但不影響前端開發和 API 測試。可搭配 `POST /api/test/seed` 注入假資料。

### 方式 B — Docker Compose（完整環境含 Prometheus + Alertmanager）

```bash
# 首次或 Dockerfile 有改動
make dev

# 日常啟動（不重新 build，秒起）
make dev-up

# 查看日誌
make dev-logs

# 停止
make dev-down
```

啟動後：

| 服務 | URL |
|------|-----|
| App（API + 前端） | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/docs |
| Fake Prometheus | http://localhost:9090 |
| Fake Alertmanager | http://localhost:9093 |

### 測試

```bash
make test-quick    # 快速驗證（首個失敗即停）
make test          # 完整單元測試（184 tests）
make lint          # Ruff linter
make test-e2e      # E2E 瀏覽器測試（需先 make dev）
```

---

## 2. Docker Image

CI 自動產出（push `v*` tag 觸發 `.github/workflows/release.yaml`）：

```bash
# 從 GHCR 拉取（替換為實際版號）
docker pull ghcr.io/vencil/sre-alert-tracker:<version>

# 或本機 build
make build
# 等同 docker build -t alert-tracker:latest .
```

Image 為 multi-stage build（Node 22 frontend → Python 3.12 backend），non-root user，內建 HEALTHCHECK。

---

## 3. Testing / Staging 部署 (K8s)

目標：驗證系統功能、Poller 拉取、前端互動，不需要完整安全機制。

### 一鍵部署

```bash
# 建立 namespace
kubectl create namespace sre-alert-tracker

# 套用所有資源
kubectl apply -n sre-alert-tracker \
  -f k8s/pvc.yaml \
  -f k8s/service.yaml

# ConfigMap — 指向 staging cluster
kubectl apply -n sre-alert-tracker -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: sre-alert-tracker-clusters
data:
  clusters.yaml: |
    clusters:
      - name: staging-cluster
        prometheus_url: "http://prometheus.monitoring.svc:9090"
        alertmanager_url: "http://alertmanager.monitoring.svc:9093"
        interval_hours: 4
        pull_info: true
EOF

# Deployment — 覆寫為 testing 配置
kubectl apply -n sre-alert-tracker -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sre-alert-tracker
  labels:
    app: sre-alert-tracker
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: sre-alert-tracker
  template:
    metadata:
      labels:
        app: sre-alert-tracker
    spec:
      securityContext:
        runAsNonRoot: true
        fsGroup: 1000
      initContainers:
        - name: db-migrate
          image: ghcr.io/vencil/sre-alert-tracker:<version>
          command: ["python", "-m", "alembic", "upgrade", "head"]
          env:
            - { name: AT_AUTH_MODE, value: "none" }
            - { name: AT_DATA_DIR, value: "/data" }
            - { name: AT_CONFIG_DIR, value: "/app/config" }
          volumeMounts:
            - { name: data, mountPath: /data }
            - { name: clusters-config, mountPath: /app/config, readOnly: true }
            - { name: tmp, mountPath: /tmp }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
      containers:
        - name: sre-alert-tracker
          image: ghcr.io/vencil/sre-alert-tracker:<version>
          ports:
            - { containerPort: 8000, protocol: TCP, name: http }
          env:
            - { name: AT_AUTH_MODE, value: "none" }
            - { name: AT_DATA_DIR, value: "/data" }
            - { name: AT_CONFIG_DIR, value: "/app/config" }
            - { name: AT_POLLER_INTERVAL_HOURS, value: "4" }
            - { name: AT_POLLER_LOOKBACK_HOURS, value: "6" }
          volumeMounts:
            - { name: data, mountPath: /data }
            - { name: clusters-config, mountPath: /app/config, readOnly: true }
            - { name: tmp, mountPath: /tmp }
          livenessProbe:
            httpGet: { path: /api/health, port: http }
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet: { path: /api/health, port: http }
            initialDelaySeconds: 5
            periodSeconds: 10
          startupProbe:
            httpGet: { path: /api/health, port: http }
            initialDelaySeconds: 3
            periodSeconds: 5
            failureThreshold: 10
          resources:
            requests: { cpu: 100m, memory: 256Mi }
            limits: { cpu: 500m, memory: 512Mi }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
      volumes:
        - { name: data, persistentVolumeClaim: { claimName: sre-alert-tracker-data } }
        - { name: clusters-config, configMap: { name: sre-alert-tracker-clusters } }
        - { name: tmp, emptyDir: { sizeLimit: 64Mi } }
EOF
```

### 驗證

```bash
kubectl rollout status -n sre-alert-tracker deployment/sre-alert-tracker
kubectl port-forward -n sre-alert-tracker svc/sre-alert-tracker 8000:8000
```

| 檢查項 | 指令 / URL |
|--------|-----------|
| Health | `curl http://localhost:8000/api/health` → 200 |
| Clusters | `curl http://localhost:8000/api/clusters` → status=healthy |
| 手動拉取 | `curl -X POST http://localhost:8000/api/poller/trigger` |
| Seed 測試資料 | `curl -X POST http://localhost:8000/api/test/seed` |
| Swagger | http://localhost:8000/docs |
| 前端 | http://localhost:8000 |

---

## 4. Production 部署 (K8s)

Production 必須啟用認證 + TLS + 完整安全配置。

### Step 1 — ConfigMap（Cluster 清單）

```bash
kubectl apply -n sre-alert-tracker -f k8s/configmap.yaml
```

編輯 `k8s/configmap.yaml` 填入實際的 production cluster endpoints。URL 會在啟動時經過 SSRF 驗證（封鎖 metadata endpoints、link-local 位址）。

### Step 2 — Secret（敏感環境變數）

```bash
kubectl create secret generic sre-alert-tracker-env \
  -n sre-alert-tracker \
  --from-literal=AT_CORS_ORIGINS="https://alert-tracker.example.com" \
  --from-literal=AT_ADMIN_USERS="poyu,john" \
  --from-literal=AT_OPENAPI_ENABLED="false"
  # ↓ 可選：MariaDB
  # --from-literal=AT_DATABASE_URL="mysql+pymysql://user:pass@mariadb.svc:3306/alert_tracker"
  # ↓ 可選：AIOps LLM
  # --from-literal=AT_LLM_PROVIDER="openai-compatible"
  # --from-literal=AT_LLM_API_KEY="sk-..."
  # --from-literal=AT_LLM_API_BASE="https://api.openai.com/v1"
  # --from-literal=AT_LLM_MODEL="gpt-4o-mini"
```

Deployment 的 `envFrom.secretRef` 會自動載入（設為 `optional: true`，不存在也不影響啟動）。

### Step 3 — PVC + Deployment + Service

```bash
kubectl apply -n sre-alert-tracker \
  -f k8s/pvc.yaml \
  -f k8s/deployment.yaml \
  -f k8s/service.yaml
```

`deployment.yaml` 預設即為 production 配置，內建：Recreate strategy、Alembic init-container、`runAsNonRoot`、`readOnlyRootFilesystem`、`drop ALL` capabilities、三層 probes、resource limits。

### Step 4 — Ingress + oauth2-proxy

```bash
# 確保 oauth2-proxy 已部署
kubectl apply -n sre-alert-tracker -f k8s/ingress.yaml
```

`ingress.yaml` 會透過 nginx annotation 將所有請求導向 oauth2-proxy 驗證，成功後注入 `X-Forwarded-User` header。

TLS 證書可手動建立或用 cert-manager：

```bash
# 手動
kubectl create secret tls alert-tracker-tls \
  -n sre-alert-tracker \
  --cert=tls.crt --key=tls.key

# 或在 ingress.yaml 加 annotation：
# cert-manager.io/cluster-issuer: letsencrypt-prod
```

> **Production 認證行為：**
> - 所有請求必須帶 `X-Forwarded-User` header（由 oauth2-proxy 注入）
> - 缺少 header → 401；非 admin 用戶存取 `/api/admin/*` → 403
> - `POST /api/test/seed` 端點完全不可用（router 不註冊）
> - Service 為 ClusterIP，只有 Ingress 能觸達，防止 header 偽造
> - CORS 由 `AT_CORS_ORIGINS` 白名單控制

### 驗證

```bash
kubectl rollout status -n sre-alert-tracker deployment/sre-alert-tracker
curl -I https://alert-tracker.example.com/api/health
```

| 檢查項 | 預期結果 |
|--------|---------|
| oauth2-proxy 登入 | 導向 OIDC provider → 登入後回到 App |
| `GET /api/me` | 回傳正確 username |
| 未登入存取 API | 401 或 redirect to login |
| `GET /api/clusters` | 所有 cluster status=healthy |
| `POST /api/test/seed` | 404（production 下 router 不註冊） |
| `GET /docs` | 404（`AT_OPENAPI_ENABLED=false` 時） |
| `POST /api/admin/purge` | 非 admin 用戶回 403 |
| Pod logs | Poller 定時拉取正常，無錯誤 |

---

## 環境變數完整參考

| 變數 | 預設值 | 說明 |
|------|--------|------|
| **核心** | | |
| `AT_AUTH_MODE` | `oauth2-proxy` | `none` 關閉認證 (Lab/Testing) |
| `AT_DATABASE_URL` | (空) | 空=SQLite；`mysql+pymysql://...`=MariaDB |
| `AT_DATA_DIR` | `/data` | SQLite 資料目錄 |
| `AT_CONFIG_DIR` | `/app/config` | clusters.yaml 目錄 |
| `AT_DISPLAY_TIMEZONE` | `Asia/Taipei` | IANA 時區，影響顯示與週報交接（DB 存 UTC） |
| **Poller** | | |
| `AT_POLLER_INTERVAL_HOURS` | `8` | 拉取間隔 |
| `AT_POLLER_LOOKBACK_HOURS` | `12` | 回溯窗口（建議 > interval，刻意重疊用 dedup 確保不漏） |
| **安全** | | |
| `AT_CORS_ORIGINS` | (空) | 逗號分隔的允許來源（Production 必填；Lab 自動允許全部） |
| `AT_ADMIN_USERS` | (空) | 允許存取 `/api/admin/*` 的用戶（逗號分隔），空=所有認證用戶 |
| `AT_OPENAPI_ENABLED` | `true` | `false` 隱藏 `/docs`、`/redoc`、`/openapi.json` |
| **AIOps（可選）** | | |
| `AT_LLM_PROVIDER` | `none` | `openai-compatible` 啟用 AI 建議 |
| `AT_LLM_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `AT_LLM_API_KEY` | (空) | LLM API key（建議放 Secret） |
| `AT_LLM_MODEL` | `gpt-4o-mini` | 模型名稱 |

---

## 常見操作

### 手動觸發 Poller

```bash
curl -X POST http://localhost:8000/api/poller/trigger
curl http://localhost:8000/api/poller/status
```

### 查看 Pod Logs

```bash
kubectl logs -n sre-alert-tracker -f deployment/sre-alert-tracker
kubectl logs -n sre-alert-tracker deployment/sre-alert-tracker -c db-migrate
```

### DB Migration（通常自動）

Init-container 每次 Pod 啟動時自動執行 `alembic upgrade head`。手動操作：

```bash
kubectl exec -n sre-alert-tracker -it deployment/sre-alert-tracker -- python -m alembic current
kubectl exec -n sre-alert-tracker -it deployment/sre-alert-tracker -- python -m alembic upgrade head
```

### 資料備份（SQLite）

```bash
kubectl cp -n sre-alert-tracker <pod>:/data/alerts.db ./alerts-backup-$(date +%Y%m%d).db
```

### 手動 Purge 舊資料

```bash
curl -X POST http://localhost:8000/api/admin/purge
```

---

## Kustomize 建議結構（可選）

若需同時管理 testing 與 production，建議 Kustomize overlay：

```
k8s/
├── base/                          # 現有 k8s/ 目錄直接作為 base
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── pvc.yaml
│   └── configmap.yaml
├── overlays/
│   ├── testing/
│   │   ├── kustomization.yaml
│   │   ├── configmap-patch.yaml   # staging cluster endpoints
│   │   └── deployment-patch.yaml  # AT_AUTH_MODE=none, interval=4h
│   └── production/
│       ├── kustomization.yaml
│       ├── configmap-patch.yaml   # production cluster endpoints
│       ├── ingress.yaml           # TLS + oauth2-proxy
│       └── secret-generator.yaml  # AT_DATABASE_URL, AT_ADMIN_USERS 等
```

```bash
kubectl apply -k k8s/overlays/testing/
kubectl apply -k k8s/overlays/production/
```

---

## 故障排查

| 症狀 | 可能原因 | 排查方式 |
|------|---------|---------|
| Pod CrashLoopBackOff | Alembic migration 失敗 | `kubectl logs <pod> -c db-migrate` |
| 401 Unauthorized | oauth2-proxy 未注入 header | 確認 Ingress annotations、oauth2-proxy 部署 |
| 403 Admin access denied | 用戶不在 `AT_ADMIN_USERS` | 確認 Secret 中的值，或設為空（全開放） |
| Cluster status=unhealthy | Prometheus/Alertmanager 不可達 | 確認 cluster 間網路策略、Service DNS |
| 報表未自動生成 | 時區或 APScheduler 問題 | Pod logs 搜尋 `report_generator` |
| Poller 拉取為空 | Filter rules 過嚴 | `GET /api/filters` 確認、暫時清空測試 |
| SQLite locked | 多 replica 同時寫入 | 確認 `replicas: 1` + Recreate strategy |
| SSRF 驗證失敗 | clusters.yaml URL 指向 metadata endpoint | 修正 URL，避免 169.254.* / metadata.google.internal |
| AI 建議 501 | LLM 未啟用 | 設定 `AT_LLM_PROVIDER=openai-compatible` + API key |
