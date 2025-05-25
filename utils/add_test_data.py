#!/usr/bin/env python3
"""
用于向数据库添加测试数据的工具脚本
"""

import os
import sys
import json
from datetime import datetime, timedelta
import random

# 添加项目根目录到系统路径
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from utils.db_manager import DatabaseManager

# 测试用户数据
TEST_USERS = [
    {"user_id": "test_user_1", "name": "测试用户1"},
    {"user_id": "test_user_2", "name": "测试用户2"},
    {"user_id": "test_user_3", "name": "测试用户3"}
]

# 测试商品数据
TEST_ITEMS = [
    {
        "item_id": "test_item_1",
        "title": "测试商品1",
        "price": 199.0,
        "description": "这是一个测试商品描述，用于测试消息显示功能。",
        "soldPrice": 199.0,
        "desc": "这是一个测试商品描述，用于测试消息显示功能。"
    },
    {
        "item_id": "test_item_2",
        "title": "测试商品2",
        "price": 299.0,
        "description": "这是另一个测试商品描述，价格更高一些。",
        "soldPrice": 299.0,
        "desc": "这是另一个测试商品描述，价格更高一些。"
    }
]

# 测试对话内容
TEST_CONVERSATIONS = [
    {
        "user_id": "test_user_1",
        "item_id": "test_item_1",
        "messages": [
            {"role": "user", "content": "你好，这个商品还有吗？"},
            {"role": "assistant", "content": "您好，是的，这个商品还有库存。有什么可以帮到您的吗？"},
            {"role": "user", "content": "可以便宜一点吗？"},
            {"role": "assistant", "content": "这个商品的价格是199元，已经是很优惠的价格了。我可以给您一个小折扣，190元如何？", "intent": "price"},
            {"role": "user", "content": "能再便宜一点吗？170怎么样？"},
            {"role": "assistant", "content": "非常抱歉，170元的价格有点低了。考虑到商品的品质和成本，我最多可以降到185元，这是我能给出的最低价格了。", "intent": "price"},
            {"role": "user", "content": "好吧，那就185元吧。"},
            {"role": "assistant", "content": "谢谢您的理解！185元成交。您可以点击确认购买，然后按照系统提示完成付款。如果有任何问题，随时联系我。"}
        ]
    },
    {
        "user_id": "test_user_2",
        "item_id": "test_item_2",
        "messages": [
            {"role": "user", "content": "这个商品是全新的吗？"},
            {"role": "assistant", "content": "您好，是的，这是全新未拆封的商品，包装完好。"},
            {"role": "user", "content": "有什么颜色可选？"},
            {"role": "assistant", "content": "这款商品有黑色、白色和蓝色三种颜色可选，目前三种颜色都有库存。"}
        ]
    }
]

def add_test_data():
    """添加测试数据到数据库"""
    db_manager = DatabaseManager()
    
    try:
        print("开始添加测试数据...")
        
        # 添加用户
        for user in TEST_USERS:
            db_manager.save_user(user["user_id"])
            print(f"添加用户: {user['user_id']}")
        
        # 添加商品
        for item in TEST_ITEMS:
            db_manager.save_item(item["item_id"], item)
            print(f"添加商品: {item['item_id']} - {item['title']}")
        
        # 添加会话和消息
        for conv in TEST_CONVERSATIONS:
            user_id = conv["user_id"]
            item_id = conv["item_id"]
            
            # 创建会话
            conversation_id = db_manager.get_or_create_conversation(user_id, item_id)
            print(f"创建会话: ID={conversation_id}, 用户={user_id}, 商品={item_id}")
            
            # 计算议价次数
            bargain_count = sum(1 for msg in conv["messages"] if msg.get("intent") == "price")
            
            # 更新议价次数
            for _ in range(bargain_count):
                db_manager.increment_bargain_count(conversation_id)
            
            # 添加消息
            base_time = datetime.now() - timedelta(hours=2)
            
            for i, msg in enumerate(conv["messages"]):
                # 计算消息时间，每条消息间隔1-5分钟
                msg_time = base_time + timedelta(minutes=(i * random.randint(1, 5)))
                
                # 保存消息
                msg_id = db_manager.save_message(
                    conversation_id, 
                    msg["role"], 
                    msg["content"], 
                    msg.get("intent")
                )
                
                # 更新消息时间戳
                cursor = db_manager.connection.cursor()
                cursor.execute(
                    "UPDATE messages SET timestamp = ? WHERE id = ?",
                    (msg_time.isoformat(), msg_id)
                )
                db_manager.connection.commit()
                
                print(f"添加消息: ID={msg_id}, 角色={msg['role']}, 内容={msg['content'][:30]}...")
        
        print("测试数据添加完成！")
    except Exception as e:
        print(f"添加测试数据失败: {e}")
    finally:
        db_manager.close()

if __name__ == "__main__":
    add_test_data() 