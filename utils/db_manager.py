import sqlite3
import os
import json
from datetime import datetime
from loguru import logger
import threading

class DatabaseManager:
    """SQLite3数据库管理类，用于存储闲鱼消息记录"""
    
    def __init__(self, db_path="data/xianyu_messages.db"):
        """初始化数据库连接"""
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()
        self.connect()
        self.create_tables()
        
    def connect(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"成功连接到数据库: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"连接数据库失败: {e}")
            raise
    
    def create_tables(self):
        """创建必要的数据表"""
        try:
            cursor = self.connection.cursor()
            
            # 用户表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                conversation_count INTEGER DEFAULT 1
            )
            ''')
            
            # 商品表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY,
                title TEXT,
                price REAL,
                description TEXT,
                added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data JSON
            )
            ''')
            
            # 会话表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                item_id TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_update TIMESTAMP,
                bargain_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (item_id) REFERENCES items (item_id)
            )
            ''')
            
            # 消息表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                intent TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
            ''')
            
            self.connection.commit()
            logger.info("数据表创建或已存在")
        except sqlite3.Error as e:
            logger.error(f"创建数据表失败: {e}")
            raise
    
    def save_user(self, user_id):
        """保存或更新用户信息"""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # 检查用户是否存在
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
                
                current_time = datetime.now().isoformat()
                
                if user:
                    # 更新现有用户
                    cursor.execute(
                        "UPDATE users SET last_seen = ?, conversation_count = conversation_count + 1 WHERE user_id = ?",
                        (current_time, user_id)
                    )
                else:
                    # 添加新用户
                    cursor.execute(
                        "INSERT INTO users (user_id, last_seen) VALUES (?, ?)",
                        (user_id, current_time)
                    )
                
                self.connection.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"保存用户信息失败: {e}")
                self.connection.rollback()
                raise
    
    def save_item(self, item_id, item_info):
        """保存商品信息"""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # 检查商品是否已存在
                cursor.execute("SELECT * FROM items WHERE item_id = ?", (item_id,))
                item = cursor.fetchone()
                
                if not item:
                    # 添加新商品
                    cursor.execute(
                        "INSERT INTO items (item_id, title, price, description, data) VALUES (?, ?, ?, ?, ?)",
                        (
                            item_id,
                            item_info.get('title', ''),
                            float(item_info.get('soldPrice', 0)),
                            item_info.get('desc', ''),
                            json.dumps(item_info, ensure_ascii=False)
                        )
                    )
                    self.connection.commit()
                
                return item_id
            except sqlite3.Error as e:
                logger.error(f"保存商品信息失败: {e}")
                self.connection.rollback()
                raise
    
    def get_or_create_conversation(self, user_id, item_id):
        """获取或创建会话记录"""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # 查找现有会话
                cursor.execute(
                    "SELECT * FROM conversations WHERE user_id = ? AND item_id = ? AND status = 'active'",
                    (user_id, item_id)
                )
                conversation = cursor.fetchone()
                
                current_time = datetime.now().isoformat()
                
                if conversation:
                    # 更新现有会话
                    cursor.execute(
                        "UPDATE conversations SET last_update = ? WHERE id = ?",
                        (current_time, conversation['id'])
                    )
                    self.connection.commit()
                    return conversation['id']
                else:
                    # 创建新会话
                    cursor.execute(
                        "INSERT INTO conversations (user_id, item_id, last_update) VALUES (?, ?, ?)",
                        (user_id, item_id, current_time)
                    )
                    self.connection.commit()
                    return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"获取或创建会话失败: {e}")
                self.connection.rollback()
                raise
    
    def increment_bargain_count(self, conversation_id):
        """增加议价次数"""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "UPDATE conversations SET bargain_count = bargain_count + 1 WHERE id = ?",
                    (conversation_id,)
                )
                self.connection.commit()
            except sqlite3.Error as e:
                logger.error(f"增加议价次数失败: {e}")
                self.connection.rollback()
                raise
    
    def save_message(self, conversation_id, role, content, intent=None):
        """保存消息记录"""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content, intent) VALUES (?, ?, ?, ?)",
                    (conversation_id, role, content, intent)
                )
                self.connection.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"保存消息记录失败: {e}")
                self.connection.rollback()
                raise
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def __del__(self):
        """析构函数，确保数据库连接被关闭"""
        self.close() 