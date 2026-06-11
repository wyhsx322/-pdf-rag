# 一键启动前后端（前后端分离）
# 用法：在项目根目录执行 .\start.ps1

$Root = $PSScriptRoot
$Venv = "$Root\.venv\Scripts\python.exe"
$Frontend = "$Root\frontend"

Write-Host "=== 启动后端 (FastAPI @ http://localhost:8000) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$Venv' -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000" -WorkingDirectory $Root

Start-Sleep -Seconds 2

Write-Host "=== 启动前端 (Vite @ http://localhost:5173) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev" -WorkingDirectory $Frontend

Write-Host ""
Write-Host "两个窗口已打开：" -ForegroundColor Green
Write-Host "  后端：http://localhost:8000      (API 文档：http://localhost:8000/docs)" -ForegroundColor Green
Write-Host "  前端：http://localhost:5173" -ForegroundColor Green
