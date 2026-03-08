# GitHub Release Playbook

> Cowork VM + Windows MCP 環境下的 git push、Docker image build、GitHub Release 流程。

## 安全規則

**禁止將 GitHub token 寫入任何 repo 檔案。** Token 只存 `~/.git-credentials`（session 結束即消失）。

## 環境限制

| 操作 | Cowork VM | Windows MCP |
|------|-----------|-------------|
| `git push` / `git tag` | ✅ HTTPS 直連 | — |
| GitHub API (`api.github.com`) | ❌ sandbox 擋 | ✅ PowerShell |
| `gh` CLI | ❌ 無法安裝 | ✅ 可用 |

**結論：** git 操作在 Cowork VM，GitHub API 操作透過 Windows MCP。

## 認證設定（Cowork VM）

使用者提供 GitHub Fine-grained PAT（需要 `Contents: Read and write` + `Workflows: Read and write`）：

```bash
git config --global credential.helper store
echo "https://<USERNAME>:<TOKEN>@github.com" > ~/.git-credentials
# 驗證
git push --dry-run origin main
```

> **注意：** 沒有 `Workflows` scope 的 PAT 可以 push 程式碼，但 push 含 `.github/workflows/` 變更的 commit 會被 reject。

## Release 流程

### Step 1: Commit & Push（Cowork VM）

```bash
git add <files>
git commit -m "v1.x.x — 摘要"
git tag v1.x.x
git push origin main v1.x.x
```

### Step 2: CI Build（自動）

Tag push 觸發 GitHub Actions workflow（`release.yaml`）：
- Build Docker image（multi-stage: Node frontend → Python backend）
- Push to GitHub Container Registry（`ghcr.io/vencil/sre-alert-tracker:<tag>`）
- 建立 GitHub Release（Draft 或 auto-publish）

> **CI workflow 尚未建立。** 建立時需包含：
> - trigger: `push tags: ['v*']`
> - jobs: build + push Docker image to GHCR
> - 可選: 自動建立 GitHub Release

### Step 3: 手動建立 GitHub Release（Windows MCP，若 CI 未設定）

```powershell
$token = "<TOKEN>"
$headers = @{ "Authorization" = "token $token"; "Accept" = "application/vnd.github+json" }
$url = "https://api.github.com/repos/vencil/sre-alert-tracker/releases"

# 短 body — 單行 JSON
$b = '{"tag_name":"v1.0.0","name":"v1.0.0","body":"Initial release","draft":false,"prerelease":false}'
Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $b

# 長 body / CJK — ConvertTo-Json + UTF8
$payload = @{
    tag_name = "v1.0.0"
    name = "v1.0.0 — SRE Alert Tracker"
    body = $bodyText
    draft = $false
    prerelease = $false
} | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri $url -Method Post -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
```

> **CJK 必須** 用 `UTF8.GetBytes()` + `charset=utf-8`，否則亂碼。

### Step 4: 驗證

```powershell
# CI 狀態
Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/sre-alert-tracker/actions/runs?per_page=3" -Headers $headers

# Release 確認
Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/sre-alert-tracker/releases/latest" -Headers $headers
```

## 已知陷阱

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | Cowork VM 無法存取 `api.github.com` | GitHub API 改走 Windows MCP |
| 2 | `gh` CLI 無法安裝 | Windows MCP PowerShell 直接呼叫 REST API |
| 3 | PAT 缺 `Workflows` scope | push `.github/workflows/` 被 reject |
| 4 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 5 | Release `already_exists` 422 | GET `/releases/tags/<tag>` → PATCH `/releases/<id>` |
| 6 | Windows MCP 長 body timeout | Desktop Commander `write_file` 暫存 → PowerShell `Get-Content -Raw` 讀入 |
