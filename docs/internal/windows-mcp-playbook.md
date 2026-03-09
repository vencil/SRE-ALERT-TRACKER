# Windows MCP + Cowork VM Playbook

> AI Agent 環境限制、工具選擇策略、已知陷阱。
> **相關文件：** [GitHub Release Playbook](github-release-playbook.md) | [Testing Playbook](testing-playbook.md)

## 環境概覽

| 元件 | Cowork VM (Linux) | Windows MCP |
|------|-------------------|-------------|
| Python / pip | ✅ 直接可用 | — |
| Node.js / npm | ✅ 直接可用 | — |
| Docker CLI | ✅（docker compose） | ✅ |
| git commit / tag | ✅ | ✅ (batch file) |
| git push | ✅ credential.helper store | ✅ batch file + git.exe |
| GitHub API | ⚠️ 可能被 sandbox 擋 | ✅ PowerShell |
| 瀏覽器操作 | ❌ | ✅ Chrome MCP |

## 核心原則

### Cowork VM 優先

大部分操作（Python tests、前端 build、docker compose、git commit/push）在 Cowork VM 直接跑。只有以下場景才需要 Windows MCP：

1. **GitHub REST API** — Cowork VM 可能被 sandbox proxy 擋
2. **瀏覽器操作** — Chrome MCP
3. **git push fallback** — 若 VM push 遇 403（搭配 `credential.helper store` 通常可行）

### docker exec stdout 為空

Windows MCP Shell 執行 `docker exec` 時，**stdout 被 PowerShell 吞掉**。唯一可靠做法：

```bash
# ✅ bash -c 內部重定向到 workspace
docker exec <container> bash -c "command > /workspace/_output.txt 2>&1"
# → 再用 Read tool 讀 _output.txt

# ❌ 以下全部不可靠
docker exec <container> kubectl get pods > output.txt   # PS 搶走重定向
docker exec <container> kubectl get pods -A              # stdout 為空
```

### Shell 選擇：用 cmd 不用 PowerShell

PowerShell 對 docker exec 有額外的編碼/引號問題。**Windows MCP Shell 指定 `shell: "cmd"` 可避免多數問題。**

### 複雜指令寫成獨立腳本

只要指令含引號嵌套、管道、JSON 處理、多步邏輯，一律：
1. 用 Write tool 寫 `.sh` 或 `.py` 腳本
2. `docker exec bash /path/to/script.sh`
3. 結果從重定向檔案讀取
4. 完成後清理暫存腳本

## 工具選擇策略

| 情境 | 推薦方式 | 原因 |
|------|---------|------|
| Python 測試 | Cowork VM：`TESTING=1 python -m pytest tests/ -x -q` | 最快，無 docker 開銷 |
| 前端 build | Cowork VM：`cd frontend && npm ci && npm run build` | 直接可用 |
| Docker Compose Lab | Cowork VM：`docker compose up -d` | Docker CLI 可用 |
| git commit / tag / push | Cowork VM：`credential.helper store` + PAT | 直連通常可行 |
| GitHub API / Release | 先試 VM → fallback Windows MCP PowerShell | sandbox 可能擋 API |
| 掛載路徑檔案刪除 | `allow_cowork_file_delete` 後 `rm -f`；或 `docker exec ... rm -f` | VM 預設無法 rm 掛載路徑 |

## Cowork VM 限制

**網路：** sandbox proxy 封鎖部分外部 API（`api.github.com`、`github.com` 下載）。pip / npm registry 正常。git push 搭配 `credential.helper store` + PAT 通常可行。

**檔案系統：** 掛載的 workspace 路徑（`/sessions/.../mnt/`）預設無法用 `rm` 刪除檔案。需透過 `allow_cowork_file_delete` 工具啟用權限，或用 `docker exec ... rm -f` 繞過。

**前端 build：** 若 workspace 的 `frontend/` 沒有 `node_modules`，需先 `npm ci`。

## PowerShell REST API（GitHub 等）

Windows MCP PowerShell 是 Cowork VM 無法直連的 API（如 `api.github.com`）的橋樑。

**JSON body 兩種可靠做法：**

