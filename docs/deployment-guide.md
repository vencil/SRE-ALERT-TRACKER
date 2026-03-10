# Kubernetes Deployment Guide

> SRE Alert Tracking System — Testing 與 Production 環境部署指南。

---

## 環境概覽

系統支援三種部署階段，核心差異在認證、資料庫、拉取頻率與安全配置：

| 項目 | Lab (本機) | Testing / Staging (K8s) | Production (K8s) |
|------|-----------|------------------------|-------------------|
| 啟動方式 | `docker compose up -d` | `kubectl apply` | `kubectl apply` |
| 認證 | `AT_AUTH_MODE=none` | `none` 或 `oauth2-proxy` | `oauth2-proxy` (必須) |
| 資料庫 | SQLite (本機 `./data/`) | SQLite (PVC) | SQLite (PVC) 或 MariaDB |
| Poller 間隔 | 1h (快速驗證) | 4h (頻繁觀察) | 8h (正式) |
| Lookback | 2h | 6h | 12h |
| TLS | 無 | 可選 | 必須 |
| Security Context | 無 | 建議啟用 | 必須啟用 |
| Ingress | 無 (直接 port) | 可選 | 必須 (oauth2-proxy) |
| Cluster 來源 | `lab/` fake endpoints | Staging cluster endpoints | Production cluster endpoints |
| Seed endpoint | 可用 (`/api/test/seed`) | 可用 (若 auth=none) | 不可用 (auth≠none) |
| 資料保留 | 無限制 | 3-6 個月 | 6-12 個月 |

---

## 前置準備

### Docker Image

CI 自動產出（push `v*` tag 觸發 `.github/workflows/release.yaml`）：

```bash
# 從 GHCR 拉取
docker pull ghcr.io/vencil/sre-alert-tracker:1.0.0

# 或本機 build
docker build -t sre-alert-tracker:1.0.0 .
```

Image 為 multi-stage build（Node 20 frontend → Python 3.12 backend），non-root user，內建 HEALTHCHECK。

### K8s Namespace（建議）

```bash
kubectl create namespace sre-alert-tracker
# 以下所有 kubectl 指令加上 -n sre-alert-tracker
```

---

## Testing / Staging 部署

Testing 環境的目標是驗證系統功能、poller 拉取邏輯、前端互動，不需要完整的安全機制。

### Step 1: ConfigMap — Cluster 清單

建立指向 staging cluster 的 ConfigMap：

```yaml
# k8s/configmap-testing.yaml
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
        pull_info: true          # testing 環境也拉 info severity
        instance_label: "instance"
```

```bash
kubectl apply -f k8s/configmap-testing.yaml
```

### Step 2: PVC

```bash
kubectl apply -f k8s/pvc.yaml
```

PVC 使用 `ReadWriteOnce`，1Gi 足以存放數月的 SQLite 資料。

### Step 3: Deployment（Testing 覆寫）

直接使用 `k8s/deployment.yaml`，但覆寫關鍵環境變數：

```bash
# 方法 A: 直接修改 env 欄位後 apply
# 方法 B: 用 kustomize overlay 覆寫（推薦）
```

**Testing 需要覆寫的環境變數：**

```yaml
env:
  - name: AT_AUTH_MODE
    value: "none"                    # ← Testing 關閉認證
  - name: AT_POLLER_INTERVAL_HOURS
    value: "4"                       # ← 更頻繁拉取
  - name: AT_POLLER_LOOKBACK_HOURS
    value: "6"
```

> **`AT_AUTH_MODE=none` 的效果：**
> - Auth middleware 跳過 header 檢查，所有 request 的 user 為 `dev-user`
> - `POST /api/test/seed` 端點可用（方便 E2E 測試注入資料）
> - 不需要 oauth2-proxy、不需要 Ingress TLS

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Step 4: 驗證（Testing）

```bash
# 等待 Pod ready
kubectl rollout status deployment/sre-alert-tracker

# Port-forward 到本機
kubectl port-forward svc/sre-alert-tracker 8000:8000

# 開啟瀏覽器
# App:     http://localhost:8000
# Swagger: http://localhost:8000/docs
# Health:  http://localhost:8000/api/health
```

驗證清單：

1. `GET /api/health` 回傳 200
2. `GET /api/clusters` 看到 staging cluster（status=healthy）
3. `POST /api/poller/trigger` 手動觸發拉取，觀察 alert 是否入庫
4. 前端頁面可正常瀏覽報表、填寫紀錄
5. `POST /api/test/seed` 可成功建立測試資料（僅 `AT_AUTH_MODE=none`）

---

## Production 部署

Production 環境必須啟用認證、TLS、完整的安全配置。

