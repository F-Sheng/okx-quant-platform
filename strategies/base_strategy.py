"""
策略基类
所有策略都继承自这个基类
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    action: str  # 'buy', 'sell', 'close', 'hold'
    size: float  # 数量
    price: Optional[float] = None  # 价格(None=市价)
    order_type: str = 'market'  # 'market', 'limit'
    reason: str = ''  # 信号原因
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Position:
    """持仓"""
    symbol: str
    side: str  # 'long', 'short'
    size: float  # 数量
    entry_price: float  # 开仓价格
    current_price: float = 0.0
    pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, name: str, config: Dict):
        """
        初始化策略

        Args:
            name: 策略名称
            config: 策略配置
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # 策略状态
        self.is_running = False
        self.positions: Dict[str, Position] = {}
        self.signals: List[Signal] = []

        # 绩效统计
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.trade_count = 0

        self.logger.info(f"策略 [{name}] 初始化完成")

    @abstractmethod
    def initialize(self):
        """初始化策略(加载历史数据、计算指标等)"""
        pass

    @abstractmethod
    def generate_signals(self, market_data: Dict) -> List[Signal]:
        """
        生成交易信号

        Args:
            market_data: 市场数据

        Returns:
            信号列表
        """
        pass

    @abstractmethod
    def on_order_filled(self, order: Dict):
        """订单成交回调"""
        pass

    def on_tick(self, market_data: Dict):
        """
        每个 tick 调用

        Args:
            market_data: 市场数据
        """
        if not self.is_running:
            return

        # 生成信号
        signals = self.generate_signals(market_data)

        # 处理信号
        for signal in signals:
            self.signals.append(signal)
            self.logger.info(f"生成信号: {signal.action} {signal.symbol} @ {signal.price} - {signal.reason}")

    def update_position(self, symbol: str, side: str, size: float, price: float):
        """更新持仓"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.current_price = price
            pos.pnl = (price - pos.entry_price) * pos.size * (1 if pos.side == 'long' else -1)
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=price,
                current_price=price
            )

    def close_position(self, symbol: str):
        """平仓"""
        if symbol in self.positions:
            pos = self.positions.pop(symbol)
            self.total_pnl += pos.pnl
            self.trade_count += 1

            if pos.pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1

            self.logger.info(f"平仓 {symbol}, PnL: {pos.pnl:.2f}, 总PnL: {self.total_pnl:.2f}")

    def get_performance(self) -> Dict:
        """获取绩效统计"""
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0

        return {
            'strategy': self.name,
            'total_pnl': self.total_pnl,
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': win_rate,
            'positions_count': len(self.positions)
        }

    def start(self):
        """启动策略"""
        self.is_running = True
        self.logger.info(f"策略 [{self.name}] 启动")

    def stop(self):
        """停止策略"""
        self.is_running = False
        self.logger.info(f"策略 [{self.name}] 停止")

    def reset(self):
        """重置策略"""
        self.positions.clear()
        self.signals.clear()
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.trade_count = 0
        self.logger.info(f"策略 [{self.name}] 重置")
