# GitHub 仓库创建和推送脚本
# 使用方法: .\setup_github.ps1

Write-Host "
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        OKX 量化平台 - GitHub 自动部署脚本                       ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
" -ForegroundColor Cyan

# Git 和 GitHub CLI 路径
$gitPath = "C:\Program Files\Git\cmd\git.exe"
$ghPath = "C:\Program Files\GitHub CLI\gh.exe"

Write-Host "[步骤 1/5] 检查工具..." -ForegroundColor Yellow
if (-not (Test-Path $gitPath)) {
    Write-Host "❌ 未找到 Git" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Git 已安装" -ForegroundColor Green

if (-not (Test-Path $ghPath)) {
    Write-Host "⚠️  GitHub CLI 未安装，将使用网页方式" -ForegroundColor Yellow
    $useGhCli = $false
} else {
    Write-Host "✅ GitHub CLI 已安装" -ForegroundColor Green
    $useGhCli = $true
}

Write-Host ""
Write-Host "[步骤 2/5] 检查 SSH 连接..." -ForegroundColor Yellow
$sshTest = & ssh -T git@github.com 2>&1
if ($sshTest -match "Hi (.+)!") {
    $username = $matches[1]
    Write-Host "✅ SSH 连接成功，用户: $username" -ForegroundColor Green
} else {
    Write-Host "❌ SSH 连接失败" -ForegroundColor Red
    Write-Host "请运行: ssh -T git@github.com 测试连接" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[步骤 3/5] 准备 Git 仓库..." -ForegroundColor Yellow
Set-Location $PSScriptRoot

# 检查是否已经是 Git 仓库
if (Test-Path ".git") {
    Write-Host "✅ Git 仓库已存在" -ForegroundColor Green
} else {
    Write-Host "初始化 Git 仓库..." -ForegroundColor Yellow
    & $gitPath init
    & $gitPath config user.name $username
    & $gitPath config user.email "$username@users.noreply.github.com"
    Write-Host "✅ Git 仓库初始化完成" -ForegroundColor Green
}

# 确保所有文件已提交
& $gitPath add .
$hasChanges = & $gitPath status --porcelain
if ($hasChanges) {
    Write-Host "提交更改..." -ForegroundColor Yellow
    & $gitPath commit -m "Update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "✅ 代码已提交" -ForegroundColor Green
} else {
    Write-Host "✅ 无更改需要提交" -ForegroundColor Green
}

Write-Host ""
Write-Host "[步骤 4/5] 创建 GitHub 仓库..." -ForegroundColor Yellow

$repoName = "okx-quant-platform"
$repoDesc = "OKX Multi-Strategy Quantitative Trading Platform - 期现套利、配对交易、做市策略、情绪分析"

if ($useGhCli) {
    # 使用 GitHub CLI
    Write-Host "使用 GitHub CLI 创建仓库..." -ForegroundColor Yellow
    
    # 检查是否已登录
    $authStatus = & $ghPath auth status 2>&1
    if ($authStatus -match "not logged in") {
        Write-Host "需要登录 GitHub CLI..." -ForegroundColor Yellow
        Write-Host "正在启动登录流程..." -ForegroundColor Yellow
        Start-Process $ghPath -ArgumentList "auth", "login"
        Write-Host "请在浏览器中完成登录，然后按任意键继续..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    
    # 创建仓库
    & $ghPath repo create $repoName --public --description $repoDesc --source . --remote origin --push
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 仓库创建并推送成功！" -ForegroundColor Green
    } else {
        Write-Host "❌ 仓库创建失败" -ForegroundColor Red
        Write-Host "尝试使用网页方式..." -ForegroundColor Yellow
        $useGhCli = $false
    }
}

if (-not $useGhCli) {
    # 使用网页方式
    Write-Host "使用网页方式创建仓库..." -ForegroundColor Yellow
    
    # 设置远程仓库
    $remoteUrl = "git@github.com:$username/$repoName.git"
    & $gitPath remote remove origin 2>$null
    & $gitPath remote add origin $remoteUrl
    
    Write-Host ""
    Write-Host "📋 请手动创建 GitHub 仓库:" -ForegroundColor Cyan
    Write-Host "   1. 访问: https://github.com/new" -ForegroundColor White
    Write-Host "   2. Repository name: $repoName" -ForegroundColor White
    Write-Host "   3. Description: $repoDesc" -ForegroundColor White
    Write-Host "   4. 选择 Public" -ForegroundColor White
    Write-Host "   5. ❌ 不要勾选 'Initialize this repository with a README'" -ForegroundColor White
    Write-Host "   6. 点击 'Create repository'" -ForegroundColor White
    
    Write-Host ""
    Write-Host "创建完成后，按任意键继续推送..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

Write-Host ""
Write-Host "[步骤 5/5] 推送代码到 GitHub..." -ForegroundColor Yellow

# 确保分支名为 main
& $gitPath branch -M main

# 推送
& $gitPath push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "║                    ✅ 部署成功！                                ║" -ForegroundColor Green
    Write-Host "║                                                                ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "🌐 项目地址: https://github.com/$username/$repoName" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📚 文档:" -ForegroundColor Yellow
    Write-Host "   - README.md - 项目说明" -ForegroundColor White
    Write-Host "   - 使用指南.md - 详细文档" -ForegroundColor White
    Write-Host ""
    Write-Host "🎉 祝贺！你的量化交易平台上 GitHub 了！" -ForegroundColor Green
} else {
    Write-Host "❌ 推送失败" -ForegroundColor Red
    Write-Host "请检查:" -ForegroundColor Red
    Write-Host "  1. GitHub 仓库是否已创建" -ForegroundColor Red
    Write-Host "  2. SSH 密钥是否正确" -ForegroundColor Red
    Write-Host "  3. 网络连接是否正常" -ForegroundColor Red
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
