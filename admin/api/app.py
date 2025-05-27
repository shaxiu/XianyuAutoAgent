from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import sys
import logging
import threading
import time

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('admin_api')
logger.info("启动API服务器...")

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.append(project_root)
logger.info(f"项目根目录: {project_root}")
logger.info(f"Python路径: {sys.path}")

# 导入项目中的模块
try:
    logger.info("尝试导入项目模块...")
    from utils.db_manager import DatabaseManager
    logger.info("成功导入 DatabaseManager")
    try:
        from context_manager import ConversationManager
        logger.info("成功导入 ConversationManager")
    except ImportError as e:
        logger.warning(f"导入 ConversationManager 失败: {e}，但这可能不是必需的")
    
    try:
        from utils.session_manager import SessionManager
        logger.info("成功导入 SessionManager")
    except ImportError as e:
        logger.warning(f"导入 SessionManager 失败: {e}，但将在需要时创建")
except ImportError as e:
    logger.error(f"无法导入项目模块: {e}")
    logger.error("请确保路径正确，当前路径设置为:")
    for path in sys.path:
        logger.error(f" - {path}")
    raise

app = FastAPI(title="闲鱼AutoAgent管理后台API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为实际前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库管理器
db_path = os.path.join(project_root, "data", "chat_history.db")
logger.info(f"使用数据库: {db_path}")
db_manager = DatabaseManager(db_path=db_path)

# 用户设置
settings = {
    "default_model": "通义千问",
    "auto_response": True,
    "price_negotiation": {
        "enabled": True,
        "min_price_percentage": 80,
        "steps": 3
    },
    "notification": {
        "email_enabled": False,
        "email": "",
        "ding_talk_enabled": False,
        "ding_talk_webhook": ""
    }
}

# 确保日志目录存在
os.makedirs(os.path.join(os.path.dirname(__file__), '../../logs'), exist_ok=True)

# 添加定时任务相关代码
class BackgroundTasks:
    """后台任务管理器"""
    
    def __init__(self):
        self.tasks = {}
        self.stop_event = threading.Event()
    
    def start_task(self, task_name, func, interval_seconds, *args, **kwargs):
        """
        启动一个定时任务
        
        Args:
            task_name: 任务名称
            func: 要执行的函数
            interval_seconds: 执行间隔（秒）
            args, kwargs: 传递给函数的参数
        """
        if task_name in self.tasks:
            logger.warning(f"任务 {task_name} 已存在，先停止旧任务")
            self.stop_task(task_name)
        
        def task_wrapper():
            while not self.stop_event.is_set():
                try:
                    logger.info(f"执行定时任务: {task_name}")
                    result = func(*args, **kwargs)
                    logger.info(f"任务 {task_name} 执行结果: {result}")
                except Exception as e:
                    logger.error(f"任务 {task_name} 执行出错: {e}")
                
                # 等待下一次执行，同时检查是否应该停止
                for _ in range(int(interval_seconds)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
        
        thread = threading.Thread(target=task_wrapper, daemon=True)
        thread.start()
        
        self.tasks[task_name] = {
            "thread": thread,
            "interval": interval_seconds,
            "function": func,
            "args": args,
            "kwargs": kwargs
        }
        
        logger.info(f"已启动定时任务: {task_name}, 间隔: {interval_seconds}秒")
        return True
    
    def stop_task(self, task_name):
        """停止指定的定时任务"""
        if task_name in self.tasks:
            # 我们不能直接停止线程，但可以通过标志位让它自行退出
            # 这里简单处理，只从任务列表中移除
            del self.tasks[task_name]
            logger.info(f"已停止任务: {task_name}")
            return True
        return False
    
    def stop_all(self):
        """停止所有定时任务"""
        self.stop_event.set()
        self.tasks.clear()
        logger.info("已停止所有定时任务")
    
    def list_tasks(self):
        """列出所有定时任务"""
        return {
            name: {
                "interval": task["interval"],
                "function": task["function"].__name__,
                "running": task["thread"].is_alive()
            }
            for name, task in self.tasks.items()
        }

# 创建后台任务管理器实例
background_tasks = BackgroundTasks()

@app.get("/")
async def root():
    return {"message": "闲鱼AutoAgent管理后台API"}

@app.get("/stats")
async def get_stats():
    """获取系统统计数据"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取总会话数
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]
        
        # 获取活跃会话数 (过去24小时有活动的会话)
        cursor.execute("""
            SELECT COUNT(*) FROM conversations 
            WHERE datetime(last_update) > datetime('now', '-1 day')
        """)
        active_conversations = cursor.fetchone()[0]
        
        # 获取已完成会话数
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE status = 'completed'")
        completed_conversations = cursor.fetchone()[0]
        
        # 获取成功议价次数
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE intent = 'price'
        """)
        successful_negotiations = cursor.fetchone()[0]
        
        # 获取平均响应时间 (暂时模拟)
        avg_response_time = 1.5
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "completed_conversations": completed_conversations,
            "successful_negotiations": successful_negotiations,
            "avg_response_time": avg_response_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")

@app.get("/conversations")
async def get_conversations(limit: int = 10, offset: int = 0):
    """获取对话列表"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取会话总数
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total = cursor.fetchone()[0]
        
        logger.info(f"数据库中有 {total} 条会话记录")
        
        # 获取会话列表 - 增加更多详细信息
        cursor.execute("""
            SELECT c.id, c.user_id, c.item_id, c.start_time, c.last_update, c.bargain_count,
                   (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                   c.status,
                   i.title as item_title, i.price as item_price,
                   i.description as item_description
            FROM conversations c
            LEFT JOIN items i ON c.item_id = i.item_id
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        logger.info(f"查询到 {len(rows)} 条会话记录")
        
        conversations = []
        
        for row in rows:
            conv = dict(row)
            logger.info(f"处理会话: ID={conv['id']}, 用户={conv['user_id']}")
            
            # 获取每个会话的最近5条消息
            cursor.execute("""
                SELECT id, role, content, timestamp, intent
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (conv["id"],))
            
            recent_messages = []
            latest_timestamp = None
            
            for msg in cursor.fetchall():
                message_data = {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "intent": msg["intent"]
                }
                recent_messages.append(message_data)
                
                # 记录最新消息的时间戳
                if latest_timestamp is None or msg["timestamp"] > latest_timestamp:
                    latest_timestamp = msg["timestamp"]
            
            # 如果有消息，用最新消息的时间戳更新会话的 last_update
            if latest_timestamp and latest_timestamp != conv['last_update']:
                # 更新数据库中的last_update字段
                cursor.execute(
                    "UPDATE conversations SET last_update = ? WHERE id = ?",
                    (latest_timestamp, conv['id'])
                )
                conn.commit()
                # 同时更新当前返回数据中的last_update
                conv['last_update'] = latest_timestamp
            
            # 获取意图统计
            cursor.execute("""
                SELECT intent, COUNT(*) as count
                FROM messages
                WHERE conversation_id = ? AND intent IS NOT NULL
                GROUP BY intent
            """, (conv["id"],))
            
            intent_stats = {}
            for stat in cursor.fetchall():
                if stat["intent"]:
                    intent_stats[stat["intent"]] = stat["count"]
            
            conversations.append({
                "id": conv["id"],
                "user_id": conv["user_id"],
                "item_id": conv["item_id"],
                "item_title": conv["item_title"],
                "item_price": conv["item_price"],
                "item_description": conv["item_description"],
                "start_time": conv["start_time"],
                "last_update": conv["last_update"],
                "message_count": conv["message_count"],
                "bargain_count": conv["bargain_count"],
                "status": conv["status"] or "active",
                "recent_messages": recent_messages,
                "intent_stats": intent_stats
            })
        
        # 按会话的last_update时间倒序排序，确保最新的会话显示在前面
        conversations.sort(key=lambda x: x["last_update"] if x["last_update"] else "", reverse=True)
        
        return {
            "total": total,
            "conversations": conversations
        }
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@app.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """获取特定对话详情"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 首先尝试使用ID查询
        try:
            conv_id_int = int(conv_id)
            logger.info(f"使用ID查询会话: {conv_id_int}")
            cursor.execute("""
                SELECT c.*, i.title as item_title, i.price as item_price, i.description as item_description
                FROM conversations c
                LEFT JOIN items i ON c.item_id = i.item_id
                WHERE c.id = ?
            """, (conv_id_int,))
        except ValueError:
            # 如果转换失败，则尝试使用user_id查询
            logger.info(f"使用user_id查询会话: {conv_id}")
            cursor.execute("""
                SELECT c.*, i.title as item_title, i.price as item_price, i.description as item_description
                FROM conversations c
                LEFT JOIN items i ON c.item_id = i.item_id
                WHERE c.user_id = ?
                ORDER BY datetime(c.last_update) DESC
                LIMIT 1
            """, (conv_id,))
        
        conversation = cursor.fetchone()
        
        if conversation:
            # 获取消息列表
            logger.info(f"找到会话: ID={conversation['id']}, 用户={conversation['user_id']}, 商品={conversation['item_id']}")
            
            cursor.execute("""
                SELECT id, role, content, timestamp, intent
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
            """, (conversation["id"],))
            
            messages = []
            for msg in cursor.fetchall():
                messages.append({
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "intent": msg["intent"]
                })
            
            logger.info(f"获取到 {len(messages)} 条消息记录")
            
            # 检查messages为空的原因
            if len(messages) == 0:
                logger.warning(f"会话 {conversation['id']} 没有消息记录，执行额外检查")
                # 检查消息表中是否存在记录
                cursor.execute("SELECT COUNT(*) FROM messages")
                total_messages = cursor.fetchone()[0]
                logger.info(f"数据库中共有 {total_messages} 条消息记录")
                
                # 检查是否有其他会话的消息
                cursor.execute("SELECT conversation_id, COUNT(*) as count FROM messages GROUP BY conversation_id")
                for row in cursor.fetchall():
                    logger.info(f"会话 {row['conversation_id']} 有 {row['count']} 条消息")
            
            result = {
                "id": conversation["id"],
                "user_id": conversation["user_id"],
                "item_id": conversation["item_id"],
                "item_title": conversation["item_title"],
                "item_price": conversation["item_price"],
                "item_description": conversation["item_description"],
                "start_time": conversation["start_time"],
                "last_update": conversation["last_update"],
                "bargain_count": conversation["bargain_count"],
                "status": conversation["status"],
                "messages": messages
            }
            
            return result
        else:
            # 如果在数据库中没找到，尝试从旧的JSON文件中获取
            try:
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
                file_path = os.path.join(data_dir, f"{conv_id}.json")
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as file:
                        return json.load(file)
                else:
                    raise HTTPException(status_code=404, detail="会话不存在")
            except Exception as e:
                raise HTTPException(status_code=404, detail="会话不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取会话详情失败: {str(e)}")

@app.get("/settings")
async def get_settings():
    """获取系统设置"""
    return settings

@app.post("/settings")
async def update_settings(updated_settings: Dict[str, Any]):
    """更新系统设置"""
    global settings
    # 在实际应用中，应该验证输入并保存到数据库或配置文件
    settings.update(updated_settings)
    return {"message": "设置已更新", "settings": settings}

@app.post("/send_message/{conv_id}")
async def send_message(conv_id: str, message: str = Body(..., embed=True)):
    """手动发送消息到特定对话"""
    try:
        # 查找会话
        conn = db_manager.connection
        cursor = conn.cursor()
        
        try:
            # 首先尝试将conv_id作为整数处理
            conv_id_int = int(conv_id)
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id_int,))
        except ValueError:
            # 如果不是整数，则尝试作为user_id处理
            cursor.execute("""
                SELECT * FROM conversations 
                WHERE user_id = ? 
                ORDER BY datetime(last_update) DESC 
                LIMIT 1
            """, (conv_id,))
        
        conversation = cursor.fetchone()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        conversation_id = conversation["id"]
        
        # 保存管理员消息
        db_manager.save_message(conversation_id, "admin", message)
        
        # 更新会话最后更新时间
        cursor.execute(
            "UPDATE conversations SET last_update = ? WHERE id = ?",
            (datetime.now().isoformat(), conversation_id)
        )
        conn.commit()
        
        # 在实际应用中，这里应该调用项目中的消息发送功能
        # 例如: xianyuLive.send_message_to_user(user_id, message)
        
        return {"message": "消息已保存并发送到会话", "conversation_id": conversation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """应用启动时执行的操作"""
    logger.info("启动API服务器...")
    
    # 启动定时任务：每小时自动更新会话状态
    try:
        # 定义自动更新函数
        def auto_update_session_status():
            try:
                from utils.session_manager import SessionManager
                session_manager = SessionManager(db_path=db_manager.db_path)
                updated_count = session_manager.mark_inactive_sessions_completed(hours=1)
                return updated_count
            except ImportError:
                # 如果无法导入，使用API端点的实现
                return update_session_status._raw_fn(hours=1)
        
        # 启动定时任务，每小时执行一次
        background_tasks.start_task(
            "auto_update_session_status",
            auto_update_session_status,
            interval_seconds=3600  # 1小时
        )
        logger.info("已启动会话状态自动更新任务")
    except Exception as e:
        logger.error(f"启动定时任务失败: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行的操作"""
    # 停止所有定时任务
    background_tasks.stop_all()
    
    # 关闭数据库连接
    db_manager.close()
    logger.info("API服务器已关闭")

@app.get("/debug/messages")
async def debug_messages():
    """调试端点：获取所有消息记录"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取最近10条消息
        cursor.execute("""
            SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp, m.intent,
                   c.user_id, c.item_id
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            ORDER BY m.timestamp DESC
            LIMIT 10
        """)
        
        messages = []
        for msg in cursor.fetchall():
            messages.append({
                "id": msg["id"],
                "conversation_id": msg["conversation_id"],
                "user_id": msg["user_id"],
                "item_id": msg["item_id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "intent": msg["intent"]
            })
        
        # 获取消息总数
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        # 获取会话总数
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]
        
        return {
            "total_messages": total_messages,
            "total_conversations": total_conversations,
            "recent_messages": messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息记录失败: {str(e)}")

@app.get("/debug/conversations")
async def debug_conversations():
    """调试端点：获取所有会话记录"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取所有会话
        cursor.execute("""
            SELECT c.id, c.user_id, c.item_id, c.start_time, c.last_update, c.bargain_count,
                  (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
            FROM conversations c
            ORDER BY c.last_update DESC
        """)
        
        conversations = []
        for conv in cursor.fetchall():
            conversations.append({
                "id": conv["id"],
                "user_id": conv["user_id"],
                "item_id": conv["item_id"],
                "start_time": conv["start_time"],
                "last_update": conv["last_update"],
                "bargain_count": conv["bargain_count"],
                "message_count": conv["message_count"]
            })
        
        return {
            "total": len(conversations),
            "conversations": conversations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话记录失败: {str(e)}")

@app.get("/debug")
async def debug_info():
    """调试页面：获取系统信息"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取数据统计
        stats = {
            "database_file": db_manager.db_path,
            "tables": {}
        }
        
        # 获取表数据统计
        for table in ['users', 'items', 'conversations', 'messages']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats["tables"][table] = count
        
        # 获取最新的3条消息
        cursor.execute("""
            SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp, m.intent,
                   c.user_id, c.item_id
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            ORDER BY m.id DESC
            LIMIT 3
        """)
        
        latest_messages = []
        for msg in cursor.fetchall():
            latest_messages.append({
                "id": msg["id"],
                "conversation_id": msg["conversation_id"],
                "user_id": msg["user_id"],
                "item_id": msg["item_id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "intent": msg["intent"]
            })
        
        stats["latest_messages"] = latest_messages
        
        # 获取所有会话ID和用户ID
        cursor.execute("""
            SELECT id, user_id, item_id
            FROM conversations
            ORDER BY id DESC
        """)
        
        conversations = []
        for conv in cursor.fetchall():
            # 获取每个会话的消息数
            cursor.execute("""
                SELECT COUNT(*) FROM messages WHERE conversation_id = ?
            """, (conv["id"],))
            msg_count = cursor.fetchone()[0]
            
            conversations.append({
                "id": conv["id"],
                "user_id": conv["user_id"],
                "item_id": conv["item_id"],
                "message_count": msg_count
            })
        
        stats["conversations"] = conversations
        
        return stats
    except Exception as e:
        logger.error(f"获取调试信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取调试信息失败: {str(e)}")

@app.post("/debug/add-test-message/{conv_id}")
async def add_test_message(conv_id: int):
    """添加测试消息到指定会话"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 检查会话是否存在
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        conversation = cursor.fetchone()
        
        if not conversation:
            raise HTTPException(status_code=404, detail=f"会话 {conv_id} 不存在")
        
        # 添加测试消息
        current_time = datetime.now().isoformat()
        
        # 添加用户消息
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conv_id, "user", f"这是一条测试用户消息 - {current_time}", current_time)
        )
        
        # 添加系统回复
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conv_id, "assistant", f"这是一条测试系统回复 - {current_time}", current_time)
        )
        
        conn.commit()
        
        return {"message": f"已添加测试消息到会话 {conv_id}"}
    except Exception as e:
        logger.error(f"添加测试消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加测试消息失败: {str(e)}")

