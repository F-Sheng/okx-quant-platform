"""
情绪分析策略
基于新闻和社交媒体情绪的交易策略
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import json

from strategies.base_strategy import BaseStrategy, Signal
from execution.okx_client import OKXClient


logger = logging.getLogger(__name__)


@dataclass
class SentimentSignal:
    """情绪信号"""
    symbol: str
    sentiment_score: float  # -1.0 到 1.0
    confidence: float  # 0.0 到 1.0
    source: str
    timestamp: datetime
    raw_text: str = ''


class SentimentTradingStrategy(BaseStrategy):
    """
    情绪分析交易策略

    原理:
    - 收集新闻、社交媒体数据
    - 使用 DeepSeek API 进行情绪分析
    - 根据情绪分数生成交易信号

    情绪分数:
    - -1.0: 极度恐慌
    -  0.0: 中性
    -  1.0: 极度贪婪

    交易逻辑:
    - 极度恐慌时买入(逆向)
    - 极度贪婪时卖出(逆向)
    """

    def __init__(self, config: Dict, okx_client: OKXClient):
        super().__init__("SentimentTrading", config)
        self.client = okx_client

        # 策略参数
        self.symbols = config.get('symbols', ['BTC', 'ETH'])
        self.deepseek_api_key = config.get('deepseek_api_key', '')
        self.check_interval = config.get('check_interval', 1800)  # 30分钟

        # 情绪数据
        self.sentiment_history: Dict[str, List[SentimentSignal]] = {}
        self.current_sentiment: Dict[str, float] = {}

        # 交易参数
        self.sentiment_threshold_buy = -0.5  # 买入阈值
        self.sentiment_threshold_sell = 0.5  # 卖出阈值
        self.position_size_usd = 1000

        self.last_check_time = 0

    def initialize(self):
        """初始化策略"""
        self.logger.info("情绪分析策略初始化...")

        # 初始化 DeepSeek 客户端
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=self.deepseek_api_key,
                base_url="https://api.deepseek.com"
            )
            self.logger.info("DeepSeek API 客户端初始化成功")
        except Exception as e:
            self.logger.error(f"DeepSeek API 初始化失败: {e}")
            self.llm_client = None

    def collect_sentiment_data(self, symbol: str) -> List[Dict]:
        """
        收集情绪数据

        Args:
            symbol: 资产符号 (如 BTC, ETH)

        Returns:
            情绪数据列表
        """
        # 这里简化实现,实际应该爬取新闻、Twitter等
        # 可以接入:
        # 1. Twitter API
        # 2. 新闻 API (如 NewsAPI, CryptoPanic)
        # 3. Telegram 群组
        # 4. Reddit

        mock_data = [
            {
                'text': f'{symbol} showing strong momentum, institutional buying increasing',
                'source': 'mock_news',
                'timestamp': datetime.now()
            },
            {
                'text': f'Market volatility high, {symbol} faces regulatory uncertainty',
                'source': 'mock_twitter',
                'timestamp': datetime.now()
            }
        ]

        return mock_data

    def analyze_sentiment(self, text: str) -> Optional[Dict]:
        """
        使用 DeepSeek 分析情绪

        Args:
            text: 文本

        Returns:
            情绪分析结果
        """
        if not self.llm_client:
            return None

        try:
            prompt = f"""Analyze the sentiment of this crypto market text. Return JSON with:
- sentiment_score: float from -1.0 (very bearish) to 1.0 (very bullish)
- confidence: float from 0.0 to 1.0
- reasoning: brief explanation

Text: {text}

Return only valid JSON."""

            response = self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a crypto market sentiment analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            result_text = response.choices[0].message.content

            # 解析 JSON
            result = json.loads(result_text)
            return result

        except Exception as e:
            self.logger.error(f"情绪分析异常: {e}")
            return None

    def calculate_aggregate_sentiment(self, symbol: str) -> float:
        """
        计算综合情绪分数

        Args:
            symbol: 资产符号

        Returns:
            综合情绪分数
        """
        if symbol not in self.sentiment_history:
            return 0.0

        signals = self.sentiment_history[symbol]
        if not signals:
            return 0.0

        # 加权平均(最近的权重更高)
        total_weight = 0
        weighted_sum = 0

        for i, signal in enumerate(signals):
            weight = (i + 1) / len(signals)  # 线性权重
            weighted_sum += signal.sentiment_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

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

        # 检查每个资产
        for symbol in self.symbols:
            # 收集情绪数据
            sentiment_data = self.collect_sentiment_data(symbol)

            # 分析情绪
            for data in sentiment_data:
                result = self.analyze_sentiment(data['text'])
                if result:
                    sentiment_signal = SentimentSignal(
                        symbol=symbol,
                        sentiment_score=result.get('sentiment_score', 0),
                        confidence=result.get('confidence', 0),
                        source=data['source'],
                        timestamp=data['timestamp'],
                        raw_text=data['text']
                    )

                    if symbol not in self.sentiment_history:
                        self.sentiment_history[symbol] = []
                    self.sentiment_history[symbol].append(sentiment_signal)

            # 计算综合情绪
            aggregate_sentiment = self.calculate_aggregate_sentiment(symbol)
            self.current_sentiment[symbol] = aggregate_sentiment

            self.logger.info(f"{symbol} 情绪分数: {aggregate_sentiment:.3f}")

            # 生成交易信号
            trading_symbol = f"{symbol}-USDT"

            if aggregate_sentiment < self.sentiment_threshold_buy:
                signals.append(Signal(
                    symbol=trading_symbol,
                    action='buy',
                    size=self.position_size_usd,
                    reason=f"极度恐慌,逆向买入,情绪分数: {aggregate_sentiment:.3f}"
                ))

            elif aggregate_sentiment > self.sentiment_threshold_sell:
                signals.append(Signal(
                    symbol=trading_symbol,
                    action='sell',
                    size=self.position_size_usd,
                    reason=f"极度贪婪,逆向卖出,情绪分数: {aggregate_sentiment:.3f}"
                ))

        return signals

    def on_order_filled(self, order: Dict):
        """订单成交回调"""
        symbol = order.get('symbol', '')
        action = order.get('action', '')
        size = order.get('size', 0)

        self.logger.info(f"情绪策略订单成交: {action} {symbol} {size}")

    def get_performance(self) -> Dict:
        """获取绩效统计"""
        perf = super().get_performance()
        perf['current_sentiment'] = self.current_sentiment.copy()
        perf['sentiment_data_count'] = sum(len(signals) for signals in self.sentiment_history.values())
        return perf