### Step 1: ConfigMap — Production Cluster 清單

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sre-alert-tracker-clusters
data:
  clusters.yaml: |
    clusters:
      - name: prod-cluster-1
        prometheus_url: "http://prometheus.prod-1.svc:9090"
        alertmanager_url: "http://alertmanager.prod-1.svc:9093"
        interval_hours: 8
        pull_info: false
        instance_label: "instance"
      - name: prod-cluster-2
        prometheus_url: "http://prometheus.prod-2.svc:9090"
        alertmanager_url: "http://alertmanager.prod-2.svc:9093"
```

### Step 2: Secret（敏感環境變數，可選）

若使用 MariaDB 或有其他敏感設定：

```bash
kubectl create secret generic sre-alert-tracker-env \
  --from-literal=AT_DATABASE_URL="mysql+pymysql://user:pass@mariadb.svc:3306/alert_tracker"
```

Deployment 的 `envFrom.secretRef` 會自動載入此 Secret（設為 `optional: true`，不存在也不影響啟動）。

### Step 3: PVC + Deployment + Service

```bash
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml    # 預設已是 production 配置
kubectl apply -f k8s/service.yaml
```

**Production deployment.yaml 的安全特性（已內建）：**

| 特性 | 說明 |
|------|------|
| Recreate strategy | 避免 SQLite dual-write（兩個 Pod 同時寫一個 DB 檔案） |
| Alembic init-container | Pod 啟動前自動執行 DB migration |
| `runAsNonRoot: true` | 容器不以 root 執行 |
| `readOnlyRootFilesystem: true` | 防止容器內寫入系統檔案 |
| `drop: ["ALL"]` capabilities | 最小權限原則 |
| `allowPrivilegeEscalation: false` | 禁止提權 |
| emptyDir `/tmp` | readOnlyRootFilesystem 下 Python cache 的可寫空間 |
| liveness + readiness + startup probes | 自動健康檢查與滾動部署控制 |
| Resource limits | CPU 500m / Memory 512Mi |

### Step 4: Ingress + oauth2-proxy

Production 必須透過 oauth2-proxy 保護 API：

```bash
# 先確保 oauth2-proxy 已部署在同 namespace 或可達位置
kubectl apply -f k8s/ingress.yaml
```

`ingress.yaml` 包含：
- `nginx.ingress.kubernetes.io/auth-url` → oauth2-proxy 驗證端點
- `nginx.ingress.kubernetes.io/auth-response-headers` → 注入 `X-Forwarded-User`
- TLS 區塊（需先建立 TLS Secret，可用 cert-manager 自動化）

```bash
# TLS Secret（手動方式）
kubectl create secret tls alert-tracker-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key

# 或使用 cert-manager annotation（在 ingress.yaml 加入）
# cert-manager.io/cluster-issuer: letsencrypt-prod
```

> **重要：** `AT_AUTH_MODE=oauth2-proxy` 時：
> - 所有 API 請求必須帶 `X-Forwarded-User` header（由 oauth2-proxy 注入）
> - 缺少 header 的請求回傳 401
> - `POST /api/test/seed` 端點完全不可用（router 不註冊）
> - Service 使用 ClusterIP，只有 Ingress 能觸達，防止 header 偽造
> - **CORS：** 必須設定 `AT_CORS_ORIGINS`（逗號分隔），否則跨域請求將被拒絕。Lab 模式 (`AT_AUTH_MODE=none`) 自動允許所有來源。

### Step 5: 驗證（Production）

```bash
kubectl rollout status deployment/sre-alert-tracker

# 透過 Ingress URL 驗證（需通過 oauth2-proxy 登入）
curl -I https://alert-tracker.example.com/api/health
```

驗證清單：

1. oauth2-proxy 登入流程正常，使用者被導向 OIDC provider
2. 登入後 `GET /api/me` 回傳正確的 username
3. 未登入直接存取 API 回傳 401
4. `GET /api/clusters` 顯示所有 production cluster 且 status=healthy
5. Poller 自動拉取正常（查看 Pod logs）
6. `POST /api/test/seed` 回傳 404（確認不可用）
7. 前端功能正常（報表、紀錄、Dashboard）

---

## 環境變數完整參考

| 變數 | 預設值 | Testing 建議 | Production 建議 | 說明 |
|------|--------|-------------|-----------------|------|
| `AT_AUTH_MODE` | `oauth2-proxy` | `none` | `oauth2-proxy` | 認證模式 |
| `AT_DATABASE_URL` | (空) | (空) = SQLite | 空或 MariaDB URL | 資料庫連線 |
| `AT_DATA_DIR` | `/data` | `/data` | `/data` | SQLite 資料目錄 |
| `AT_CONFIG_DIR` | `/app/config` | `/app/config` | `/app/config` | clusters.yaml 目錄 |
| `AT_POLLER_INTERVAL_HOURS` | `8` | `4` | `8` | 拉取間隔 |
| `AT_POLLER_LOOKBACK_HOURS` | `12` | `6` | `12` | 回溯窗口 |
| `AT_CORS_ORIGINS` | (空) | 不需設定 | `https://alert-tracker.example.com` | 逗號分隔的允許來源；Production 必須設定 |
| `AT_DISPLAY_TIMEZONE` | `Asia/Taipei` | `Asia/Taipei` | `Asia/Taipei` | IANA 時區，影響顯示與週報交接 |

