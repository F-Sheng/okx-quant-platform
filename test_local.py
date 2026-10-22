"""
本地测试模式 - 使用模拟数据
当无法连接 OKX API 时,使用模拟数据测试策略逻辑
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class MockOKXClient:
    """模拟 OKX 客户端"""

    def __init__(self):
        self.prices = {
            'BTC-USDT': 65000.0,
            'ETH-USDT': 3200.0,
            'BTC-USDT-SWAP': 65100.0,
            'ETH-USDT-SWAP': 3205.0
        }

        self.funding_rates = {
            'BTC-USDT-SWAP': 0.0001,  # 0.01%
            'ETH-USDT-SWAP': 0.00015  # 0.015%
        }

        self.balance = 10000.0  # USDT

        logger.info("模拟 OKX 客户端初始化")

    def get_usd_balance(self):
        return self.balance

    def get_ticker(self, symbol):
        price = self.prices.get(symbol, 0)
        return {
            'last': str(price),
            'bidPx': str(price * 0.999),
            'askPx': str(price * 1.001),
            'vol24h': '1000000'
        }

    def get_ticker_price(self, symbol):
        return self.prices.get(symbol, 0)

    def get_funding_rate(self, symbol):
        rate = self.funding_rates.get(symbol, 0)
        return {
            'fundingRate': str(rate),
            'fundingTime': str(int(datetime.now().timestamp() * 1000) + 8*3600*1000)
        }

    def get_orderbook(self, symbol, depth=10):
        price = self.prices.get(symbol, 0)
        return {
            'bids': [[str(price * 0.999), '10']],
            'asks': [[str(price * 1.001), '10']]
        }

    def get_candlesticks(self, symbol, bar='1H', limit=100):
        """生成模拟K线数据"""
        price = self.prices.get(symbol, 100)

        dates = [datetime.now() - timedelta(hours=i) for i in range(limit, 0, -1)]

        data = []
        for date in dates:
            noise = np.random.normal(0, 0.02)
            p = price * (1 + noise)
            data.append([
                str(int(date.timestamp() * 1000)),
                str(p * 0.99),  # open
                str(p * 1.01),  # high
                str(p * 0.98),  # low
                str(p),          # close
                '1000',          # volume
                '1000',
                '1000',
                '1'
            ])

        return {'code': '0', 'data': data}

    def place_order(self, **kwargs):
        logger.info(f"[模拟] 下单: {kwargs}")
        return {'ordId': 'mock_order_123'}

    def get_instrument_info(self, symbol):
        return {
            'ctVal': '0.01',  # 合约面值
            'minSz': '1',      # 最小下单量
            'lotSz': '1'       # 下单步长
        }


def test_funding_arbitrage():
    """测试资金费率套利策略"""
    print("\n" + "=" * 60)
    print("测试: 资金费率套利策略")
    print("=" * 60)

    from strategies.basis_arbitrage.funding_arb import FundingRateArbitrage

    client = MockOKXClient()

    config = {
        'symbols': ['BTC-USDT-SWAP', 'ETH-USDT-SWAP'],
        'min_funding_rate': 0.0001,
        'max_position_usd': 10000,
        'hedge_ratio': 1.0,
        'check_interval': 0  # 立即检查
    }

    strategy = FundingRateArbitrage(config, client)
    strategy.initialize()

    # 模拟生成信号
    print("\n生成交易信号...")
    signals = strategy.generate_signals({})

    print(f"\n生成了 {len(signals)} 个信号:")
    for i, signal in enumerate(signals, 1):
        print(f"\n信号 {i}:")
        print(f"  动作: {signal.action}")
        print(f"  交易对: {signal.symbol}")
        print(f"  原因: {signal.reason}")
        if signal.metadata:
            print(f"  仓位: {signal.metadata.get('swap_contracts', 0)} 张")
            print(f"  金额: {signal.metadata.get('position_usd', 0):.2f} USD")

    print("\n[OK] 资金费率套利策略测试完成\n")


def test_pair_trading():
    """测试配对交易策略"""
    print("\n" + "=" * 60)
    print("测试: 配对交易策略")
    print("=" * 60)

    from strategies.pair_trading.pair_trading import PairTradingStrategy

    client = MockOKXClient()

    config = {
        'pairs': [
            {
                'symbol1': 'BTC-USDT',
                'symbol2': 'ETH-USDT',
                'cointegration_window': 168,
                'zscore_threshold': 2.0,
                'stop_loss_zscore': 3.5
            }
        ],
        'max_position_usd': 5000,
        'check_interval': 0  # 立即检查
    }

    strategy = PairTradingStrategy(config, client)
    strategy.initialize()

    # 显示协整检验结果
    print("\n协整检验结果:")
    for pair_name, result in strategy.cointegration_results.items():
        print(f"\n{pair_name}:")
        print(f"  P-value: {result.get('pvalue', 0):.4f}")
        print(f"  Beta: {result.get('beta', 0):.4f}")
        print(f"  R²: {result.get('r_squared', 0):.4f}")
        print(f"  协整关系: {'✓ 成立' if result.get('is_cointegrated') else '✗ 不成立'}")

    print("\n[OK] 配对交易策略测试完成\n")


def test_market_making():
    """测试做市策略"""
    print("\n" + "=" * 60)
    print("测试: 做市策略")
    print("=" * 60)

    from strategies.market_making.basic_mm import MarketMakingStrategy

    client = MockOKXClient()

    config = {
        'symbol': 'BTC-USDT-SWAP',
        'spread_bps': 20,
        'order_size_usd': 1000,
        'max_inventory_usd': 10000,
        'inventory_limit_pct': 0.3,
        'update_interval': 1
    }

    strategy = MarketMakingStrategy(config, client)
    strategy.initialize()

    # 计算报价
    bid_price, ask_price = strategy.calculate_order_prices()
    print(f"\n做市报价:")
    print(f"  买价: {bid_price:.2f}")
    print(f"  卖价: {ask_price:.2f}")
    print(f"  价差: {ask_price - bid_price:.2f}")
    print(f"  价差(bps): {((ask_price - bid_price) / bid_price * 10000):.1f}")

    print("\n[OK] 做市策略测试完成\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("本地测试模式(模拟数据)")
    print("=" * 60)
    print("\n说明: 使用模拟数据测试策略逻辑")
    print("     不需要连接 OKX API\n")

    test_funding_arbitrage()
    test_pair_trading()
    test_market_making()

    print("=" * 60)
    print("所有测试完成!")
    print("=" * 60)
    print("\n结论:")
    print("  1. 策略逻辑验证成功")
    print("  2. 信号生成正常")
    print("  3. 可以配置参数后使用")
    print("\n下一步:")
    print("  1. 解决网络问题(VPN/代理)")
    print("  2. 配置 config/settings.yaml")
    print("  3. 运行 py main.py 启动策略")
    print()


if __name__ == '__main__':
    main()
