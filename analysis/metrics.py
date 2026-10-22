"""
绩效分析模块
"""
import logging
from typing import Dict, List
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """绩效分析器"""

    def __init__(self):
        """初始化分析器"""
        pass

    @staticmethod
    def calculate_metrics(equity_curve: pd.DataFrame) -> Dict:
        """
        计算绩效指标

        Args:
            equity_curve: 权益曲线 DataFrame, 需要包含 'timestamp' 和 'total_equity' 列

        Returns:
            绩效指标字典
        """
        if equity_curve.empty:
            return {}

        equity = equity_curve['total_equity']
        returns = equity.pct_change().dropna()

        # 基本指标
        total_return = (equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0]

        # 年化收益率
        days = (pd.to_datetime(equity_curve['timestamp'].iloc[-1]) -
                pd.to_datetime(equity_curve['timestamp'].iloc[0])).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        # 夏普比率(假设无风险利率为 0)
        if returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(365)
        else:
            sharpe_ratio = 0

        # 索提诺比率(只考虑下行风险)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(365)
        else:
            sortino_ratio = 0

        # 最大回撤
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # 卡玛比率
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0

        # 波动率
        volatility = returns.std() * np.sqrt(365)

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'trading_days': days
        }

    @staticmethod
    def plot_equity_curve(equity_curve: pd.DataFrame, title: str = 'Equity Curve',
                         save_path: str = None):
        """
        绘制权益曲线

        Args:
            equity_curve: 权益曲线
            title: 图表标题
            save_path: 保存路径
        """
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # 权益曲线
        axes[0].plot(equity_curve['timestamp'], equity_curve['total_equity'],
                    linewidth=2, color='blue')
        axes[0].set_title(title, fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Total Equity (USDT)')
        axes[0].grid(True, alpha=0.3)
        axes[0].fill_between(equity_curve['timestamp'], equity_curve['total_equity'],
                            alpha=0.3, color='blue')

        # 回撤曲线
        equity = equity_curve['total_equity']
        running_max = equity.expanding().max()
        drawdown = ((equity - running_max) / running_max) * 100

        axes[1].fill_between(equity_curve['timestamp'], drawdown, 0,
                            alpha=0.5, color='red')
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].set_xlabel('Time')
        axes[1].grid(True, alpha=0.3)
        axes[1].set_title('Drawdown', fontsize=12)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"图表已保存: {save_path}")

        plt.show()

    @staticmethod
    def plot_monthly_returns(equity_curve: pd.DataFrame, save_path: str = None):
        """
        绘制月度收益热力图

        Args:
            equity_curve: 权益曲线
            save_path: 保存路径
        """
        # 计算月度收益
        equity_curve['timestamp'] = pd.to_datetime(equity_curve['timestamp'])
        equity_curve = equity_curve.set_index('timestamp')

        monthly_equity = equity_curve['total_equity'].resample('M').last()
        monthly_returns = monthly_equity.pct_change().dropna()

        # 创建年-月矩阵
        monthly_returns_df = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values * 100
        })

        pivot = monthly_returns_df.pivot(index='year', columns='month', values='return')

        # 绘制热力图
        plt.figure(figsize=(12, 6))
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn',
                   center=0, linewidths=1, cbar_kws={'label': 'Return (%)'})
        plt.title('Monthly Returns Heatmap (%)', fontsize=14, fontweight='bold')
        plt.xlabel('Month')
        plt.ylabel('Year')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"图表已保存: {save_path}")

        plt.show()

    @staticmethod
    def generate_report(result) -> str:
        """
        生成绩效报告

        Args:
            result: BacktestResult 对象

        Returns:
            报告文本
        """
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║                    策略回测报告                                ║
╚════════════════════════════════════════════════════════════════╝

策略名称: {result.strategy_name}
回测期间: {result.start_date.strftime('%Y-%m-%d')} 至 {result.end_date.strftime('%Y-%m-%d')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【收益指标】
  初始资金:     {result.initial_capital:>15,.2f} USDT
  最终资金:     {result.final_capital:>15,.2f} USDT
  总收益率:     {result.total_return:>15.2%}
  年化收益率:   {result.annual_return:>15.2%}

【风险指标】
  最大回撤:     {result.max_drawdown:>15.2%}
  夏普比率:     {result.sharpe_ratio:>15.2f}

【交易统计】
  总交易次数:   {result.trade_count:>15d}
  胜率:         {result.win_rate:>15.2%}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【评估】
"""
        # 评级
        if result.annual_return > 0.20 and result.sharpe_ratio > 1.5:
            rating = "★★★★★ 优秀"
        elif result.annual_return > 0.10 and result.sharpe_ratio > 1.0:
            rating = "★★★★ 良好"
        elif result.annual_return > 0.05 and result.sharpe_ratio > 0.5:
            rating = "★★★ 一般"
        elif result.annual_return > 0:
            rating = "★★ 较差"
        else:
            rating = "★ 亏损"

        report += f"  策略评级: {rating}\n"
        report += "\n════════════════════════════════════════════════════════════════\n"

        return report

    @staticmethod
    def compare_strategies(results: List) -> pd.DataFrame:
        """
        比较多个策略

        Args:
            results: BacktestResult 列表

        Returns:
            比较表格
        """
        data = []
        for result in results:
            data.append({
                'Strategy': result.strategy_name,
                'Total Return': f"{result.total_return:.2%}",
                'Annual Return': f"{result.annual_return:.2%}",
                'Sharpe Ratio': f"{result.sharpe_ratio:.2f}",
                'Max Drawdown': f"{result.max_drawdown:.2%}",
                'Win Rate': f"{result.win_rate:.2%}",
                'Trades': result.trade_count
            })

        return pd.DataFrame(data)
