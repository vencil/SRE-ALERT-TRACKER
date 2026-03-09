# Windows MCP + Cowork VM Playbook

> AI Agent 環境限制、工具選擇策略、已知陷阱。

## 環境概覽

| 元件 | Cowork VM (Linux) | Windows MCP |
|------|-------------------|-------------|
| Python / pip | ✅ 直接可用 | — |
| Node.js / npm | ✅ 直接可用 | — |
| Docker CLI | ✅（docker compose） | ✅ |
| git commit / tag | ✅ | ✅ (batch file) |
| git push | ❌ sandbox 403 | ✅ batch file + git.exe |
| GitHub API | ❌ sandbox 擋 | ✅ PowerShell |
| 瀏覽器操作 | ❌ | ✅ Chrome MCP |

## 工具選擇策略

| 情境 | 推薦方式 |
|------|---------|
| Python 測試 | Cowork VM：`TESTING=1 python -m pytest tests/ -x -q` |
| 前端 build | Cowork VM：`cd frontend && npm ci && npm run build` |
| Docker build | Cowork VM：`docker build -t alert-tracker .` |
| Docker Compose Lab | Cowork VM：`docker compose up -d` |
| git commit / tag | Cowork VM：workspace 掛載共享到 Windows |
| git push | Windows MCP：batch file + `"C:\Program Files\Git\cmd\git.exe"` |
| GitHub API / Release | Windows MCP：PowerShell `Invoke-RestMethod` |
| 掛載路徑檔案刪除 | `docker exec ... rm -f`（VM 無法直接 rm） |

## Cowork VM 限制

**網路：** sandbox proxy 封鎖部分外部 API（`api.github.com`、`github.com` 下載）以及 `git push`（HTTPS 403）。pip / npm registry 正常。

**檔案系統：** 掛載的 workspace 路徑（`/sessions/.../mnt/`）無法用 `rm` 刪除檔案。替代方案：清空檔案內容，或透過 docker exec 刪除。

**前端 build：** 若 workspace 的 `frontend/` 沒有 `node_modules`，需先 `npm ci`，或在工作目錄 `/sessions/<session>/work/frontend/` 建好環境後 build，再把 `dist/` 複製回 `backend/static/`。

## Windows MCP Shell 注意事項

**docker exec stdout 為空：** Windows MCP PowerShell 下 `docker exec` 的 stdout 常被吞掉。可靠做法：

```bash
# bash -c 內部重定向到 workspace
docker exec <container> bash -c "command > /workspace/_output.txt 2>&1"
# 再用 Read tool 讀 _output.txt
```

**shell 選擇：** docker exec 在 PowerShell 下有引號問題。指定 `shell: "cmd"` 可避免。

**長時間操作（>60s）：** Desktop Commander `start_process` 有硬上限。用 `docker exec -d` 背景執行 + 腳本內 `exec > file 2>&1` 重定向。

**PowerShell REST API：**

```powershell
$headers = @{ "Authorization" = "token $token"; "Accept" = "application/vnd.github+json" }

# 短 body
Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body '{"key":"value"}'

# 長 body / CJK
$payload = @{ key = "值" } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri $url -Method Post -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
```

## 已知陷阱速查

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | docker exec stdout 為空 | `bash -c` 內重定向至檔案 |
| 2 | `bash -c "..."` 引號被拆解 | 寫成獨立 `.sh` 腳本 |
| 3 | PowerShell 編碼亂碼 | MCP Shell 指定 `shell: "cmd"` |
| 4 | `start_process` 硬上限 60s | 寫腳本 → `docker exec -d` → sleep → 讀結果 |
| 5 | VM 無法刪除掛載路徑檔案 | `docker exec ... rm -f` 或清空內容 |
| 6 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 7 | GitHub API 被 sandbox 擋 | 改走 Windows MCP PowerShell |
| 8 | VM `git push` 403 | sandbox 擋 HTTPS push → Windows batch file + git.exe |
| 9 | Windows `git` 不在 PATH | 完整路徑 `"C:\Program Files\Git\cmd\git.exe"` |
| 10 | PowerShell 直接呼叫 git.exe 失敗 | 寫 .bat → Desktop Commander `start_process` (shell: cmd) |
| 11 | PowerShell `echo $obj.prop` 為空 | `Write-Host "$($obj.prop)"` 字串插值 |
| 12 | VM 首次 commit 無 user identity | `git config --global user.email/name` |