@app.post("/debug/create-test-conversation")
async def create_test_conversation():
    """创建测试会话"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        test_user_id = f"test_user_{int(datetime.now().timestamp())}"
        test_item_id = f"test_item_{int(datetime.now().timestamp())}"
        
        # 添加测试用户
        cursor.execute(
            "INSERT INTO users (user_id, last_seen) VALUES (?, ?)",
            (test_user_id, current_time)
        )
        
        # 添加测试商品
        cursor.execute(
            "INSERT INTO items (item_id, title, price, description, data) VALUES (?, ?, ?, ?, ?)",
            (
                test_item_id,
                f"测试商品 {current_time}",
                199.0,
                "这是一个测试商品描述",
                json.dumps({"title": f"测试商品 {current_time}", "soldPrice": 199.0}, ensure_ascii=False)
            )
        )
        
        # 添加测试会话
        cursor.execute(
            "INSERT INTO conversations (user_id, item_id, last_update) VALUES (?, ?, ?)",
            (test_user_id, test_item_id, current_time)
        )
        conversation_id = cursor.lastrowid
        
        # 添加测试消息
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, "user", "你好，这个商品还有吗？", current_time)
        )
        
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp, intent) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, "assistant", "您好，是的，这个商品还有库存，欢迎咨询！", current_time, None)
        )
        
        conn.commit()
        
        return {
            "message": "测试会话创建成功",
            "conversation_id": conversation_id,
            "user_id": test_user_id,
            "item_id": test_item_id
        }
    except Exception as e:
        logger.error(f"创建测试会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建测试会话失败: {str(e)}")

@app.post("/debug/reset-test-data")
async def reset_test_data():
    """重置测试数据"""
    try:
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 清空现有数据
        cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM conversations")
        cursor.execute("DELETE FROM items")
        cursor.execute("DELETE FROM users")
        
        # 添加测试用户
        cursor.execute(
            "INSERT INTO users (user_id, last_seen) VALUES (?, ?)",
            ("test_user", datetime.now().isoformat())
        )
        
        # 添加测试商品
        cursor.execute(
            "INSERT INTO items (item_id, title, price, description, data) VALUES (?, ?, ?, ?, ?)",
            (
                "test_item",
                "测试商品",
                199.0,
                "这是一个测试商品描述",
                json.dumps({"title": "测试商品", "price": 199.0}, ensure_ascii=False)
            )
        )
        
        # 添加测试会话
        cursor.execute(
            "INSERT INTO conversations (user_id, item_id, start_time, last_update, status) VALUES (?, ?, ?, ?, ?)",
            (
                "test_user",
                "test_item",
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                "active"
            )
        )
        conversation_id = cursor.lastrowid
        
        # 添加测试消息
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, "user", "你好，这个商品还有吗？", datetime.now().isoformat())
        )
        
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, "assistant", "您好，是的，这个商品还有库存，欢迎咨询！", datetime.now().isoformat())
        )
        
        conn.commit()
        
        return {
            "message": "测试数据重置成功",
            "conversation_id": conversation_id
        }
    except Exception as e:
        logger.error(f"重置测试数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置测试数据失败: {str(e)}")

@app.post("/update_session_status")
async def update_session_status(hours: float = 1.0):
    """
    将指定时间内未更新的活跃会话标记为已完成
    
    Args:
        hours: 未更新的小时数，默认为1小时
    """
    try:
        # 导入或创建会话管理器
        try:
            from utils.session_manager import SessionManager
            # 使用导入的会话管理器
            session_manager = SessionManager(db_path=db_manager.db_path)
            updated_count = session_manager.mark_inactive_sessions_completed(hours)
        except ImportError:
            # 如果无法导入，则在当前文件中定义简化版的函数
            logger.warning("无法导入SessionManager，使用简化版函数")
            
            def mark_inactive_sessions_completed(db_connection, hours=1):
                cursor = db_connection.cursor()
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
                
                db_connection.commit()
                return len(inactive_sessions)
            
            # 使用简化版函数
            updated_count = mark_inactive_sessions_completed(db_manager.connection, hours)
        
        # 获取更新后的统计信息
        conn = db_manager.connection
        cursor = conn.cursor()
        
        # 获取总会话数
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total = cursor.fetchone()[0]
        
        # 获取已完成会话数
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        
        return {
            "message": f"已将 {updated_count} 个超过 {hours} 小时未更新的会话标记为已完成",
            "updated_count": updated_count,
            "total_conversations": total,
            "completed_conversations": completed
        }
    except Exception as e:
        logger.error(f"更新会话状态时出错: {e}")
        raise HTTPException(status_code=500, detail=f"更新会话状态失败: {str(e)}")

# 添加管理定时任务的API端点
@app.get("/tasks")
async def get_tasks():
    """获取所有定时任务"""
    return {"tasks": background_tasks.list_tasks()}

@app.post("/tasks/{task_name}/start")
async def start_task(task_name: str, interval_seconds: int = 3600):
    """
    启动指定的定时任务
    
    Args:
        task_name: 任务名称
        interval_seconds: 执行间隔（秒）
    """
    if task_name == "update_session_status":
        # 定义自动更新函数，不使用异步调用
        def auto_update_session_status():
            try:
                # 直接使用会话管理器
                from utils.session_manager import SessionManager
                session_manager = SessionManager(db_path=db_manager.db_path)
                updated_count = session_manager.mark_inactive_sessions_completed(hours=1)
                return updated_count
            except Exception as e:
                logger.error(f"执行会话状态更新失败: {e}")
                return 0
        
        success = background_tasks.start_task(
            task_name,
            auto_update_session_status,
            interval_seconds
        )
        return {"success": success, "message": f"已启动任务: {task_name}"}
    else:
        raise HTTPException(status_code=400, detail=f"未知的任务: {task_name}")

@app.post("/tasks/{task_name}/stop")
async def stop_task(task_name: str):
    """停止指定的定时任务"""
    success = background_tasks.stop_task(task_name)
    if success:
        return {"success": True, "message": f"已停止任务: {task_name}"}
    else:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_name}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090) 