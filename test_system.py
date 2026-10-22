"""
系统测试脚本
"""
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_configuration():
    """测试配置加载"""
    print("=" * 60)
    print("测试 1: 配置加载")
    print("=" * 60)

    from config.okx_config import config

    print(f"交易所: {config.exchange_config.get('name')}")
    print(f"交易模式: {config.exchange_config.get('trading_mode')}")
    print(f"资金费率套利启用: {config.basis_arbitrage_config.get('enabled')}")
    print(f"配对交易启用: {config.pair_trading_config.get('enabled')}")
    print(f"做市策略启用: {config.market_making_config.get('enabled')}")
    print(f"情绪分析启用: {config.sentiment_config.get('enabled')}")
    print("\n✓ 配置加载成功\n")


def test_database():
    """测试数据库"""
    print("=" * 60)
    print("测试 2: 数据库")
    print("=" * 60)

    from data.database import Database

    db = Database('data/test_quant.db')
    print(f"数据库路径: {db.db_path}")
    print("✓ 数据库初始化成功\n")


def test_okx_client():
    """测试 OKX 客户端(需要 API)"""
    print("=" * 60)
    print("测试 3: OKX 客户端连接")
    print("=" * 60)

    from config.okx_config import config
    from execution.okx_client import OKXClient

    try:
        client = OKXClient(
            api_key=config.exchange_config['api_key'],
            secret_key=config.exchange_config['secret_key'],
            passphrase=config.exchange_config['passphrase'],
            trading_mode=config.exchange_config.get('trading_mode', 'demo')
        )

        print("正在连接 OKX...")

        # 测试获取余额
        balance = client.get_usd_balance()
        print(f"账户余额: {balance:.2f} USDT")

        # 测试获取行情
        ticker = client.get_ticker('BTC-USDT')
        if ticker:
            price = float(ticker.get('last', 0))
            print(f"BTC 价格: {price:.2f} USDT")

        # 测试获取资金费率
        funding = client.get_funding_rate('BTC-USDT-SWAP')
        if funding:
            rate = float(funding.get('fundingRate', 0))
            print(f"BTC 资金费率: {rate:.6f}")

        print("\n✓ OKX 客户端连接成功\n")
        return client

    except Exception as e:
        print(f"✗ OKX 客户端连接失败: {e}\n")
        return None


def test_strategies(client):
    """测试策略"""
    print("=" * 60)
    print("测试 4: 策略初始化")
    print("=" * 60)

    if client is None:
        print("跳过策略测试(需要 OKX 连接)\n")
        return

    from config.okx_config import config

    # 测试资金费率套利策略
    print("\n【资金费率套利策略】")
    from strategies.basis_arbitrage.funding_arb import FundingRateArbitrage
    funding_strategy = FundingRateArbitrage(
        config.basis_arbitrage_config,
        client
    )
    funding_strategy.initialize()
    print("✓ 资金费率套利策略初始化成功")

    # 测试配对交易策略
    print("\n【配对交易策略】")
    from strategies.pair_trading.pair_trading import PairTradingStrategy
    pair_strategy = PairTradingStrategy(
        config.pair_trading_config,
        client
    )
    pair_strategy.initialize()
    print("✓ 配对交易策略初始化成功")

    print("\n✓ 所有策略测试通过\n")


def test_backtest():
    """测试回测引擎"""
    print("=" * 60)
    print("测试 5: 回测引擎")
    print("=" * 60)

    from backtest.engine import BacktestEngine

    engine = BacktestEngine(
        initial_capital=10000,
        fee_rate=0.001,
        slippage=0.0005
    )

    print(f"初始资金: {engine.initial_capital} USDT")
    print(f"手续费率: {engine.fee_rate:.2%}")
    print(f"滑点: {engine.slippage:.2%}")
    print("\n✓ 回测引擎初始化成功\n")


def test_performance_analyzer():
    """测试绩效分析"""
    print("=" * 60)
    print("测试 6: 绩效分析")
    print("=" * 60)

    from analysis.metrics import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()
    print("✓ 绩效分析器初始化成功\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("OKX 量化交易平台 - 系统测试")
    print("=" * 60 + "\n")

    # 运行测试
    test_configuration()
    test_database()

    client = test_okx_client()

    test_strategies(client)
    test_backtest()
    test_performance_analyzer()

    print("=" * 60)
    print("测试完成!")
    print("=" * 60)
    print("\n下一步:")
    print("1. 检查 config/settings.yaml 配置")
    print("2. 运行 python main.py 启动交易系统")
    print("3. 或运行回测: python backtest/run_backtest.py")
    print()


if __name__ == '__main__':
    main()
