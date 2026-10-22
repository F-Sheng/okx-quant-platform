"""
OKX API 客户端封装
提供统一的接口访问 OKX 交易所
"""
import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
import pandas as pd
from datetime import datetime, timedelta

try:
    import okx.Account as Account
    import okx.Trade as Trade
    import okx.MarketData as MarketData
    import okx.PublicData as PublicData
    import okx.Funding as Funding
except ImportError:
    raise ImportError("请安装 python-okx: pip install python-okx")

logger = logging.getLogger(__name__)


class OKXClient:
    """OKX 交易所客户端"""

    def __init__(self, api_key: str, secret_key: str, passphrase: str,
                 trading_mode: str = "demo"):
        """
        初始化 OKX 客户端

        Args:
            api_key: API Key
            secret_key: Secret Key
            passphrase: Passphrase
            trading_mode: 'demo' (模拟盘) 或 'live' (实盘)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

        # OKX flag: '0'=实盘, '1'=模拟盘
        self.flag = '1' if trading_mode == 'demo' else '0'

        # 初始化各个模块
        self.account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, self.flag)
        self.trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, self.flag)
        self.market_api = MarketData.MarketAPI(api_key, secret_key, passphrase, False, self.flag)
        self.public_api = PublicData.PublicAPI(api_key, secret_key, passphrase, False, self.flag)
        self.funding_api = Funding.FundingAPI(api_key, secret_key, passphrase, False, self.flag)

        logger.info(f"OKX 客户端初始化完成, 模式: {trading_mode}")

    # ==================== 账户信息 ====================

    def get_balance(self, ccy: str = "USDT") -> Dict:
        """获取账户余额"""
        try:
            result = self.account_api.get_account_balance(ccy=ccy)
            if result['code'] == '0':
                return result['data'][0]
            else:
                logger.error(f"获取余额失败: {result['msg']}")
                return {}
        except Exception as e:
            logger.error(f"获取余额异常: {e}")
            return {}

    def get_positions(self, inst_type: str = "SWAP") -> List[Dict]:
        """获取持仓信息"""
        try:
            result = self.account_api.get_positions(instType=inst_type)
            if result['code'] == '0':
                return result['data']
            return []
        except Exception as e:
            logger.error(f"获取持仓异常: {e}")
            return []

    # ==================== 行情数据 ====================

    def get_ticker(self, symbol: str) -> Dict:
        """获取最新行情"""
        try:
            result = self.market_api.get_ticker(instId=symbol)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取行情异常: {e}")
            return {}

    def get_candles(self, symbol: str, bar: str = "1H",
                    limit: int = 100, after: Optional[str] = None,
                    before: Optional[str] = None) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易对,如 BTC-USDT-SWAP
            bar: K线周期 (1m, 5m, 15m, 1H, 4H, 1D, etc.)
            limit: 返回数量
            after: 此时间之前的数据
            before: 此时间之后的数据

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            result = self.market_api.get_candlesticks(
                instId=symbol, bar=bar, limit=limit, after=after, before=before
            )
            if result['code'] == '0' and result['data']:
                df = pd.DataFrame(result['data'], columns=[
                    'timestamp', 'open', 'high', 'low', 'close',
                    'volume', 'volCcy', 'volCcyQuote', 'confirm'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取K线异常: {e}")
            return pd.DataFrame()

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        """获取订单簿"""
        try:
            result = self.market_api.get_orderbook(instId=symbol, sz=str(depth))
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取订单簿异常: {e}")
            return {}

    # ==================== 资金费率(期现套利核心) ====================

    def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取资金费率

        Returns:
            包含 fundingRate, fundingTime, nextFundingRate 等
        """
        try:
            result = self.public_api.get_funding_rate(instId=symbol)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取资金费率异常: {e}")
            return {}

    def get_funding_rate_history(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """获取资金费率历史"""
        try:
            result = self.public_api.funding_rate_history(instId=symbol, limit=limit)
            if result['code'] == '0' and result['data']:
                df = pd.DataFrame(result['data'])
                df['fundingRate'] = df['fundingRate'].astype(float)
                df['fundingTime'] = pd.to_datetime(df['fundingTime'].astype(float), unit='ms')
                return df.sort_values('fundingTime').reset_index(drop=True)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取资金费率历史异常: {e}")
            return pd.DataFrame()

    def get_mark_price(self, symbol: str) -> Dict:
        """获取标记价格"""
        try:
            result = self.public_api.get_mark_price(instId=symbol)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取标记价格异常: {e}")
            return {}

    # ==================== 交易操作 ====================

    def place_order(self, symbol: str, side: str, pos_side: str,
                    order_type: str, size: str, price: Optional[str] = None,
                    reduce_only: bool = False) -> Dict:
        """
        下单

        Args:
            symbol: 交易对
            side: buy/sell
            pos_side: long/short (双向持仓模式)
            order_type: market/limit
            size: 数量(张)
            price: 价格(limit单必须)
            reduce_only: 是否只减仓

        Returns:
            订单信息
        """
        try:
            params = {
                'instId': symbol,
                'tdMode': 'cross',  # 全仓模式
                'side': side,
                'posSide': pos_side,
                'ordType': order_type,
                'sz': size
            }

            if price and order_type == 'limit':
                params['px'] = price

            if reduce_only:
                params['reduceOnly'] = 'true'

            result = self.trade_api.place_order(**params)

            if result['code'] == '0':
                logger.info(f"下单成功: {symbol} {side} {size} @ {price or 'market'}")
                return result['data'][0]
            else:
                logger.error(f"下单失败: {result['msg']}")
                return {'error': result['msg']}
        except Exception as e:
            logger.error(f"下单异常: {e}")
            return {'error': str(e)}

    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        try:
            result = self.trade_api.cancel_order(instId=symbol, ordId=order_id)
            if result['code'] == '0':
                logger.info(f"取消订单成功: {order_id}")
                return result['data'][0]
            return {'error': result['msg']}
        except Exception as e:
            logger.error(f"取消订单异常: {e}")
            return {'error': str(e)}

    def cancel_all_orders(self, symbol: str) -> Dict:
        """取消所有订单"""
        try:
            result = self.trade_api.cancel_all_orders(instId=symbol)
            if result['code'] == '0':
                logger.info(f"取消所有订单成功: {symbol}")
                return result['data']
            return {'error': result['msg']}
        except Exception as e:
            logger.error(f"取消所有订单异常: {e}")
            return {'error': str(e)}

    def get_order(self, symbol: str, order_id: str) -> Dict:
        """获取订单详情"""
        try:
            result = self.trade_api.get_order(instId=symbol, ordId=order_id)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取订单异常: {e}")
            return {}

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取未完成订单"""
        try:
            params = {'ordType': 'live'}
            if symbol:
                params['instId'] = symbol

            result = self.trade_api.get_order_list(**params)
            if result['code'] == '0':
                return result['data']
            return []
        except Exception as e:
            logger.error(f"获取未完成订单异常: {e}")
            return []

    # ==================== 工具方法 ====================

    def get_instrument_info(self, symbol: str) -> Dict:
        """获取合约信息(合约面值、最小下单量等)"""
        try:
            result = self.public_api.get_instruments(instType='SWAP', instId=symbol)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            return {}
        except Exception as e:
            logger.error(f"获取合约信息异常: {e}")
            return {}

    def get_ticker_price(self, symbol: str) -> float:
        """获取最新价格"""
        ticker = self.get_ticker(symbol)
        return float(ticker.get('last', 0))

    def get_usd_balance(self) -> float:
        """获取 USDT 余额"""
        balance = self.get_balance('USDT')
        if balance and 'details' in balance:
            for detail in balance['details']:
                if detail.get('ccy') == 'USDT':
                    return float(detail.get('availBal', 0))
        return 0.0
