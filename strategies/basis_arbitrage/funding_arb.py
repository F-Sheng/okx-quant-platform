"""
资金费率套利策略
期现套利的核心:现货 + 永续合约对冲,赚取资金费率
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import time

from strategies.base_strategy import BaseStrategy, Signal
from execution.okx_client import OKXClient

logger = logging.getLogger(__name__)


@dataclass
class FundingArbPosition:
    """资金费率套利持仓"""
    symbol: str
    spot_size: float  # 现货数量
    swap_size: float  # 合约数量
    entry_time: datetime
    accumulated_funding: float = 0.0  # 累计收取的资金费


class FundingRateArbitrage(BaseStrategy):
    """
    资金费率套利策略

    原理:
    - 当资金费率为正(多头付给空头)时:
        * 买入现货
        * 做空等量永续合约
        * 每 8 小时收取资金费

    风险:
    - 市场中性,几乎无方向性风险
    - 主要风险是交易所风险和极端行情下的滑点
    """

    def __init__(self, config: Dict, okx_client: OKXClient):
        super().__init__("FundingRateArbitrage", config)
        self.client = okx_client

        # 策略参数
        self.symbols = config.get('symbols', ['BTC-USDT-SWAP'])
        self.min_funding_rate = config.get('min_funding_rate', 0.0001)  # 0.01%
        self.max_position_usd = config.get('max_position_usd', 10000)
        self.hedge_ratio = config.get('hedge_ratio', 1.0)
        self.check_interval = config.get('check_interval', 300)  # 5分钟

        # 持仓管理
        self.positions: Dict[str, FundingArbPosition] = {}

        # 状态
        self.last_check_time = 0
        self.total_funding_collected = 0.0

    def initialize(self):
        """初始化策略"""
        self.logger.info("资金费率套利策略初始化...")

        # 检查账户余额
        balance = self.client.get_usd_balance()
        self.logger.info(f"账户余额: {balance:.2f} USDT")

        if balance < 100:
            self.logger.warning("账户余额不足,建议至少 100 USDT")

        # 获取支持的交易对信息
        for symbol in self.symbols:
            info = self.client.get_instrument_info(symbol)
            if info:
                self.logger.info(f"{symbol}: 合约面值={info.get('ctVal')}, 最小下单量={info.get('minSz')}")
            else:
                self.logger.warning(f"无法获取 {symbol} 合约信息")

    def check_funding_opportunity(self, symbol: str) -> Optional[Dict]:
        """
        检查资金费率套利机会

        Returns:
            套利机会信息,如果有机会则返回
        """
        try:
            # 获取当前资金费率
            funding_data = self.client.get_funding_rate(symbol)
            if not funding_data:
                return None

            funding_rate = float(funding_data.get('fundingRate', 0))
            next_funding_time = int(funding_data.get('fundingTime', 0))
            current_time = int(time.time() * 1000)

            # 计算距离下次资金费的时间(小时)
            time_to_funding = (next_funding_time - current_time) / 1000 / 3600

            self.logger.debug(f"{symbol} 资金费率: {funding_rate:.6f}, 距下次结算: {time_to_funding:.2f}h")

            # 判断是否满足套利条件
            if funding_rate >= self.min_funding_rate:
                return {
                    'symbol': symbol,
                    'funding_rate': funding_rate,
                    'annualized_return': funding_rate * 3 * 365,  # 年化收益率(每8小时一次)
                    'next_funding_time': next_funding_time,
                    'time_to_funding_hours': time_to_funding
                }

            return None

        except Exception as e:
            self.logger.error(f"检查资金费率异常: {e}")
            return None

    def calculate_position_size(self, symbol: str, funding_rate: float) -> Dict:
        """
        计算仓位大小

        Args:
            symbol: 交易对
            funding_rate: 资金费率

        Returns:
            仓位信息
        """
        try:
            # 获取当前价格
            price = self.client.get_ticker_price(symbol.replace('-SWAP', ''))
            if price == 0:
                return {}

            # 获取合约信息
            instrument = self.client.get_instrument_info(symbol)
            contract_value = float(instrument.get('ctVal', 0.01))  # BTC 合约面值 0.01 BTC

            # 计算最大可用资金
            available_balance = self.client.get_usd_balance()

            # 根据资金费率调整仓位(费率越高,仓位越大)
            rate_multiplier = min(funding_rate / self.min_funding_rate, 3.0)

            # 计算仓位大小(USD)
            position_usd = min(
                self.max_position_usd * rate_multiplier,
                available_balance * 0.5  # 最多使用 50% 资金
            )

            # 计算合约张数
            # 1 张 = contract_value BTC
            swap_contracts = int(position_usd / (price * contract_value))

            # 现货数量 = 合约数量 * 合约面值 * 对冲比例
            spot_amount = swap_contracts * contract_value * self.hedge_ratio

            return {
                'symbol': symbol,
                'price': price,
                'position_usd': position_usd,
                'swap_contracts': swap_contracts,
                'spot_amount': spot_amount,
                'contract_value': contract_value
            }

        except Exception as e:
            self.logger.error(f"计算仓位异常: {e}")
            return {}

    def open_arbitrage_position(self, symbol: str, position_info: Dict) -> bool:
        """
        开仓(现货 + 合约对冲)

        Args:
            symbol: 合约交易对 (e.g., BTC-USDT-SWAP)
            position_info: 仓位信息

        Returns:
            是否成功
        """
        try:
            spot_symbol = symbol.replace('-SWAP', '')

            self.logger.info(f"开始套利开仓: {symbol}")
            self.logger.info(f"  现货: 买入 {position_info['spot_amount']:.6f} {spot_symbol}")
            self.logger.info(f"  合约: 做空 {position_info['swap_contracts']} 张 {symbol}")

            # 1. 买入现货
            spot_order = self.client.place_order(
                symbol=spot_symbol,
                side='buy',
                pos_side='long',
                order_type='market',
                size=str(position_info['spot_amount'])
            )

            if 'error' in spot_order:
                self.logger.error(f"现货下单失败: {spot_order['error']}")
                return False

            # 2. 做空合约
            swap_order = self.client.place_order(
                symbol=symbol,
                side='sell',
                pos_side='short',
                order_type='market',
                size=str(position_info['swap_contracts'])
            )

            if 'error' in swap_order:
                self.logger.error(f"合约下单失败: {swap_order['error']}")

                # 回滚:平掉现货
                self.client.place_order(
                    symbol=spot_symbol,
                    side='sell',
                    pos_side='long',
                    order_type='market',
                    size=str(position_info['spot_amount']),
                    reduce_only=True
                )
                return False

            # 记录持仓
            self.positions[symbol] = FundingArbPosition(
                symbol=symbol,
                spot_size=position_info['spot_amount'],
                swap_size=position_info['swap_contracts'],
                entry_time=datetime.now()
            )

            self.logger.info(f"套利开仓成功: {symbol}")
            return True

        except Exception as e:
            self.logger.error(f"套利开仓异常: {e}")
            return False

    def close_arbitrage_position(self, symbol: str) -> bool:
        """
        平仓

        Args:
            symbol: 合约交易对

        Returns:
            是否成功
        """
        try:
            if symbol not in self.positions:
                self.logger.warning(f"未找到持仓: {symbol}")
                return False

            position = self.positions[symbol]
            spot_symbol = symbol.replace('-SWAP', '')

            self.logger.info(f"开始套利平仓: {symbol}")

            # 1. 平空单(买入合约)
            swap_order = self.client.place_order(
                symbol=symbol,
                side='buy',
                pos_side='short',
                order_type='market',
                size=str(position.swap_size),
                reduce_only=True
            )

            if 'error' in swap_order:
                self.logger.error(f"合约平仓失败: {swap_order['error']}")
                return False

            # 2. 卖出现货
            spot_order = self.client.place_order(
                symbol=spot_symbol,
                side='sell',
                pos_side='long',
                order_type='market',
                size=str(position.spot_size),
                reduce_only=True
            )

            if 'error' in spot_order:
                self.logger.error(f"现货平仓失败: {spot_order['error']}")
                return False

            # 累计资金费收益
            self.total_funding_collected += position.accumulated_funding

            # 移除持仓
            del self.positions[symbol]

            self.logger.info(f"套利平仓成功: {symbol}, 累计资金费: {position.accumulated_funding:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"套利平仓异常: {e}")
            return False

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

        # 检查每个交易对
        for symbol in self.symbols:
            opportunity = self.check_funding_opportunity(symbol)

            if opportunity:
                self.logger.info(f"发现套利机会: {symbol}, 资金费率: {opportunity['funding_rate']:.6f}, "
                               f"年化: {opportunity['annualized_return']:.2%}")

                # 如果没有持仓,考虑开仓
                if symbol not in self.positions:
                    position_info = self.calculate_position_size(symbol, opportunity['funding_rate'])
                    if position_info and position_info.get('swap_contracts', 0) > 0:
                        signals.append(Signal(
                            symbol=symbol,
                            action='open_arbitrage',
                            size=position_info['swap_contracts'],
                            price=position_info['price'],
                            reason=f"资金费率套利: {opportunity['funding_rate']:.6f}, "
                                  f"年化: {opportunity['annualized_return']:.2%}",
                            metadata=position_info
                        ))

            else:
                # 如果资金费率变负,考虑平仓
                if symbol in self.positions:
                    self.logger.info(f"资金费率变负,平仓: {symbol}")
                    signals.append(Signal(
                        symbol=symbol,
                        action='close_arbitrage',
                        size=0,
                        reason="资金费率变负,停止套利"
                    ))

        return signals

    def on_order_filled(self, order: Dict):
        """订单成交回调"""
        symbol = order.get('symbol', '')
        action = order.get('action', '')

        self.logger.info(f"订单成交: {symbol} {action}")

        if action == 'open_arbitrage':
            position_info = order.get('metadata', {})
            self.open_arbitrage_position(symbol, position_info)
        elif action == 'close_arbitrage':
            self.close_arbitrage_position(symbol)

    def collect_funding_fee(self):
        """收集资金费(每 8 小时调用一次)"""
        for symbol, position in self.positions.items():
            try:
                # 获取最新资金费率
                funding_data = self.client.get_funding_rate(symbol)
                if funding_data:
                    funding_rate = float(funding_data.get('fundingRate', 0))

                    # 计算本次收取的资金费
                    # 空头在正费率时收钱
                    if funding_rate > 0:
                        # 合约数量 * 合约面值 * 价格 * 费率
                        instrument = self.client.get_instrument_info(symbol)
                        contract_value = float(instrument.get('ctVal', 0.01))
                        price = self.client.get_ticker_price(symbol.replace('-SWAP', ''))

                        funding_fee = position.swap_size * contract_value * price * funding_rate
                        position.accumulated_funding += funding_fee

                        self.logger.info(f"{symbol} 收取资金费: {funding_fee:.2f} USDT, "
                                       f"累计: {position.accumulated_funding:.2f}")

            except Exception as e:
                self.logger.error(f"收集资金费异常: {e}")

    def get_performance(self) -> Dict:
        """获取绩效统计"""
        perf = super().get_performance()
        perf['total_funding_collected'] = self.total_funding_collected
        perf['active_positions'] = len(self.positions)
        return perf
