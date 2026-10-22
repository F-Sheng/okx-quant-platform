"""
配置加载模块
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Config:
    """配置管理器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 默认路径
            config_path = Path(__file__).parent.parent / 'config' / 'settings.yaml'

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"配置文件加载成功: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项,支持点号路径如 'exchange.api_key'"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def exchange_config(self) -> Dict:
        return self.config.get('exchange', {})

    @property
    def general_config(self) -> Dict:
        return self.config.get('general', {})

    @property
    def basis_arbitrage_config(self) -> Dict:
        return self.config.get('basis_arbitrage', {})

    @property
    def pair_trading_config(self) -> Dict:
        return self.config.get('pair_trading', {})

    @property
    def market_making_config(self) -> Dict:
        return self.config.get('market_making', {})

    @property
    def sentiment_config(self) -> Dict:
        return self.config.get('sentiment', {})

    @property
    def risk_management_config(self) -> Dict:
        return self.config.get('risk_management', {})

    @property
    def backtest_config(self) -> Dict:
        return self.config.get('backtest', {})


# 全局配置实例
config = Config()
