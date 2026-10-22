"""
数据库模块
使用 SQLite 存储交易数据
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)


class Database:
    """数据库管理器"""

    def __init__(self, db_path: str = 'data/quant.db'):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()
        logger.info(f"数据库初始化完成: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 交易记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,
                    reason TEXT,
                    order_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 持仓表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    pnl REAL DEFAULT 0,
                    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    closed_at DATETIME,
                    is_open INTEGER DEFAULT 1
                )
            ''')

            # 权益曲线表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    strategy TEXT NOT NULL,
                    capital REAL NOT NULL,
                    position_value REAL DEFAULT 0,
                    total_equity REAL NOT NULL
                )
            ''')

            # 资金费率历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS funding_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    funding_rate REAL NOT NULL,
                    annualized_return REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp)
                )
            ''')

            # 情绪数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sentiment_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    sentiment_score REAL NOT NULL,
                    confidence REAL,
                    source TEXT,
                    raw_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 策略绩效表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    date DATE NOT NULL,
                    total_pnl REAL DEFAULT 0,
                    trade_count INTEGER DEFAULT 0,
                    win_count INTEGER DEFAULT 0,
                    loss_count INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(strategy, date)
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_equity_timestamp ON equity_curve(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_funding_symbol ON funding_rates(symbol, timestamp)')

            logger.info("数据库表初始化完成")

    def save_trade(self, trade: Dict) -> int:
        """
        保存交易记录

        Args:
            trade: 交易数据

        Returns:
            记录 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (timestamp, strategy, symbol, action, price, size, fee, pnl, reason, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.get('timestamp'),
                trade.get('strategy'),
                trade.get('symbol'),
                trade.get('action'),
                trade.get('price'),
                trade.get('size'),
                trade.get('fee', 0),
                trade.get('pnl', 0),
                trade.get('reason', ''),
                trade.get('order_id')
            ))
            return cursor.lastrowid

    def save_position(self, position: Dict) -> int:
        """保存持仓记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO positions (strategy, symbol, side, size, entry_price, current_price, pnl, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                position.get('strategy'),
                position.get('symbol'),
                position.get('side'),
                position.get('size'),
                position.get('entry_price'),
                position.get('current_price'),
                position.get('pnl', 0),
                1
            ))
            return cursor.lastrowid

    def close_position(self, position_id: int, pnl: float):
        """平仓"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE positions
                SET closed_at = CURRENT_TIMESTAMP, is_open = 0, pnl = ?
                WHERE id = ?
            ''', (pnl, position_id))

    def save_equity_point(self, timestamp: datetime, strategy: str,
                         capital: float, position_value: float, total_equity: float):
        """保存权益点"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO equity_curve (timestamp, strategy, capital, position_value, total_equity)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, strategy, capital, position_value, total_equity))

    def save_funding_rate(self, symbol: str, timestamp: datetime,
                         funding_rate: float, annualized_return: float = None):
        """保存资金费率"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO funding_rates (symbol, timestamp, funding_rate, annualized_return)
                VALUES (?, ?, ?, ?)
            ''', (symbol, timestamp, funding_rate, annualized_return))

    def save_sentiment(self, symbol: str, timestamp: datetime,
                      sentiment_score: float, confidence: float,
                      source: str, raw_text: str):
        """保存情绪数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sentiment_data (symbol, timestamp, sentiment_score, confidence, source, raw_text)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (symbol, timestamp, sentiment_score, confidence, source, raw_text))

    def get_trades(self, strategy: Optional[str] = None,
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None) -> List[Dict]:
        """获取交易记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM trades WHERE 1=1'
            params = []

            if strategy:
                query += ' AND strategy = ?'
                params.append(strategy)

            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)

            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)

            query += ' ORDER BY timestamp DESC'

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_open_positions(self, strategy: Optional[str] = None) -> List[Dict]:
        """获取当前持仓"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM positions WHERE is_open = 1'
            params = []

            if strategy:
                query += ' AND strategy = ?'
                params.append(strategy)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_equity_curve(self, strategy: Optional[str] = None) -> List[Dict]:
        """获取权益曲线"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT * FROM equity_curve'
            params = []

            if strategy:
                query += ' WHERE strategy = ?'
                params.append(strategy)

            query += ' ORDER BY timestamp'

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_funding_rates(self, symbol: str, limit: int = 100) -> List[Dict]:
        """获取资金费率历史"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM funding_rates
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (symbol, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]


# 全局数据库实例
db = Database()
