"""
OKX 量化交易平台 - 主程序入口
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.okx_config import config
from execution.okx_client import OKXClient
from strategies.basis_arbitrage.funding_arb import FundingRateArbitrage
from strategies.pair_trading.pair_trading import PairTradingStrategy
from strategies.market_making.basic_mm import MarketMakingStrategy
from strategies.sentiment.sentiment_arb import SentimentTradingStrategy
from analysis.metrics import PerformanceAnalyzer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/quant.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class QuantPlatform:
    """量化交易平台"""

    def __init__(self):
        """初始化平台"""
        logger.info("=" * 60)
        logger.info("OKX 量化交易平台启动")
        logger.info("=" * 60)

        # 加载配置
        self.config = config

        # 初始化交易所客户端
        exchange_config = self.config.exchange_config
        self.okx_client = OKXClient(
            api_key=exchange_config['api_key'],
            secret_key=exchange_config['secret_key'],
            passphrase=exchange_config['passphrase'],
            trading_mode=exchange_config.get('trading_mode', 'demo')
        )

        # 初始化策略
        self.strategies: Dict[str, object] = {}
        self.initialize_strategies()

        # 分析器
        self.analyzer = PerformanceAnalyzer()

        # 状态
        self.is_running = False

        logger.info("平台初始化完成")

    def initialize_strategies(self):
        """初始化所有策略"""
        logger.info("初始化策略...")

        # 1. 资金费率套利策略
        if self.config.basis_arbitrage_config.get('enabled', False):
            self.strategies['funding_arb'] = FundingRateArbitrage(
                self.config.basis_arbitrage_config,
                self.okx_client
            )
            logger.info("✓ 资金费率套利策略已加载")

        # 2. 配对交易策略
        if self.config.pair_trading_config.get('enabled', False):
            self.strategies['pair_trading'] = PairTradingStrategy(
                self.config.pair_trading_config,
                self.okx_client
            )
            logger.info("✓ 配对交易策略已加载")

        # 3. 做市策略
        if self.config.market_making_config.get('enabled', False):
            self.strategies['market_making'] = MarketMakingStrategy(
                self.config.market_making_config,
                self.okx_client
            )
            logger.info("✓ 做市策略已加载")

        # 4. 情绪分析策略
        if self.config.sentiment_config.get('enabled', False):
            self.strategies['sentiment'] = SentimentTradingStrategy(
                self.config.sentiment_config,
                self.okx_client
            )
            logger.info("✓ 情绪分析策略已加载")

        logger.info(f"共加载 {len(self.strategies)} 个策略")

    def start(self):
        """启动平台"""
        logger.info("启动交易系统...")

        self.is_running = True

        # 初始化所有策略
        for name, strategy in self.strategies.items():
            strategy.initialize()
            strategy.start()

        # 主循环
        try:
            self.main_loop()
        except KeyboardInterrupt:
            logger.info("收到停止信号")
            self.stop()

    def main_loop(self):
        """主循环"""
        logger.info("进入主循环...")

        while self.is_running:
            try:
                # 获取市场数据
                market_data = self.fetch_market_data()

                # 运行每个策略
                for name, strategy in self.strategies.items():
                    if strategy.is_running:
                        strategy.on_tick(market_data)

                # 等待下一次更新
                time.sleep(5)  # 5秒更新一次

            except Exception as e:
                logger.error(f"主循环异常: {e}")
                time.sleep(5)

    def fetch_market_data(self) -> Dict:
        """获取市场数据"""
        market_data = {}

        # 获取主要交易对行情
        symbols = ['BTC-USDT', 'ETH-USDT', 'BTC-USDT-SWAP', 'ETH-USDT-SWAP']

        for symbol in symbols:
            ticker = self.okx_client.get_ticker(symbol)
            if ticker:
                market_data[symbol] = {
                    'last': float(ticker.get('last', 0)),
                    'bid': float(ticker.get('bidPx', 0)),
                    'ask': float(ticker.get('askPx', 0)),
                    'volume': float(ticker.get('vol24h', 0))
                }

        return market_data

    def stop(self):
        """停止平台"""
        logger.info("停止交易系统...")

        self.is_running = False

        # 停止所有策略
        for name, strategy in self.strategies.items():
            strategy.stop()

            # 打印绩效
            perf = strategy.get_performance()
            logger.info(f"策略 [{name}] 绩效: {perf}")

        logger.info("交易系统已停止")

    def get_status(self) -> Dict:
        """获取系统状态"""
        status = {
            'is_running': self.is_running,
            'strategies': {},
            'account_balance': self.okx_client.get_usd_balance()
        }

        for name, strategy in self.strategies.items():
            status['strategies'][name] = strategy.get_performance()

        return status

    def print_status(self):
        """打印系统状态"""
        status = self.get_status()

        print("\n" + "=" * 60)
        print("系统状态")
        print("=" * 60)
        print(f"运行状态: {'运行中' if status['is_running'] else '已停止'}")
        print(f"账户余额: {status['account_balance']:.2f} USDT")
        print("\n策略状态:")
        print("-" * 60)

        for name, perf in status['strategies'].items():
            print(f"\n【{name}】")
            print(f"  总盈亏: {perf.get('total_pnl', 0):.2f} USDT")
            print(f"  交易次数: {perf.get('trade_count', 0)}")
            print(f"  胜率: {perf.get('win_rate', 0):.2%}")
            print(f"  活跃仓位: {perf.get('positions_count', 0)}")

        print("=" * 60)


def main():
    """主函数"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║            OKX 量化交易平台 v1.0                          ║
    ║                                                           ║
    ║  策略: 期现套利 | 配对交易 | 做市 | 情绪分析               ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # 创建平台实例
    platform = QuantPlatform()

    # 打印初始状态
    platform.print_status()

    # 启动平台
    try:
        platform.start()
    except KeyboardInterrupt:
        print("\n\n收到停止信号,正在退出...")
        platform.stop()
    except Exception as e:
        logger.error(f"平台运行异常: {e}")
        platform.stop()
        raise


if __name__ == '__main__':
    main()
