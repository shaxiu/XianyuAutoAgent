#!/usr/bin/env python3
"""
修复数据库中的日期问题
"""

import os
import sys
import sqlite3
from datetime import datetime

# 添加项目根目录到系统路径
ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(ROOT_DIR)

# 数据库路径
DB_PATH = os.path.join(ROOT_DIR, "data", "xianyu_messages.db")

def fix_dates():
    """修复数据库中的日期问题"""
    try:
        # 确保数据目录存在
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"连接到数据库: {DB_PATH}")
        
        # 获取当前时间
        current_time = datetime.now().isoformat()
        
        # 查看数据库中的日期
        cursor.execute("SELECT id, start_time, last_update FROM conversations")
        for row in cursor.fetchall():
            print(f"会话 {row['id']}: start_time={row['start_time']}, last_update={row['last_update']}")
        
        # 修复会话表中的日期
        cursor.execute("""
            UPDATE conversations 
            SET start_time = ?, 
                last_update = ?
        """, (current_time, current_time))
        
        affected_rows = cursor.rowcount
        print(f"修复了 {affected_rows} 条会话记录的日期")
        
        # 修复消息表中的日期
        cursor.execute("""
            UPDATE messages 
            SET timestamp = ?
        """, (current_time,))
        
        affected_rows = cursor.rowcount
        print(f"修复了 {affected_rows} 条消息记录的日期")
        
        # 提交更改
        conn.commit()
        
        # 检查是否还有未来日期
        cursor.execute("SELECT id, start_time, last_update FROM conversations")
        future_dates = 0
        for row in cursor.fetchall():
            print(f"修复后会话 {row['id']}: start_time={row['start_time']}, last_update={row['last_update']}")
            try:
                start_time = datetime.fromisoformat(row['start_time'].replace(' ', 'T'))
                if start_time > datetime.now():
                    future_dates += 1
            except:
                pass
        
        if future_dates > 0:
            print(f"警告: 仍有 {future_dates} 条会话记录含有未来日期")
        else:
            print("所有会话记录的日期已修复")
        
        cursor.execute("SELECT id, timestamp FROM messages LIMIT 5")
        future_dates = 0
        for row in cursor.fetchall():
            print(f"消息 {row['id']}: timestamp={row['timestamp']}")
            try:
                timestamp = datetime.fromisoformat(row['timestamp'].replace(' ', 'T'))
                if timestamp > datetime.now():
                    future_dates += 1
            except:
                pass
        
        if future_dates > 0:
            print(f"警告: 仍有 {future_dates} 条消息记录含有未来日期")
        else:
            print("所有消息记录的日期已修复")
        
        # 关闭连接
        conn.close()
        print("数据库连接已关闭")
        
    except Exception as e:
        print(f"修复日期时出错: {e}")

if __name__ == "__main__":
    fix_dates() 