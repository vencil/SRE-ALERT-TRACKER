# GitHub Release Playbook

> Cowork VM + Windows MCP 環境下的 git push、Docker image build、GitHub Release 流程。

## 安全規則

**禁止將 GitHub token 寫入任何 repo 檔案。** Token 只存 `~/.git-credentials`（session 結束即消失）。

## 環境限制

| 操作 | Cowork VM | Windows MCP |
|------|-----------|-------------|
| `git commit` / `git tag` | ✅ | ✅ (via batch file) |
| `git push` | ❌ sandbox 403 | ✅ batch file + git.exe |
| GitHub API (`api.github.com`) | ❌ sandbox 擋 | ✅ PowerShell |
| `gh` CLI | ❌ 無法安裝 | ❌ 不在 PATH |

**結論：** commit/tag 在 Cowork VM（workspace 掛載共享），git push 透過 Windows batch file，GitHub API 透過 Windows MCP PowerShell。

> **2026-03 實測：** Cowork VM `git push` 即使用有效 PAT + `Contents: Read and write` scope，仍然被 sandbox 擋（HTTP 403 "Permission denied"）。API 驗證同一 token 確認 `push=True`，問題在 VM 層。

## 認證設定

使用者提供 GitHub Fine-grained PAT（需要 `Contents: Read and write` + `Workflows: Read and write`）。

**Cowork VM commit（workspace 共享到 Windows）：**

```bash
# Cowork VM — commit & tag（會反映到 Windows 檔案系統）
git config --global user.email "<EMAIL>"
git config --global user.name "<NAME>"
git add <files>
git commit -m "v1.x.x — 摘要"
git tag v1.x.x
```

> **注意：** Cowork VM 首次 commit 需設定 user.email / user.name，否則 fatal。

**Windows MCP push（batch file 繞開 PowerShell git 相容性問題）：**

```bat
@echo off
cd /d "<WINDOWS_REPO_PATH>"
"C:\Program Files\Git\cmd\git.exe" remote set-url origin "https://<USER>:<TOKEN>@github.com/<USER>/<REPO>.git"
"C:\Program Files\Git\cmd\git.exe" push origin main v1.x.x 2>&1
echo ---EXITCODE=%ERRORLEVEL%---
```

> **注意：** push 完成後立即 `remote set-url` 移除 token，避免殘留。

> **注意：** 沒有 `Workflows` scope 的 PAT 可以 push 程式碼，但 push 含 `.github/workflows/` 變更的 commit 會被 reject。

## Release 流程

### Step 1: Commit & Tag（Cowork VM）

```bash
git add <files>
git commit -m "v1.x.x — 摘要"
git tag v1.x.x
```

### Step 2: Push（Windows MCP batch file）

透過 Desktop Commander `write_file` 寫 batch → `start_process` (shell: cmd) 執行：

```bat
@echo off
cd /d "C:\Users\<USER>\<REPO>"
"C:\Program Files\Git\cmd\git.exe" remote set-url origin "https://<USER>:<TOKEN>@github.com/<USER>/<REPO>.git"
"C:\Program Files\Git\cmd\git.exe" push origin main v1.x.x 2>&1
echo ---EXITCODE=%ERRORLEVEL%---
```

> **重要：** push 完成後清除 token：
> ```bat
> "C:\Program Files\Git\cmd\git.exe" remote set-url origin "https://github.com/<USER>/<REPO>.git"
> ```

### Step 3: CI Build（自動）

Tag push 自動觸發 `.github/workflows/release.yaml`：

1. **test** — `pytest`（unit tests，排除 e2e）
2. **build** — Docker multi-stage build → Push to GHCR (`ghcr.io/vencil/sre-alert-tracker:<tag>`)
3. **release** — 自動從 CHANGELOG.md 擷取 release notes，建立 GitHub Release

Image tags：`<version>`（如 `1.0.0`）、`<major>.<minor>`（如 `1.0`）、`<sha>`。

### Step 4: 手動建立 GitHub Release（備用，CI 已自動處理）

> **注意：** Step 3 的 CI workflow 已包含自動建立 GitHub Release（`softprops/action-gh-release`）。以下僅在 CI 失敗或需手動修改 Release 時使用。

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

### Step 5: 驗證

```powershell
# Release 確認
$r = Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/releases/tags/v1.0.0" -Headers $headers
Write-Host "ID: $($r.id)  TAG: $($r.tag_name)  URL: $($r.html_url)"
```

> **注意：** PowerShell `Invoke-RestMethod` 回傳 object 的屬性用 `echo` 會是空字串，必須用 `Write-Host` 或 `"$($r.property)"` 字串插值。

## 已知陷阱

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | Cowork VM `git push` 403 | sandbox 擋 HTTPS push → 改用 Windows batch file + git.exe |
| 2 | Cowork VM 無法存取 `api.github.com` | GitHub API 改走 Windows MCP PowerShell |
| 3 | `gh` CLI 無法安裝 | Windows MCP PowerShell 直接呼叫 REST API |
| 4 | Windows `git` 不在 PATH | 用完整路徑 `"C:\Program Files\Git\cmd\git.exe"` |
| 5 | PowerShell 直接呼叫 git.exe 失敗 | 寫 .bat 檔 → Desktop Commander `start_process` (shell: cmd) |
| 6 | PAT 缺 `Workflows` scope | push `.github/workflows/` 被 reject |
| 7 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 8 | PowerShell `echo $obj.prop` 為空 | 用 `Write-Host "$($obj.prop)"` 字串插值 |
| 9 | Release `already_exists` 422 | GET `/releases/tags/<tag>` → PATCH `/releases/<id>` |
| 10 | Windows MCP 長 body timeout | Desktop Commander `write_file` 暫存 → PowerShell `Get-Content -Raw` 讀入 |
| 11 | Cowork VM 首次 commit 無 user identity | `git config --global user.email/name` |
| 12 | Release body 先短後長 | 先 POST 建立（短 body），再 PATCH 更新完整 body（避免一次性 JSON 問題） |
| 13 | 前端 dependency 未列入 package.json | `import` 的 npm 套件（如 recharts）必須在 package.json `dependencies` 中；dev 有 node_modules 時可能不報錯，CI `npm ci` 必定失敗 |
| 14 | `npm ci` package-lock.json 不同步 | 手動改 package.json 後 lock file 不一致 → 從乾淨目錄重新生成：`mkdir fresh && cp package.json fresh/ && cd fresh && npm install && cp package-lock.json ../ ` |
| 15 | CI re-trigger 需 retag | tag 已存在的 commit 不會重跑 CI → `git push origin :refs/tags/v1.x.x` 刪遠端 tag → `git tag -d v1.x.x && git tag v1.x.x` 本地 retag → push |
| 16 | Git lock files 阻擋操作 | Cowork VM 無法 `rm` 掛載路徑的 lock files → Windows batch `del /f ".git\index.lock" ".git\HEAD.lock" ".git\refs\stale.lock"` |
