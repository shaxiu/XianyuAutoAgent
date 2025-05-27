"""
会话状态管理模块

负责管理会话的状态，包括自动将长时间无响应的会话标记为已完成。
"""

import sqlite3
import os
from datetime import datetime, timedelta
from loguru import logger

class SessionManager:
    """会话状态管理器"""
    
    def __init__(self, db_path="data/chat_history.db"):
        """
        初始化会话状态管理器
        
        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """确保数据库文件存在"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
    
    def mark_inactive_sessions_completed(self, hours=1):
        """
        将指定时间内未更新的活跃会话标记为已完成
        
        Args:
            hours: 未更新的小时数，默认为1小时
            
        Returns:
            int: 更新的会话数量
        """
        try:
            conn = sqlite3.connect(self.db_path)
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
            
            return updated_count
        
        except Exception as e:
            logger.error(f"更新会话状态时出错: {e}")
            return 0
        finally:
            if conn:
                conn.close()
    
    def get_session_stats(self):
        """
        获取会话状态统计信息
        
        Returns:
            dict: 包含会话状态统计的字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取总会话数
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total = cursor.fetchone()[0]
            
            # 按状态统计会话数
            cursor.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM conversations 
                GROUP BY status
                """
            )
            
            status_counts = {row[0] or 'active': row[1] for row in cursor.fetchall()}
            
            # 获取过去24小时内活动的会话数
            cursor.execute(
                """
                SELECT COUNT(*) FROM conversations 
                WHERE datetime(last_update) > datetime('now', '-1 day')
                """
            )
            active_24h = cursor.fetchone()[0]
            
            return {
                "total": total,
                "status": status_counts,
                "active_24h": active_24h
            }
        
        except Exception as e:
            logger.error(f"获取会话统计信息时出错: {e}")
            return {}
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    # 如果直接运行此脚本，则执行会话状态更新
    import sys
    
    # 确定数据库路径
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # 使用默认路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..'))
        db_path = os.path.join(project_root, "data", "chat_history.db")
    
    # 创建会话管理器并更新会话状态
    try:
        hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1
    except ValueError:
        hours = 1
    
    manager = SessionManager(db_path)
    updated_count = manager.mark_inactive_sessions_completed(hours)
    
    stats = manager.get_session_stats()
    print(f"会话统计: 总数={stats.get('total', 0)}, 已完成={stats.get('status', {}).get('completed', 0)}")
    
    print(f"已将 {updated_count} 个超过 {hours} 小时未更新的会话标记为已完成") 