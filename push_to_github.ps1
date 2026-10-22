# 一键推送到 GitHub (Windows)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "OKX 量化交易平台 - 推送到 GitHub" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Git 路径
$gitPath = "C:\Program Files\Git\cmd\git.exe"

# 检查 Git
if (-not (Test-Path $gitPath)) {
    Write-Host "[错误] 未找到 Git，请先安装 Git" -ForegroundColor Red
    exit 1
}

# 进入脚本所在目录
Set-Location $PSScriptRoot

Write-Host "[1/4] 检查 Git 状态..." -ForegroundColor Yellow
& $gitPath status

Write-Host ""
Write-Host "[2/4] 添加所有文件..." -ForegroundColor Yellow
& $gitPath add .

Write-Host ""
Write-Host "[3/4] 提交更改..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
& $gitPath commit -m "Update: $timestamp"

Write-Host ""
Write-Host "[4/4] 推送到 GitHub..." -ForegroundColor Yellow
& $gitPath push -u origin main

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "推送完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "项目地址: https://github.com/F-Sheng/okx-quant-platform" -ForegroundColor Cyan
Write-Host ""

# 检查推送结果
if ($LASTEXITCODE -eq 0) {
    Write-Host "[成功] 代码已推送到 GitHub！" -ForegroundColor Green
} else {
    Write-Host "[失败] 推送失败，请检查：" -ForegroundColor Red
    Write-Host "  1. 是否已在 GitHub 创建仓库: okx-quant-platform" -ForegroundColor Red
    Write-Host "  2. SSH 密钥是否配置正确" -ForegroundColor Red
    Write-Host "  3. 网络连接是否正常" -ForegroundColor Red
    Write-Host "  4. 是否有推送权限" -ForegroundColor Red
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
