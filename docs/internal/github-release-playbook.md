# GitHub Release — 操作手冊 (Playbook)

> AI Agent 透過 Cowork VM + Windows MCP 執行 git push、CI build、GitHub Release 的流程。
> **相關文件：** [Windows-MCP Playbook](windows-mcp-playbook.md) | [Testing Playbook](testing-playbook.md)

## 安全規則

**絕對禁止將 GitHub token 寫入任何 repo 檔案。** Token 只能存在 VM 的 `~/.git-credentials`（session 結束即消失），操作完成後 `rm -f ~/.git-credentials` 清除。

## 環境分工

| 操作 | Cowork VM | Windows MCP |
|------|-----------|-------------|
| git commit / tag / push | ✅ credential.helper store | 備用 |
| GitHub REST API | ❌ sandbox 擋 `api.github.com` | ✅ PowerShell `Invoke-RestMethod` |
| CI 狀態查詢 | ❌ | ✅ PowerShell |

**結論：** git 操作在 Cowork VM 做，GitHub API（Release 建立、CI 監控）透過 Windows MCP。

## 認證設定（Cowork VM）

Fine-grained PAT 需要 permissions：**Contents** (R/W) + **Metadata** (R) + **Workflows** (R/W)。

> **缺 Workflows scope** 會導致 push 含 `.github/workflows/` 變更的 commit 被 reject。

```bash
git config --global credential.helper store
echo "https://<USERNAME>:<TOKEN>@github.com" > ~/.git-credentials

# 驗證
git push --dry-run origin main   # "Everything up-to-date"
```

## Release 標準流程

### Step 1: 確保 CI 依賴同步

> **Lesson Learned (v1.1.1)：** 本地 `pip install` 裝的套件不代表 CI 也有。新增測試依賴時，必須同步更新 `.github/workflows/release.yaml` 的 `pip install` 行。
>
> 例如：新增 `freezegun` 和 `pytest-asyncio` 用於測試，本地全過但 CI 因缺套件而失敗。

**檢查清單：**
```bash
# 比對本地 pip 與 CI install 行
grep "pip install" .github/workflows/release.yaml
# 確認 import 的測試套件都在 CI install 列表中
grep -rh "^import\|^from" tests/ | sort -u | head -20
```

### Step 2: 版號 Bump + Tag

> **Lesson Learned (v1.2.0)：** 大功能 release 要用「兩段式 commit」—— 先 commit 所有功能/修正/文件，再跑 `bump --tag` 建立乾淨的版號 commit。`--tag` 要求 clean working tree，不能跟功能改動混在一起。

```bash
# ─── 大版本 release 標準流程 ───

# 1. 更新 CHANGELOG.md：[Unreleased] → [v1.x.x] — 日期
# 2. Commit 所有功能 + 修正 + 文件改動
git add <all-changed-files>
git commit -m "feat: summary of all changes"

# 3. 版號 bump（working tree 必須 clean）
make version-check                                     # 確認舊版號一致
python scripts/bump_version.py --bump 1.x.x --tag     # bump → commit → tag

# ─── 或 patch release 簡化版 ───
python scripts/bump_version.py --bump patch --tag
```

bump script 自動同步：`VERSION` → `Dockerfile LABEL` → `README.md` → `CLAUDE.md` → `docs/architecture-design.md`。

### Step 3: Push

```bash
# Cowork VM（首選，credential.helper store + PAT）
git push origin main v1.x.x

# Windows MCP（備用，VM push 失敗時）
# & 'C:\Program Files\Git\cmd\git.exe' push origin main v1.x.x 2>&1
```

### Step 4: CI 自動 Build + Release

Tag push 自動觸發 `.github/workflows/release.yaml`：

1. **test** — `pytest`（排除 e2e）
2. **build** — Docker image → `ghcr.io/vencil/sre-alert-tracker:{version,major.minor,sha}`
3. **release** — 從 CHANGELOG.md 擷取對應版號的 section → 建立 GitHub Release

### Step 5: 驗證（Windows MCP）

```powershell
$headers = @{
    "Authorization" = "token <TOKEN>"
    "Accept" = "application/vnd.github+json"
}

# CI 狀態
$r = Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/actions/runs?per_page=3" -Headers $headers
$r.workflow_runs | ForEach-Object { "$($_.name) | $($_.status) | $($_.conclusion)" }

# 失敗時看 job 細節
$runId = $r.workflow_runs[0].id
$jobs = Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/actions/runs/$runId/jobs" -Headers $headers
$jobs.jobs | ForEach-Object { "$($_.name) | $($_.conclusion)" }

# 看失敗 log（最後 30 行）
$jobId = ($jobs.jobs | Where-Object { $_.conclusion -eq "failure" }).id
$logs = Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/actions/jobs/$jobId/logs" -Headers $headers
($logs -split "`n")[-30..-1] -join "`n"

# Release 確認
$rel = Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/releases/latest" -Headers $headers
"Tag: $($rel.tag_name) | URL: $($rel.html_url)"
```

