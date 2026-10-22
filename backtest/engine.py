"""
回测引擎
用于在历史数据上测试策略
"""
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易记录"""
    timestamp: datetime
    symbol: str
    action: str
    price: float
    size: float
    fee: float
    pnl: float = 0.0
    reason: str = ''


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)


class BacktestEngine:
    """
    回测引擎

    功能:
    - 模拟历史交易
    - 计算绩效指标
    - 生成回测报告
    """

    def __init__(self, initial_capital: float = 10000,
                 fee_rate: float = 0.001,
                 slippage: float = 0.0005):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资金
            fee_rate: 手续费率
            slippage: 滑点
        """
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage

        # 状态
        self.capital = initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []

        logger.info(f"回测引擎初始化: 资金={initial_capital}, 手续费={fee_rate}, 滑点={slippage}")

    def reset(self):
        """重置回测引擎"""
        self.capital = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()

    def execute_trade(self, timestamp: datetime, symbol: str,
                     action: str, price: float, size: float,
                     reason: str = '') -> Optional[Trade]:
        """
        执行交易

        Args:
            timestamp: 时间
            symbol: 交易对
            action: 'buy' 或 'sell'
            price: 价格
            size: 数量
            reason: 交易原因

        Returns:
            交易记录
        """
        try:
            # 计算滑点
            if action == 'buy':
                execution_price = price * (1 + self.slippage)
            else:
                execution_price = price * (1 - self.slippage)

            # 计算手续费
            trade_value = execution_price * size
            fee = trade_value * self.fee_rate

            # 检查资金是否足够
            if action == 'buy':
                total_cost = trade_value + fee
                if total_cost > self.capital:
                    logger.warning(f"资金不足: 需要 {total_cost:.2f}, 可用 {self.capital:.2f}")
                    return None

                # 扣除资金
                self.capital -= total_cost

                # 更新持仓
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    total_size = pos['size'] + size
                    avg_price = (pos['avg_price'] * pos['size'] + execution_price * size) / total_size
                    pos['size'] = total_size
                    pos['avg_price'] = avg_price
                else:
                    self.positions[symbol] = {
                        'size': size,
                        'avg_price': execution_price
                    }

                pnl = 0.0

            else:  # sell
                # 检查是否有持仓
                if symbol not in self.positions or self.positions[symbol]['size'] < size:
                    logger.warning(f"持仓不足: {symbol}")
                    return None

                # 计算 PnL
                pos = self.positions[symbol]
                pnl = (execution_price - pos['avg_price']) * size

                # 更新持仓
                pos['size'] -= size
                if pos['size'] < 1e-10:
                    del self.positions[symbol]

                # 增加资金
                self.capital += trade_value - fee

            # 记录交易
            trade = Trade(
                timestamp=timestamp,
                symbol=symbol,
                action=action,
                price=execution_price,
                size=size,
                fee=fee,
                pnl=pnl,
                reason=reason
            )
            self.trades.append(trade)

            logger.debug(f"交易: {action} {symbol} {size:.6f} @ {execution_price:.2f}, PnL: {pnl:.2f}")

            return trade

        except Exception as e:
            logger.error(f"执行交易异常: {e}")
            return None

    def update_equity(self, timestamp: datetime, prices: Dict[str, float]):
        """
        更新权益曲线

        Args:
            timestamp: 时间
            prices: 价格字典
        """
        # 计算持仓价值
        position_value = 0.0
        for symbol, pos in self.positions.items():
            if symbol in prices:
                position_value += pos['size'] * prices[symbol]

        total_equity = self.capital + position_value

        self.equity_curve.append({
            'timestamp': timestamp,
            'capital': self.capital,
            'position_value': position_value,
            'total_equity': total_equity
        })

    def calculate_metrics(self) -> BacktestResult:
        """
        计算绩效指标

        Returns:
            回测结果
        """
        if not self.equity_curve:
            return None

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        equity_df = equity_df.set_index('timestamp')

        # 基本指标
        final_capital = equity_df['total_equity'].iloc[-1]
        total_return = (final_capital - self.initial_capital) / self.initial_capital

        # 年化收益率
        days = (equity_df.index[-1] - equity_df.index[0]).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        # 夏普比率
        returns = equity_df['total_equity'].pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(365)
        else:
            sharpe_ratio = 0.0

        # 最大回撤
        cumulative = equity_df['total_equity']
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # 胜率
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        total_closed_trades = len(winning_trades) + len(losing_trades)
        win_rate = len(winning_trades) / total_closed_trades if total_closed_trades > 0 else 0

        return BacktestResult(
            strategy_name='strategy',
            start_date=equity_df.index[0],
            end_date=equity_df.index[-1],
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trade_count=len(self.trades),
            trades=self.trades.copy(),
            equity_curve=equity_df.reset_index()
        )

    def run_backtest(self, strategy, historical_data: pd.DataFrame,
                    price_column: str = 'close') -> BacktestResult:
        """
        运行回测

        Args:
            strategy: 策略对象
            historical_data: 历史数据
            price_column: 价格列名

        Returns:
            回测结果
        """
        logger.info(f"开始回测: {len(historical_data)} 条数据")

        self.reset()

        # 初始化策略
        strategy.initialize()

        for idx, row in historical_data.iterrows():
            timestamp = row['timestamp'] if 'timestamp' in row else idx
            price = row[price_column]

            # 构造市场数据
            market_data = {
                'timestamp': timestamp,
                'price': price,
                'open': row.get('open', price),
                'high': row.get('high', price),
                'low': row.get('low', price),
                'close': price,
                'volume': row.get('volume', 0)
            }

            # 生成信号
            signals = strategy.generate_signals(market_data)

            # 执行交易
            for signal in signals:
                if signal.action in ['buy', 'sell']:
                    self.execute_trade(
                        timestamp=timestamp,
                        symbol=signal.symbol,
                        action=signal.action,
                        price=price,
                        size=signal.size,
                        reason=signal.reason
                    )

            # 更新权益
            self.update_equity(timestamp, {signal.symbol: price})

        # 计算指标
        result = self.calculate_metrics()

        logger.info(f"回测完成: 总收益={result.total_return:.2%}, 年化={result.annual_return:.2%}, "
                   f"夏普={result.sharpe_ratio:.2f}, 最大回撤={result.max_drawdown:.2%}")

        return result