```powershell
$headers = @{ "Authorization" = "token $token"; "Accept" = "application/vnd.github+json" }

# 方法 A：單行字串 — 適合短 body、純 ASCII
$b = '{"tag_name":"v1.0.0","name":"v1.0.0","body":"notes","draft":false}'
Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $b

# 方法 B：ConvertTo-Json + UTF8 Bytes — 適合長 body、CJK 字元
$payload = @{ tag_name = "v1.0.0"; name = "title"; body = $longText } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri $url -Method Post -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
# ⚠️ 必須用 UTF8.GetBytes()，否則 CJK 字元亂碼
```

### 長 Body 的 File Staging 模式

Windows MCP Shell 有 timeout 限制，inline 長 body 容易超時。用 Desktop Commander 寫暫存檔再讀入更可靠：

```powershell
# Step 1: Desktop Commander write_file 寫 body 到暫存路徑
# Step 2: PowerShell 讀檔 + API 呼叫
$bodyText = Get-Content "<TEMP_PATH>/release-body.txt" -Raw
$payload = @{ name = "title"; body = $bodyText } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri $url -Method Patch -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) `
    -ContentType "application/json; charset=utf-8"
# Step 3: 清理暫存
Remove-Item "<TEMP_PATH>/release-body.txt" -Force
```

## 長時間操作 (>60s)

Desktop Commander `start_process` 硬上限 **60 秒**（`timeout_ms` 參數無效）。超過的操作用背景腳本：

```bash
# Step 1: Write tool 寫腳本
#!/bin/bash
exec > /path/to/_result.txt 2>&1
# ... 操作 ...
echo "DONE"

# Step 2: 背景啟動（-d 只接腳本路徑）
docker exec -d <container> bash /path/to/script.sh

# Step 3: Cowork VM Bash tool 等待
sleep 120

# Step 4: Read tool 讀 _result.txt，確認結尾有 "DONE"
```

**注意：** `docker exec -d` 的 stdout 不返回 → 腳本開頭必須 `exec > file 2>&1`。

## 已知陷阱速查

| # | 陷阱 | 解法 |
|---|------|------|
| 1 | docker exec stdout 為空 | `bash -c` 內重定向至 workspace 檔案 |
| 2 | `bash -c "..."` 引號被拆解 | 寫成獨立 `.sh` / `.py` 腳本 |
| 3 | PowerShell 編碼亂碼 | MCP Shell 指定 `shell: "cmd"` |
| 4 | `docker exec -d bash -c "..."` 失敗 | `-d` 只接腳本路徑，腳本內 `exec > file 2>&1` |
| 5 | `start_process` 硬上限 60s | 寫腳本 → `docker exec -d` → sleep → 讀結果 |
| 6 | VM 無法刪除掛載路徑檔案 | `allow_cowork_file_delete` 啟用後 `rm -f`；或 `docker exec ... rm -f` |
| 7 | PowerShell JSON CJK 亂碼 | `ConvertTo-Json` + `UTF8.GetBytes()` + `charset=utf-8` |
| 8 | GitHub API 被 sandbox 擋 | 改走 Windows MCP PowerShell |
| 9 | VM `git push` 偶爾 403 | `credential.helper store` + PAT 通常可行；若 403 → Windows batch file + git.exe |
| 10 | Windows `git` 不在 PATH | 完整路徑 `"C:\Program Files\Git\cmd\git.exe"` |
| 11 | PowerShell 直接呼叫 git.exe 失敗 | 寫 .bat → Desktop Commander `start_process` (shell: cmd) |
| 12 | PowerShell `echo $obj.prop` 為空 | `Write-Host "$($obj.prop)"` 字串插值 |
| 13 | VM 首次 commit 無 user identity | `git config --global user.email/name` |
| 14 | PAT 缺 `Workflows` scope → push 被 reject | PAT 需含 Workflows: Read and write |
| 15 | Git lock files 阻擋操作 | `allow_cowork_file_delete` → `rm -f .git/*.lock`；或 Windows batch `del /f` |
| 16 | Windows MCP Shell 長 REST body timeout | Desktop Commander `write_file` 寫暫存檔 → PowerShell `Get-Content -Raw` 讀入 → 結束後刪暫存 |
| 17 | Release `already_exists` 422 | 先 GET `/releases/tags/<tag>` 取 `id`，再 PATCH `/releases/<id>` 更新 body |