## CI 失敗 → Retag 重觸發

CI 失敗後修復 → 需要 retag 才能重新觸發（同名 tag 的 commit 不會重跑 CI）：

```bash
# 1. 修復問題 + commit
git add <files> && git commit -m "fix: ..."

# 2. 本地刪除舊 tag，建立新 tag
git tag -d v1.x.x
git tag -a v1.x.x -m "Release v1.x.x"

# 3. Push commit + 刪遠端舊 tag + push 新 tag
git push origin main
git push origin :refs/tags/v1.x.x
git push origin v1.x.x
```

## 手動建立 Release（備用）

> 正常情況下 CI 會自動建立 Release。以下僅在 CI release job 失敗時使用。

```powershell
# 透過 Windows MCP PowerShell
$payload = @{
    tag_name = "v1.x.x"
    name = "v1.x.x — SRE Alert Tracking System"
    body = $bodyText
    draft = $false
    prerelease = $false
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://api.github.com/repos/vencil/SRE-ALERT-TRACKER/releases" `
    -Method Post -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
```

> **CJK 字元** 必須用 `UTF8.GetBytes()` + `charset=utf-8`，否則亂碼。

**Release 已存在（422）** → 先 GET 取 id，再 PATCH：

```powershell
$r = Invoke-RestMethod -Uri ".../releases/tags/v1.x.x" -Headers $headers
Invoke-RestMethod -Uri ".../releases/$($r.id)" -Method Patch -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($update)) `
    -ContentType "application/json; charset=utf-8"
```

## 大版本 Release Checklist (v1.2.0 經驗)

適用於跨多 session 累積的大功能 release：

```
□ 功能開發完成 + 單元測試全過 (make test)
□ 前端 lint 無錯誤 (npm run lint via Windows MCP)
□ 前端 build 成功 (npm run build via Windows MCP)
□ 多 Agent review (backend / frontend / tests / docs+security)
□ Review 修正分波執行 (P0 → P1 → P2)，每波跑 test + lint
□ CHANGELOG.md [Unreleased] → [v1.x.x] — 日期
□ 文件一致性：CLAUDE.md / README / architecture / deployment-guide
   - 計數核對：routers、services、models、components、test files、passed count
   - 環境變數表完整（新增的 AT_* 都有列）
   - API endpoint 表完整
□ Commit 所有功能改動（一個乾淨的 feature commit）
□ bump_version.py --bump X.Y.Z --tag（clean tree 上執行）
□ version-check 全 OK
□ git push origin main vX.Y.Z
□ CI workflow 跑過（test → build → release）
□ 驗證 GitHub Release 存在 + GHCR image 可拉
□ Playbooks 更新 lesson learned
```

## 已知陷阱

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | CI 缺測試依賴（本地過、CI 掛） | 新增 pip 套件同步更新 `release.yaml` 的 `pip install` 行 |
| 2 | Cowork VM 無法存取 `api.github.com` | GitHub API 改走 Windows MCP PowerShell |
| 3 | `gh` CLI 無法安裝 | 用 Windows MCP PowerShell REST API |
| 4 | PAT 缺 `Workflows` scope | push `.github/workflows/` 被 reject，PAT 需含 Workflows R/W |
| 5 | CI 不重跑（同 tag 同 commit） | 修復後 retag（見上方 retag 流程） |
| 6 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 7 | PowerShell `echo $obj.prop` 為空 | 用 `"$($obj.prop)"` 字串插值 |
| 8 | Release `already_exists` 422 | GET `/releases/tags/<tag>` 取 id → PATCH 更新 |
| 9 | Git lock files 阻擋操作 | `allow_cowork_file_delete` → `rm -f .git/*.lock` |
| 10 | Token 洩漏到 repo | **嚴格禁止** — 只存 `~/.git-credentials`，操作後 `rm -f` 清除 |
| 11 | `bump_version.py --tag` 要求 clean tree | 所有變更先 commit，再跑 bump --tag |
| 12 | Windows MCP Shell 長 body timeout | Desktop Commander `write_file` 暫存 → PowerShell `Get-Content -Raw` 讀入 |
