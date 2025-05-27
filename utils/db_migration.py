#!/usr/bin/env python3
"""
数据库迁移脚本：将数据从xianyu_messages.db迁移到chat_history.db
"""
import sqlite3
import os
import json
from datetime import datetime
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_directory(path):
    """确保目录存在"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
def create_tables_in_new_db(conn):
    """在新数据库中创建所需的表结构"""
    cursor = conn.cursor()
    
    # 创建users表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP,
        conversation_count INTEGER DEFAULT 1
    )
    ''')
    
    # 创建items表
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
    
    # 创建conversations表
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
    
    # 创建messages表
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
    
    conn.commit()
    logger.info("在新数据库中创建了所需表结构")

def migrate_data(source_db_path, target_db_path):
    """将数据从源数据库迁移到目标数据库"""
    # 确保目录存在
    ensure_directory(target_db_path)
    
    # 连接数据库
    source_conn = sqlite3.connect(source_db_path)
    source_conn.row_factory = sqlite3.Row
    
    target_conn = sqlite3.connect(target_db_path)
    target_conn.row_factory = sqlite3.Row
    
    # 在目标数据库中创建表结构
    create_tables_in_new_db(target_conn)
    
    try:
        # 迁移 users 表
        logger.info("正在迁移users表...")
        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()
        
        source_cursor.execute("SELECT * FROM users")
        users = source_cursor.fetchall()
        
        for user in users:
            target_cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, first_seen, last_seen, conversation_count) VALUES (?, ?, ?, ?)",
                (user["user_id"], user["first_seen"], user["last_seen"], user["conversation_count"])
            )
        
        target_conn.commit()
        logger.info(f"成功迁移 {len(users)} 条用户数据")
        
        # 迁移 items 表
        logger.info("正在迁移items表...")
        source_cursor.execute("SELECT * FROM items")
        items = source_cursor.fetchall()
        
        for item in items:
            target_cursor.execute(
                "INSERT OR REPLACE INTO items (item_id, title, price, description, added_time, data) VALUES (?, ?, ?, ?, ?, ?)",
                (item["item_id"], item["title"], item["price"], item["description"], item["added_time"], item["data"])
            )
        
        target_conn.commit()
        logger.info(f"成功迁移 {len(items)} 条商品数据")
        
        # 迁移 conversations 表
        logger.info("正在迁移conversations表...")
        source_cursor.execute("SELECT * FROM conversations")
        conversations = source_cursor.fetchall()
        
        for conv in conversations:
            target_cursor.execute(
                """INSERT OR REPLACE INTO conversations 
                   (id, user_id, item_id, start_time, last_update, bargain_count, status) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (conv["id"], conv["user_id"], conv["item_id"], conv["start_time"], 
                 conv["last_update"], conv["bargain_count"], conv["status"])
            )
        
        target_conn.commit()
        logger.info(f"成功迁移 {len(conversations)} 条会话数据")
        
        # 迁移 messages 表
        logger.info("正在迁移messages表...")
        source_cursor.execute("SELECT * FROM messages")
        messages = source_cursor.fetchall()
        
        for msg in messages:
            target_cursor.execute(
                """INSERT OR REPLACE INTO messages 
                   (id, conversation_id, role, content, timestamp, intent) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg["id"], msg["conversation_id"], msg["role"], 
                 msg["content"], msg["timestamp"], msg["intent"])
            )
        
        target_conn.commit()
        logger.info(f"成功迁移 {len(messages)} 条消息数据")
        
        return True
    except sqlite3.Error as e:
        logger.error(f"数据迁移失败: {e}")
        return False
    finally:
        source_conn.close()
        target_conn.close()

def main():
    """主函数"""
    # 获取脚本所在目录
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    
    # 数据库路径
    source_db_path = os.path.join(project_root, "data", "xianyu_messages.db")
    target_db_path = os.path.join(project_root, "data", "chat_history.db")
    
    # 备份目标数据库（如果存在）
    if os.path.exists(target_db_path):
        backup_path = f"{target_db_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"备份现有的chat_history.db到{backup_path}")
        try:
            os.rename(target_db_path, backup_path)
        except OSError as e:
            logger.error(f"备份数据库失败: {e}")
            sys.exit(1)
    
    # 执行数据迁移
    logger.info(f"开始数据迁移: {source_db_path} -> {target_db_path}")
    if migrate_data(source_db_path, target_db_path):
        logger.info("数据库迁移成功完成!")
    else:
        logger.error("数据库迁移失败!")
        sys.exit(1)

if __name__ == "__main__":
    main() 