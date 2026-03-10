# Windows MCP + Cowork VM — 操作手冊 (Playbook)

> AI Agent 環境限制、工具選擇策略、已知陷阱。
> **相關文件：** [GitHub Release Playbook](github-release-playbook.md) | [Testing Playbook](testing-playbook.md)

## 環境分工

| 操作 | Cowork VM (Linux) | Windows MCP |
|------|-------------------|-------------|
| Python / pip / pytest | ✅ | — |
| Node.js / npm | ⚠️ 可能 OOM | ✅ 完整路徑（見下方） |
| Docker CLI | ✅ | ✅ |
| git commit / tag | ✅ | — |
| git push | ✅ credential.helper store | ✅ 完整路徑（備用） |
| GitHub REST API | ❌ sandbox 擋 | ✅ PowerShell |
| 瀏覽器操作 | ❌ | ✅ Chrome MCP |

**核心原則：** Cowork VM 做所有開發操作，Windows MCP 只用於 VM 做不到的事（GitHub API、瀏覽器）。

## Cowork VM 限制

**網路：** sandbox proxy 封鎖 `api.github.com` 等外部 API。pip / npm registry 正常。`git push` 搭配 `credential.helper store` + PAT 可行。

**檔案刪除：** 掛載路徑（`/sessions/.../mnt/`）預設無法 `rm` 刪除。需 `allow_cowork_file_delete` 啟用權限。常見場景：`.git/*.lock` 殘留檔案。

**前端 build：** 若 `frontend/` 沒有 `node_modules`，需先 `npm ci`。

**npm OOM：** VM 記憶體有限，大型 `npm ci` 或 `npm run build` 可能 OOM killed。改用 Windows MCP：

```powershell
# Windows MCP — npm 需要完整路徑（不在 PowerShell 預設 PATH）
$node = "C:\PROGRA~1\nodejs\node.exe"
$npm  = "C:\PROGRA~1\nodejs\node_modules\npm\bin\npm-cli.js"

Set-Location C:\Users\vencs\SRE-ALERT-TRACKER\frontend
& $node $npm ci 2>&1
& $node $npm run build 2>&1
```

## Windows MCP — Git 操作

PowerShell 新 session 不一定繼承 Git PATH。始終使用完整路徑 + call operator `&`：

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
Set-Location C:\Users\vencs\SRE-ALERT-TRACKER

# push branch + tag
& $git push origin main v1.2.0 2>&1

# 檢查 log
& $git log --oneline -5 2>&1
```

> **注意：** PowerShell 不支援 `&&`（bash 語法），用 `;` 分號串接指令。

## Windows MCP PowerShell — GitHub API

Windows MCP 是存取 `api.github.com` 的唯一途徑。主要用途：

1. **CI 監控** — 查詢 workflow run 狀態、讀取失敗 job log
2. **Release 管理** — 建立或更新 GitHub Release（正常由 CI 自動完成，此為備用）
3. **Release 驗證** — 確認 Release 和 image 正確發布

**JSON body 處理：**

```powershell
$headers = @{ "Authorization" = "token $token"; "Accept" = "application/vnd.github+json" }

# 短 body / ASCII — 單行字串
$b = '{"tag_name":"v1.0.0","name":"v1.0.0","body":"notes","draft":false}'
Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $b

# 長 body / CJK — ConvertTo-Json + UTF8 Bytes（必須）
$payload = @{ tag_name = "v1.0.0"; body = $longText } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri $url -Method Post -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
```

> **CJK 必須** 用 `UTF8.GetBytes()` + `charset=utf-8`，否則亂碼。

**長 body timeout** — Windows MCP Shell 有 timeout 限制。用 Desktop Commander `write_file` 寫暫存檔 → PowerShell `Get-Content -Raw` 讀入 → 結束後 `Remove-Item`。

## 已知陷阱

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | GitHub API 被 sandbox 擋 | 改走 Windows MCP PowerShell |
| 2 | VM 無法刪除掛載路徑檔案 | `allow_cowork_file_delete` → `rm -f` |
| 3 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 4 | PowerShell `echo $obj.prop` 為空 | `"$($obj.prop)"` 字串插值 |
| 5 | Windows MCP Shell 長 body timeout | 暫存檔模式：write_file → Get-Content -Raw → Remove-Item |
| 6 | docker exec stdout 被 PowerShell 吞掉 | `bash -c "command > /workspace/_output.txt 2>&1"` 內部重定向 |
| 7 | `bash -c "..."` 引號被拆解 | 寫成獨立 `.sh` 腳本 → `docker exec bash /path/to/script.sh` |
| 8 | Windows `git` 不在 PowerShell PATH | `& 'C:\Program Files\Git\cmd\git.exe'`（call operator + 完整路徑） |
| 9 | Git lock files 阻擋操作 | `allow_cowork_file_delete` → `rm -f .git/*.lock` |
| 10 | PowerShell `&&` 語法錯誤 | PowerShell 不支援 `&&`，改用 `;`（分號）串接 |
| 11 | npm / node 不在 PowerShell PATH | `C:\PROGRA~1\nodejs\node.exe` + `...\npm-cli.js` 完整路徑 |
| 12 | VM npm ci / build OOM killed | 改走 Windows MCP 跑 npm（Windows 記憶體充裕） |
| 13 | `where.exe git` 回空但 git 確實存在 | PowerShell session PATH 不完整，用 `Get-ChildItem` 確認完整路徑後直接用 |