> **刻意重疊設計：** interval=8h, lookback=12h → 相鄰拉取重疊 4h。用 fingerprint dedup 確保不重複，但不漏掉短暫 flapping alert。

---

## Testing vs Production 差異速查

| 面向 | Testing | Production |
|------|---------|------------|
| **認證** | `AT_AUTH_MODE=none`，無需 oauth2-proxy | `AT_AUTH_MODE=oauth2-proxy`，必須搭配 Ingress |
| **存取方式** | `kubectl port-forward` 或 NodePort | Ingress + TLS + oauth2-proxy |
| **Seed 端點** | `POST /api/test/seed` 可用 | 完全不可用（router 不註冊） |
| **安全** | Security context 建議啟用但可放寬 | 所有安全措施必須啟用 |
| **Poller 頻率** | 4h interval / 6h lookback（快速觀察） | 8h interval / 12h lookback（穩定） |
| **Cluster 來源** | Staging/testing cluster endpoints | Production cluster endpoints |
| **DB 備份** | 不需要 | 建議定期備份 PVC 或使用 MariaDB |
| **TLS** | 可選 | 必須 |
| **監控** | 可選 | 建議接入 Prometheus metrics |

---

## 常見操作

### 手動觸發 Poller

```bash
# 透過 API
curl -X POST http://localhost:8000/api/poller/trigger

# 查看 poller 狀態
curl http://localhost:8000/api/poller/status
```

### 查看 Pod Logs

```bash
kubectl logs -f deployment/sre-alert-tracker
# init-container logs (Alembic migration)
kubectl logs deployment/sre-alert-tracker -c db-migrate
```

### DB Migration

Init-container 會在每次 Pod 啟動時自動執行 `alembic upgrade head`。若需手動操作：

```bash
kubectl exec -it deployment/sre-alert-tracker -- python -m alembic current
kubectl exec -it deployment/sre-alert-tracker -- python -m alembic upgrade head
```

### 資料備份（SQLite）

```bash
# 複製 SQLite 檔案出來
kubectl cp sre-alert-tracker-<pod>:/data/alerts.db ./alerts-backup.db
```

### 手動 Purge 舊資料

```bash
curl -X POST http://localhost:8000/api/admin/purge
# 或透過前端 Settings 頁面
```

---

## Kustomize 建議結構（可選）

若需同時管理 testing 與 production 配置，建議使用 Kustomize overlay：

```
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── pvc.yaml
│   └── configmap.yaml
├── overlays/
│   ├── testing/
│   │   ├── kustomization.yaml
│   │   ├── configmap-patch.yaml      # staging cluster endpoints
│   │   └── deployment-patch.yaml     # AT_AUTH_MODE=none, interval=4h
│   └── production/
│       ├── kustomization.yaml
│       ├── configmap-patch.yaml      # production cluster endpoints
│       ├── ingress.yaml              # TLS + oauth2-proxy
│       └── secret-generator.yaml     # AT_DATABASE_URL 等
```

```bash
# Testing
kubectl apply -k k8s/overlays/testing/

# Production
kubectl apply -k k8s/overlays/production/
```

> 目前提供的 `k8s/` 目錄為 production 配置，可直接作為 Kustomize base 使用。

---

## 故障排查

| 症狀 | 可能原因 | 排查 |
|------|---------|------|
| Pod CrashLoopBackOff | Alembic migration 失敗 | `kubectl logs <pod> -c db-migrate` |
| 401 Unauthorized | oauth2-proxy 未正確注入 header | 確認 Ingress annotations、oauth2-proxy 部署 |
| Cluster status=unhealthy | Prometheus/Alertmanager 不可達 | 確認 cluster 間網路策略、Service DNS |
| 報表未自動生成 | 時區或 APScheduler 問題 | 查看 Pod logs 搜尋 "report_generator" |
| Poller 拉取為空 | Filter rules 過濾太嚴 | `GET /api/filters` 確認規則、暫時清空測試 |
| SQLite locked | 多 replica 同時寫入 | 確認 `replicas: 1` + Recreate strategy |
