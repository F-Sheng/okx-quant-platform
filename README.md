# OKX 多策略量化交易平台

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)](#)

> 🚀 一个基于 OKX 交易所的多策略量化交易平台，支持期现套利、配对交易、做市策略和情绪分析。

## 📖 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [详细文档](#详细文档)
- [策略说明](#策略说明)
- [API 配置](#api-配置)
- [风险提示](#风险提示)
- [贡献指南](#贡献指南)

---

## 🎯 项目简介

本平台是一个专业的加密货币量化交易系统，集成了四大主流策略：

1. **期现套利** - 资金费率套利，低风险稳定收益
2. **配对交易** - 基于协整关系的统计套利
3. **做市策略** - 提供流动性，赚取价差
4. **情绪分析** - 基于 AI 的逆向交易

### ✨ 特点

- ✅ **模块化设计** - 策略、执行、风控独立
- ✅ **完整回测** - 历史数据验证策略有效性
- ✅ **风险管理** - 多层风控保护资金安全
- ✅ **SQLite 存储** - 交易数据持久化
- ✅ **详细文档** - 从入门到精通
- ✅ **模拟盘支持** - 先测试后实盘

---

## 🛠️ 核心功能

### 1️⃣ 期现套利（资金费率套利）

**原理**：利用永续合约的资金费率机制，通过现货+合约对冲获取稳定收益。

```
年化收益 = 资金费率 × 3次/天 × 365天

示例：
- 资金费率：0.01% (0.0001)
- 年化收益：0.0001 × 3 × 365 = 10.95%
```

**风险等级**：⭐ 低（市场中性）

---

### 2️⃣ 配对交易（统计套利）

**原理**：找到协整的资产对，当价差偏离均值时做多/做空，等待回归。

```
Z-score = (当前价差 - 均值) / 标准差

开仓信号：
- Z-score > 2.0：做空价差
- Z-score < -2.0：做多价差
- |Z-score| > 3.5：止损
```

**风险等级**：⭐⭐ 中等

---

### 3️⃣ 做市策略

**原理**：在买卖两侧挂单，提供流动性并赚取价差。

```
报价模型：
mid_price = (bid + ask) / 2
spread = mid_price × (spread_bps / 10000)

bid_price = mid_price - spread/2
ask_price = mid_price + spread/2
```

**风险等级**：⭐⭐ 中等（需要库存管理）

---

### 4️⃣ 情绪分析交易

**原理**：使用 DeepSeek AI 分析新闻/社交媒体情绪，极度恐慌/贪婪时逆向交易。

```
情绪分数：-1.0 到 +1.0
- -1.0：极度恐慌 → 买入
-  0.0：中性 → 观望
- +1.0：极度贪婪 → 卖出
```

**风险等级**：⭐⭐⭐ 较高（依赖数据质量）

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 8GB+ 内存
- 稳定的网络连接（或 VPN/代理）

### 安装步骤

```bash
# 1. 克隆项目
git clone git@github.com:F-Sheng/okx-quant-platform.git
cd okx-quant-platform

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API
# 编辑 config/settings.yaml，填入你的 OKX API 信息

# 4. 测试系统
python test_system.py

# 5. 本地测试（不需要 API）
python test_local.py

# 6. 启动交易
python main.py
```

---

## 📚 详细文档

| 文档 | 说明 |
|------|------|
| [使用指南.md](使用指南.md) | 详细使用文档、配置说明 |
| [README.md](README.md) | 项目概览、快速开始 |
| [LICENSE](LICENSE) | MIT 开源协议 |

---

## 📈 策略说明

### 策略对比

| 策略 | 预期年化 | 最大回撤 | 复杂度 | 适合场景 |
|------|---------|---------|--------|---------|
| 期现套利 | 15-30% | 5-10% | ⭐ | 稳健投资 |
| 配对交易 | 10-20% | 10-20% | ⭐⭐ | 市场中性 |
| 做市策略 | 20-50% | 15-25% | ⭐⭐⭐ | 高流动性市场 |
| 情绪分析 | 不确定 | 20-40% | ⭐⭐⭐⭐ | 高波动市场 |

### 推荐配置

**保守型**（新手推荐）：
```yaml
basis_arbitrage:
  enabled: true
  max_position_usd: 5000

pair_trading:
  enabled: true
  max_position_usd: 3000

market_making:
  enabled: false

sentiment:
  enabled: false
```

**激进型**（有经验）：
```yaml
basis_arbitrage:
  enabled: true
  max_position_usd: 10000

pair_trading:
  enabled: true
  max_position_usd: 8000

market_making:
  enabled: true
  max_position_usd: 5000

sentiment:
  enabled: true
```

---

## 🔑 API 配置

### OKX API 设置

1. 登录 [OKX](https://www.okx.com/)
2. 进入 "API 管理"
3. 创建 API Key

**权限设置**：
- ✅ 读取（Read）
- ✅ 交易（Trade）
- ❌ 提币（Withdraw）← **不要开启！**

**安全建议**：
- ✅ 启用 IP 白名单
- ✅ 设置 API 过期时间
- ✅ 定期更换密钥

### 配置文件

编辑 `config/settings.yaml`：

```yaml
exchange:
  name: OKX
  trading_mode: demo  # demo=模拟盘, live=实盘
  api_key: "your_api_key"
  secret_key: "your_secret_key"
  passphrase: "your_passphrase"
```

---

## ⚠️ 风险提示

### 🔴 重要警告

1. **市场风险**：加密货币市场波动极大，可能导致本金损失
2. **技术风险**：程序 bug、网络故障、API 限制可能导致意外损失
3. **策略风险**：历史表现不代表未来收益，策略可能失效
4. **监管风险**：不同国家/地区对加密货币交易的监管不同

### 🛡️ 风险控制建议

1. **资金管理**
   - 初始测试：100-500 USDT
   - 单策略最大仓位：总资金的 20-30%
   - 设置止损：5-10%

2. **测试优先**
   - ✅ 先用模拟盘测试 1-2 周
   - ✅ 验证策略稳定性
   - ✅ 小资金实盘测试
   - ✅ 逐步增加资金

3. **监控告警**
   - 查看日志：`logs/quant.log`
   - 监控回撤：> 15% 暂停交易
   - 定期复盘：每周分析绩效

---

## 📁 项目结构

```
okx-quant-platform/
├── config/                      # 配置模块
│   ├── settings.yaml           # 策略配置
│   └── okx_config.py           # 配置加载器
├── data/                        # 数据模块
│   ├── database.py             # SQLite 数据库
│   └── sentiment/              # 情绪数据
├── strategies/                  # 策略模块
│   ├── base_strategy.py        # 策略基类
│   ├── basis_arbitrage/        # 期现套利
│   │   └── funding_arb.py     # 资金费率套利
│   ├── pair_trading/           # 配对交易
│   │   └── pair_trading.py    # 协整套利
│   ├── market_making/          # 做市策略
│   │   └── basic_mm.py        # 基础做市
│   └── sentiment/              # 情绪分析
│       └── sentiment_arb.py   # 情绪交易
├── execution/                   # 执行模块
│   └── okx_client.py           # OKX API 客户端
├── backtest/                    # 回测模块
│   └── engine.py               # 回测引擎
├── analysis/                    # 分析模块
│   └── metrics.py              # 绩效分析
├── logs/                        # 日志文件
├── main.py                      # 主程序
├── test_system.py               # 系统测试
├── test_local.py                # 本地测试（模拟数据）
├── test_api.py                  # API 连接测试
├── requirements.txt             # 依赖列表
├── README.md                    # 项目说明
├── 使用指南.md                   # 详细文档
└── LICENSE                      # 开源协议
```

---

## 🔧 开发

### 运行测试

```bash
# 测试系统模块
python test_system.py

# 测试 API 连接
python test_api.py

# 本地测试（模拟数据）
python test_local.py
```

### 添加新策略

1. 创建策略文件 `strategies/your_strategy.py`
2. 继承 `BaseStrategy` 基类
3. 实现 `generate_signals()` 方法
4. 在 `config/settings.yaml` 添加配置
5. 在 `main.py` 中注册策略

```python
from strategies.base_strategy import BaseStrategy

class YourStrategy(BaseStrategy):
    def __init__(self, config, client):
        super().__init__("YourStrategy", config)
        self.client = client
    
    def generate_signals(self, market_data):
        # 你的策略逻辑
        return signals
```

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📄 开源协议

本项目采用 MIT 协议 - 详见 [LICENSE](LICENSE) 文件

---

## 📞 联系方式

- **作者**：F-Sheng
- **GitHub**：[@F-Sheng](https://github.com/F-Sheng)
- **Email**：(请补充)

---

## ⭐ Star History

如果这个项目对你有帮助，请给个 ⭐ Star！

---

**⚠️ 免责声明**：本项目仅供学习和研究使用，不构成任何投资建议。加密货币交易存在高风险，请谨慎投资，盈亏自负。
