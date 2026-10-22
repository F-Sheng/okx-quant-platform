#!/bin/bash
# 一键推送到 GitHub

echo "=========================================="
echo "OKX 量化交易平台 - 推送到 GitHub"
echo "=========================================="
echo ""

# 检查 Git
if ! command -v git &> /dev/null; then
    echo "[错误] 未找到 Git，请先安装 Git"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")"

echo "[1/3] 检查 Git 状态..."
git status

echo ""
echo "[2/3] 提交更改..."
git add .
git commit -m "Update: $(date '+%Y-%m-%d %H:%M:%S')"

echo ""
echo "[3/3] 推送到 GitHub..."
git push -u origin main

echo ""
echo "=========================================="
echo "推送完成！"
echo "=========================================="
echo ""
echo "项目地址: https://github.com/F-Sheng/okx-quant-platform"
echo ""
echo "如果推送失败，请确保："
echo "1. 已在 GitHub 创建仓库: okx-quant-platform"
echo "2. SSH 密钥已配置"
echo "3. 网络连接正常"
echo ""
