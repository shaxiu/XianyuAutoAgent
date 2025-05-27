#!/usr/bin/env python3
"""
修复数据库中的日期格式问题
"""

import os
import sys
import sqlite3
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "chat_history.db")

def fix_dates():
    """修复数据库中的日期格式"""
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        sys.exit(1)
    
    logger.info(f"连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 查询并修复conversations表中的last_update字段
        logger.info("修复conversations表中的last_update字段...")
        cursor.execute("SELECT id, last_update FROM conversations")
        conversations = cursor.fetchall()
        
        updates = 0
        for conv in conversations:
            if conv['last_update'] and ' ' in conv['last_update']:
                new_date = conv['last_update'].replace(' ', 'T')
                cursor.execute("UPDATE conversations SET last_update = ? WHERE id = ?", (new_date, conv['id']))
                updates += 1
        
        logger.info(f"已修复 {updates} 条会话日期记录")
        
        # 查询并修复messages表中的timestamp字段
        logger.info("修复messages表中的timestamp字段...")
        cursor.execute("SELECT id, timestamp FROM messages")
        messages = cursor.fetchall()
        
        updates = 0
        for msg in messages:
            if msg['timestamp'] and ' ' in msg['timestamp']:
                new_date = msg['timestamp'].replace(' ', 'T')
                cursor.execute("UPDATE messages SET timestamp = ? WHERE id = ?", (new_date, msg['id']))
                updates += 1
        
        logger.info(f"已修复 {updates} 条消息日期记录")
        
        conn.commit()
        logger.info("日期修复完成")
        
    except sqlite3.Error as e:
        logger.error(f"修复日期时出错: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    fix_dates() 