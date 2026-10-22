"""
配对交易策略
基于协整关系的统计套利
"""
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import coint, adfuller

from strategies.base_strategy import BaseStrategy, Signal


logger = logging.getLogger(__name__)


@dataclass
class PairPosition:
    """配对交易持仓"""
    pair_name: str
    symbol1: str
    symbol2: str
    side: str  # 'spread_long' (做多价差) 或 'spread_short' (做空价差)
    size1: float
    size2: float
    entry_spread: float
    entry_time: datetime
    zscore_at_entry: float


class PairTradingStrategy(BaseStrategy):
    """
    配对交易策略

    原理:
    - 找到两个协整的资产(如 BTC 和 ETH)
    - 计算价差(spread) = price1 - beta * price2
    - 当价差偏离均值过多时,做空价差(或做多价差)
    - 等价差回归均值后平仓

    核心指标:
    - 协整检验(Cointegration Test)
    - Z-score 标准化价差
    - 均值回归(Mean Reversion)
    """

    def __init__(self, config: Dict, okx_client):
        super().__init__("PairTrading", config)
        self.client = okx_client

        # 策略参数
        self.pairs = config.get('pairs', [])
        self.max_position_usd = config.get('max_position_usd', 5000)
        self.check_interval = config.get('check_interval', 3600)  # 1小时

        # 持仓
        self.positions: Dict[str, PairPosition] = {}

        # 历史数据缓存
        self.price_history: Dict[str, pd.Series] = {}

        # 统计数据
        self.cointegration_results: Dict[str, Dict] = {}
        self.spread_stats: Dict[str, Dict] = {}

        self.last_check_time = 0

    def initialize(self):
        """初始化策略"""
        self.logger.info("配对交易策略初始化...")

        # 加载历史数据
        for pair_config in self.pairs:
            pair_name = f"{pair_config['symbol1']}-{pair_config['symbol2']}"
            self.logger.info(f"初始化配对: {pair_name}")

            # 获取历史数据
            self.load_price_history(
                pair_config['symbol1'],
                pair_config['symbol2'],
                pair_config.get('cointegration_window', 168)  # 默认7天(小时)
            )

            # 进行协整检验
            self.test_cointegration(pair_name)

    def load_price_history(self, symbol1: str, symbol2: str, window: int = 168):
        """
        加载历史价格数据

        Args:
            symbol1: 交易对1
            symbol2: 交易对2
            window: 历史窗口(小时)
        """
        try:
            # 获取K线数据
            df1 = self.client.get_candles(symbol1, bar='1H', limit=window)
            df2 = self.client.get_candles(symbol2, bar='1H', limit=window)

            if df1.empty or df2.empty:
                self.logger.error(f"无法获取历史数据: {symbol1}, {symbol2}")
                return

            # 对齐时间戳
            merged = pd.merge(df1[['timestamp', 'close']], df2[['timestamp', 'close']],
                            on='timestamp', suffixes=('_1', '_2'))

            self.price_history[symbol1] = merged.set_index('timestamp')['close_1']
            self.price_history[symbol2] = merged.set_index('timestamp')['close_2']

            self.logger.info(f"加载历史数据: {symbol1}={len(df1)}, {symbol2}={len(df2)}")

        except Exception as e:
            self.logger.error(f"加载历史数据异常: {e}")

    def test_cointegration(self, pair_name: str) -> Dict:
        """
        协整检验

        Args:
            pair_name: 配对名称

        Returns:
            协整检验结果
        """
        try:
            symbol1, symbol2 = pair_name.split('-')

            if symbol1 not in self.price_history or symbol2 not in self.price_history:
                return {}

            prices1 = self.price_history[symbol1].values
            prices2 = self.price_history[symbol2].values

            # 检查数据长度
            if len(prices1) < 20 or len(prices2) < 20:
                self.logger.warning(f"数据不足: {pair_name}, 需要至少20个数据点")
                return {}

            # 协整检验
            coint_result = coint(prices1, prices2)
            coint_score = coint_result[0]
            pvalue = coint_result[1]

            # 计算对冲比率(beta)
            lr_result = stats.linregress(prices2, prices1)
            beta = lr_result.slope
            alpha = lr_result.intercept
            r_value = lr_result.rvalue

            # 计算价差
            spread = prices1 - beta * prices2

            # ADF 检验价差是否平稳
            adf_result = adfuller(spread)
            adf_pvalue = adf_result[1]

            result = {
                'pair': pair_name,
                'coint_score': coint_score,
                'pvalue': pvalue,
                'beta': beta,
                'alpha': alpha,
                'r_squared': r_value ** 2,
                'spread_mean': np.mean(spread),
                'spread_std': np.std(spread),
                'adf_pvalue': adf_pvalue,
                'is_cointegrated': pvalue < 0.05 and adf_pvalue < 0.05
            }

            self.cointegration_results[pair_name] = result

            if result['is_cointegrated']:
                self.logger.info(f"[OK] {pair_name} 协整关系成立: pvalue={pvalue:.4f}, beta={beta:.4f}")
            else:
                self.logger.warning(f"[X] {pair_name} 协整关系不成立: pvalue={pvalue:.4f}")

            return result

        except Exception as e:
            self.logger.error(f"协整检验异常: {e}")
            return {}

    def calculate_spread_zscore(self, pair_name: str) -> Optional[Dict]:
        """
        计算价差 Z-score

        Returns:
            价差信息
        """
        try:
            symbol1, symbol2 = pair_name.split('-')

            if symbol1 not in self.price_history or symbol2 not in self.price_history:
                return None

            if pair_name not in self.cointegration_results:
                return None

            beta = self.cointegration_results[pair_name]['beta']

            # 获取最新价格
            price1 = self.price_history[symbol1].iloc[-1]
            price2 = self.price_history[symbol2].iloc[-1]

            # 计算当前价差
            current_spread = price1 - beta * price2

            # 计算 Z-score
            spread_mean = self.cointegration_results[pair_name]['spread_mean']
            spread_std = self.cointegration_results[pair_name]['spread_std']

            zscore = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0

            return {
                'pair': pair_name,
                'price1': price1,
                'price2': price2,
                'beta': beta,
                'spread': current_spread,
                'spread_mean': spread_mean,
                'spread_std': spread_std,
                'zscore': zscore
            }

        except Exception as e:
            self.logger.error(f"计算价差异常: {e}")
            return None

    def generate_signals(self, market_data: Dict) -> List[Signal]:
        """
        生成交易信号

        Args:
            market_data: 市场数据

        Returns:
            信号列表
        """
        signals = []

        # 控制检查频率
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval:
            return signals

        self.last_check_time = current_time

        # 更新价格历史
        self.update_price_history()

        # 检查每个配对
        for pair_config in self.pairs:
            pair_name = f"{pair_config['symbol1']}-{pair_config['symbol2']}"

            # 重新进行协整检验(滚动窗口)
            self.test_cointegration(pair_name)

            # 计算 Z-score
            spread_info = self.calculate_spread_zscore(pair_name)
            if not spread_info:
                continue

            zscore = spread_info['zscore']
            zscore_threshold = pair_config.get('zscore_threshold', 2.0)
            stop_loss_zscore = pair_config.get('stop_loss_zscore', 3.5)

            self.logger.info(f"{pair_name}: Z-score = {zscore:.3f}")

            # 判断是否开仓
            if pair_name not in self.positions:
                # Z-score 太大,做空价差(卖出 symbol1, 买入 symbol2)
                if zscore > zscore_threshold:
                    signals.append(Signal(
                        symbol=pair_name,
                        action='open_spread_short',
                        size=1.0,
                        reason=f"Z-score={zscore:.3f} > {zscore_threshold}, 做空价差",
                        metadata=spread_info
                    ))

                # Z-score 太小,做多价差(买入 symbol1, 卖出 symbol2)
                elif zscore < -zscore_threshold:
                    signals.append(Signal(
                        symbol=pair_name,
                        action='open_spread_long',
                        size=1.0,
                        reason=f"Z-score={zscore:.3f} < -{zscore_threshold}, 做多价差",
                        metadata=spread_info
                    ))

            else:
                # 判断是否平仓
                position = self.positions[pair_name]

                # 价差回归,平仓
                if position.side == 'spread_short' and zscore < 0.5:
                    signals.append(Signal(
                        symbol=pair_name,
                        action='close_spread',
                        size=0,
                        reason=f"价差回归, Z-score={zscore:.3f}"
                    ))

                elif position.side == 'spread_long' and zscore > -0.5:
                    signals.append(Signal(
                        symbol=pair_name,
                        action='close_spread',
                        size=0,
                        reason=f"价差回归, Z-score={zscore:.3f}"
                    ))

                # 止损
                elif abs(zscore) > stop_loss_zscore:
                    signals.append(Signal(
                        symbol=pair_name,
                        action='close_spread',
                        size=0,
                        reason=f"止损触发, Z-score={zscore:.3f} > {stop_loss_zscore}"
                    ))

        return signals

    def update_price_history(self):
        """更新价格历史"""
        for pair_config in self.pairs:
            symbol1 = pair_config['symbol1']
            symbol2 = pair_config['symbol2']

            # 获取最新价格
            ticker1 = self.client.get_ticker(symbol1)
            ticker2 = self.client.get_ticker(symbol2)

            if ticker1 and ticker2:
                price1 = float(ticker1.get('last', 0))
                price2 = float(ticker2.get('last', 0))

                if price1 > 0 and price2 > 0:
                    # 添加到历史数据
                    now = datetime.now()

                    if symbol1 in self.price_history:
                        self.price_history[symbol1] = pd.concat([
                            self.price_history[symbol1],
                            pd.Series([price1], index=[now])
                        ]).tail(500)  # 保留最近500个点

                    if symbol2 in self.price_history:
                        self.price_history[symbol2] = pd.concat([
                            self.price_history[symbol2],
                            pd.Series([price2], index=[now])
                        ]).tail(500)

    def open_spread_position(self, pair_name: str, side: str, spread_info: Dict):
        """
        开仓

        Args:
            pair_name: 配对名称
            side: 'spread_long' 或 'spread_short'
            spread_info: 价差信息
        """
        try:
            symbol1, symbol2 = pair_name.split('-')

            # 计算仓位大小
            price1 = spread_info['price1']
            price2 = spread_info['price2']
            beta = spread_info['beta']

            # 假设每边各用一半资金
            capital_per_side = self.max_position_usd / 2

            size1 = capital_per_side / price1
            size2 = (capital_per_side * beta) / price2

            if side == 'spread_short':
                # 做空价差:卖出 symbol1, 买入 symbol2
                self.client.place_order(symbol1, 'sell', 'long', 'market', str(size1))
                self.client.place_order(symbol2, 'buy', 'long', 'market', str(size2))
            else:
                # 做多价差:买入 symbol1, 卖出 symbol2
                self.client.place_order(symbol1, 'buy', 'long', 'market', str(size1))
                self.client.place_order(symbol2, 'sell', 'long', 'market', str(size2))

            # 记录持仓
            self.positions[pair_name] = PairPosition(
                pair_name=pair_name,
                symbol1=symbol1,
                symbol2=symbol2,
                side=side,
                size1=size1,
                size2=size2,
                entry_spread=spread_info['spread'],
                entry_time=datetime.now(),
                zscore_at_entry=spread_info['zscore']
            )

            self.logger.info(f"开仓 {pair_name} {side}: size1={size1:.6f}, size2={size2:.6f}")

        except Exception as e:
            self.logger.error(f"开仓异常: {e}")

    def close_spread_position(self, pair_name: str):
        """平仓"""
        try:
            if pair_name not in self.positions:
                return

            position = self.positions[pair_name]

            # 平仓:反向操作
            if position.side == 'spread_short':
                # 平 spread_short:买入 symbol1, 卖出 symbol2
                self.client.place_order(position.symbol1, 'buy', 'long', 'market',
                                       str(position.size1), reduce_only=True)
                self.client.place_order(position.symbol2, 'sell', 'long', 'market',
                                       str(position.size2), reduce_only=True)
            else:
                # 平 spread_long:卖出 symbol1, 买入 symbol2
                self.client.place_order(position.symbol1, 'sell', 'long', 'market',
                                       str(position.size1), reduce_only=True)
                self.client.place_order(position.symbol2, 'buy', 'long', 'market',
                                       str(position.size2), reduce_only=True)

            del self.positions[pair_name]

            self.logger.info(f"平仓 {pair_name}")

        except Exception as e:
            self.logger.error(f"平仓异常: {e}")

    def on_order_filled(self, order: Dict):
        """订单成交回调"""
        action = order.get('action', '')
        pair_name = order.get('symbol', '')
        metadata = order.get('metadata', {})

        if action == 'open_spread_short':
            self.open_spread_position(pair_name, 'spread_short', metadata)
        elif action == 'open_spread_long':
            self.open_spread_position(pair_name, 'spread_long', metadata)
        elif action == 'close_spread':
            self.close_spread_position(pair_name)

    def get_performance(self) -> Dict:
        """获取绩效统计"""
        perf = super().get_performance()
        perf['active_pairs'] = len(self.positions)
        perf['cointegrated_pairs'] = sum(1 for r in self.cointegration_results.values()
                                         if r.get('is_cointegrated', False))
        return perf
