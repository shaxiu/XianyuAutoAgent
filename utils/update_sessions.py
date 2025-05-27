#!/usr/bin/env python3
"""
会话状态更新脚本

用于将长时间未更新的会话标记为已完成。
可以从命令行直接运行，也可以设置为定时任务。
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import sqlite3
from loguru import logger

# 确定项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# 添加项目根目录到Python路径
sys.path.append(project_root)

# 设置日志
logger.add(
    os.path.join(project_root, "logs", "update_sessions.log"),
    rotation="1 day",
    level="INFO"
)

def update_session_status(db_path, hours=1):
    """
    将超过指定时间未更新的会话标记为已完成
    
    Args:
        db_path: 数据库文件路径
        hours: 小时数，超过这个时间未更新的会话将被标记为已完成
        
    Returns:
        int: 更新的会话数量
    """
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return 0
    
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 计算截止时间
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 查找所有需要更新的会话
        cursor.execute(
            """
            SELECT id, user_id, item_id, last_update 
            FROM conversations 
            WHERE status = 'active' AND datetime(last_update) < datetime(?) 
            """,
            (cutoff_time,)
        )
        
        inactive_sessions = cursor.fetchall()
        
        if not inactive_sessions:
            logger.info(f"没有找到超过{hours}小时未更新的活跃会话")
            return 0
        
        # 更新会话状态
        session_ids = [session['id'] for session in inactive_sessions]
        placeholders = ', '.join(['?' for _ in session_ids])
        
        cursor.execute(
            f"""
            UPDATE conversations 
            SET status = 'completed' 
            WHERE id IN ({placeholders})
            """,
            session_ids
        )
        
        conn.commit()
        
        # 记录详细信息
        for session in inactive_sessions:
            logger.info(
                f"会话已标记为已完成: ID={session['id']}, 用户={session['user_id']}, "
                f"商品={session['item_id']}, 最后更新={session['last_update']}"
            )
        
        updated_count = len(inactive_sessions)
        logger.info(f"已将 {updated_count} 个超过 {hours} 小时未更新的会话标记为已完成")
        
        # 获取更新后的统计信息
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        
        logger.info(f"总会话数: {total}, 已完成会话数: {completed}")
        
        return updated_count
    
    except Exception as e:
        logger.error(f"更新会话状态时出错: {e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="更新会话状态")
    parser.add_argument(
        "--db-path", 
        default=os.path.join(project_root, "data", "chat_history.db"),
        help="数据库文件路径"
    )
    parser.add_argument(
        "--hours", 
        type=float, 
        default=1.0,
        help="超过多少小时未更新的会话将被标记为已完成"
    )
    
    args = parser.parse_args()
    
    # 执行更新
    updated_count = update_session_status(args.db_path, args.hours)
    
    print(f"已将 {updated_count} 个超过 {args.hours} 小时未更新的会话标记为已完成")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 