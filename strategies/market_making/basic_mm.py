"""
做市策略
提供流动性,赚取买卖价差
"""
import logging
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass
import time

from strategies.base_strategy import BaseStrategy, Signal
from execution.okx_client import OKXClient


logger = logging.getLogger(__name__)


@dataclass
class MarketMakerOrder:
    """做市订单"""
    order_id: str
    side: str  # 'buy' 或 'sell'
    price: float
    size: float
    timestamp: datetime


class MarketMakingStrategy(BaseStrategy):
    """
    做市策略

    原理:
    - 在买一和卖一附近挂单
    - 赚取买卖价差(spread)
    - 同时管理库存,避免单边持仓过大

    关键指标:
    - Spread: 买卖价差
    - Inventory: 库存(持仓)
    - Fill Rate: 成交率
    """

    def __init__(self, config: Dict, okx_client: OKXClient):
        super().__init__("MarketMaking", config)
        self.client = okx_client

        # 策略参数
        self.symbol = config.get('symbol', 'BTC-USDT-SWAP')
        self.spread_bps = config.get('spread_bps', 20)  # 价差 20bp = 0.2%
        self.order_size_usd = config.get('order_size_usd', 1000)
        self.max_inventory_usd = config.get('max_inventory_usd', 10000)
        self.inventory_limit_pct = config.get('inventory_limit_pct', 0.3)
        self.update_interval = config.get('update_interval', 1)  # 1秒

        # 订单管理
        self.active_orders: Dict[str, MarketMakerOrder] = {}
        self.bid_order_id: Optional[str] = None
        self.ask_order_id: Optional[str] = None

        # 库存管理
        self.inventory = 0.0  # 正=多头,负=空头
        self.inventory_avg_price = 0.0

        # 统计
        self.total_volume = 0.0
        self.total_spread_captured = 0.0
        self.fill_count = 0

        self.last_update_time = 0

    def initialize(self):
        """初始化策略"""
        self.logger.info(f"做市策略初始化: {self.symbol}")

        # 检查账户
        balance = self.client.get_usd_balance()
        self.logger.info(f"账户余额: {balance:.2f} USDT")

        # 获取订单簿信息
        orderbook = self.client.get_orderbook(self.symbol, depth=10)
        if orderbook:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            if bids and asks:
                bid_price = float(bids[0][0])
                ask_price = float(asks[0][0])
                spread = ask_price - bid_price
                spread_bps = (spread / bid_price) * 10000

                self.logger.info(f"当前市场: bid={bid_price}, ask={ask_price}, spread={spread_bps:.1f}bp")

    def calculate_order_prices(self) -> tuple:
        """
        计算挂单价格

        Returns:
            (bid_price, ask_price)
        """
        try:
            # 获取订单簿
            orderbook = self.client.get_orderbook(self.symbol, depth=5)
            if not orderbook:
                return 0, 0

            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            if not bids or not asks:
                return 0, 0

            # 最优买卖价
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            mid_price = (best_bid + best_ask) / 2

            # 计算我们的报价
            # 在市场价差基础上,我们报价稍微激进一点
            spread = best_ask - best_bid

            # 我们的价差(百分比)
            our_spread = mid_price * (self.spread_bps / 10000)

            # 考虑库存调整(库存多时,降低卖价;库存空时,提高买价)
            inventory_skew = (self.inventory / self.max_inventory_usd) * our_spread * 0.5

            bid_price = mid_price - our_spread / 2 + inventory_skew
            ask_price = mid_price + our_spread / 2 + inventory_skew

            return round(bid_price, 2), round(ask_price, 2)

        except Exception as e:
            self.logger.error(f"计算报价异常: {e}")
            return 0, 0

    def calculate_order_size(self, side: str) -> float:
        """
        计算下单数量

        Args:
            side: 'buy' 或 'sell'

        Returns:
            下单数量
        """
        # 基础数量
        base_size = self.order_size_usd

        # 根据库存调整
        inventory_ratio = abs(self.inventory) / self.max_inventory_usd

        if inventory_ratio > self.inventory_limit_pct:
            # 库存过大,减小单边挂单
            if (side == 'buy' and self.inventory > 0) or \
               (side == 'sell' and self.inventory < 0):
                # 这个方向会增加库存,减小仓位
                base_size *= 0.5

        # 转换为合约数量
        price = self.client.get_ticker_price(self.symbol)
        if price > 0:
            size = base_size / price
            return round(size, 4)

        return 0

    def cancel_all_orders(self):
        """取消所有订单"""
        try:
            self.client.cancel_all_orders(self.symbol)
            self.active_orders.clear()
            self.bid_order_id = None
            self.ask_order_id = None
            self.logger.debug("取消所有订单")
        except Exception as e:
            self.logger.error(f"取消订单异常: {e}")

    def place_market_making_orders(self):
        """挂做市订单"""
        try:
            # 计算报价
            bid_price, ask_price = self.calculate_order_prices()

            if bid_price == 0 or ask_price == 0:
                return

            # 取消旧订单
            self.cancel_all_orders()

            # 计算数量
            bid_size = self.calculate_order_size('buy')
            ask_size = self.calculate_order_size('sell')

            if bid_size > 0:
                # 挂买单
                bid_order = self.client.place_order(
                    symbol=self.symbol,
                    side='buy',
                    pos_side='long',
                    order_type='limit',
                    size=str(bid_size),
                    price=str(bid_price)
                )

                if 'error' not in bid_order:
                    self.bid_order_id = bid_order.get('ordId', '')
                    self.active_orders[self.bid_order_id] = MarketMakerOrder(
                        order_id=self.bid_order_id,
                        side='buy',
                        price=bid_price,
                        size=bid_size,
                        timestamp=datetime.now()
                    )

            if ask_size > 0:
                # 挂卖单
                ask_order = self.client.place_order(
                    symbol=self.symbol,
                    side='sell',
                    pos_side='short',
                    order_type='limit',
                    size=str(ask_size),
                    price=str(ask_price)
                )

                if 'error' not in ask_order:
                    self.ask_order_id = ask_order.get('ordId', '')
                    self.active_orders[self.ask_order_id] = MarketMakerOrder(
                        order_id=self.ask_order_id,
                        side='sell',
                        price=ask_price,
                        size=ask_size,
                        timestamp=datetime.now()
                    )

            self.logger.debug(f"挂单: bid={bid_price}, ask={ask_price}")

        except Exception as e:
            self.logger.error(f"挂单异常: {e}")

    def update_inventory(self, side: str, size: float, price: float):
        """
        更新库存

        Args:
            side: 'buy' 或 'sell'
            size: 数量
            price: 价格
        """
        if side == 'buy':
            # 买入,库存增加
            new_inventory = self.inventory + size

            if self.inventory >= 0:
                # 已经是多头或无仓位
                total_cost = self.inventory * self.inventory_avg_price + size * price
                self.inventory_avg_price = total_cost / new_inventory if new_inventory != 0 else 0
            else:
                # 空头减仓
                pass

            self.inventory = new_inventory

        else:
            # 卖出,库存减少
            new_inventory = self.inventory - size

            if self.inventory <= 0:
                # 已经是空头或无仓位
                total_cost = self.inventory * self.inventory_avg_price - size * price
                self.inventory_avg_price = total_cost / new_inventory if new_inventory != 0 else 0

            self.inventory = new_inventory

        self.logger.info(f"更新库存: {side} {size:.4f} @ {price}, 库存={self.inventory:.4f}")

    def generate_signals(self, market_data: Dict) -> List[Signal]:
        """
        生成交易信号(做市策略主要靠挂单,这里用于检查订单状态)

        Args:
            market_data: 市场数据

        Returns:
            信号列表
        """
        signals = []

        # 控制更新频率
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return signals

        self.last_update_time = current_time

        # 检查订单状态
        self.check_order_status()

        # 检查是否需要调整报价
        if self.should_update_orders():
            signals.append(Signal(
                symbol=self.symbol,
                action='update_orders',
                size=0,
                reason='调整做市报价'
            ))

        return signals

    def check_order_status(self):
        """检查订单状态"""
        try:
            for order_id, order in list(self.active_orders.items()):
                order_info = self.client.get_order(self.symbol, order_id)

                if order_info:
                    state = order_info.get('state', '')
                    filled_size = float(order_info.get('accFillSz', 0))

                    if state == 'filled':
                        # 订单成交
                        self.fill_count += 1
                        self.total_volume += filled_size * order.price

                        # 更新库存
                        self.update_inventory(order.side, filled_size, order.price)

                        # 移除订单
                        del self.active_orders[order_id]
                        if order_id == self.bid_order_id:
                            self.bid_order_id = None
                        elif order_id == self.ask_order_id:
                            self.ask_order_id = None

                    elif state == 'canceled':
                        del self.active_orders[order_id]

        except Exception as e:
            self.logger.error(f"检查订单状态异常: {e}")

    def should_update_orders(self) -> bool:
        """是否需要更新订单"""
        # 如果没有买单或卖单,需要更新
        if not self.bid_order_id or not self.ask_order_id:
            return True

        # 检查订单是否太旧(超过30秒)
        for order in self.active_orders.values():
            age = (datetime.now() - order.timestamp).total_seconds()
            if age > 30:
                return True

        return False

    def on_order_filled(self, order: Dict):
        """订单成交回调"""
        order_id = order.get('orderId', '')
        side = order.get('side', '')
        size = float(order.get('size', 0))
        price = float(order.get('price', 0))

        if order_id in self.active_orders:
            del self.active_orders[order_id]

        self.update_inventory(side, size, price)

        # 计算价差收益
        if side == 'buy':
            # 买单成交,如果之前有卖单成交,计算价差
            spread = price * self.spread_bps / 10000
            self.total_spread_captured += spread * size

    def get_performance(self) -> Dict:
        """获取绩效统计"""
        perf = super().get_performance()
        perf.update({
            'total_volume': self.total_volume,
            'total_spread_captured': self.total_spread_captured,
            'fill_count': self.fill_count,
            'inventory': self.inventory,
            'active_orders': len(self.active_orders)
        })
        return perf
