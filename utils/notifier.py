import os
import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
from loguru import logger
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

import lark_oapi as lark
from lark_oapi.api.im.v1 import *



class BaseNotifier(ABC):
    """通知器基类"""
    
    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        """
        发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
            
        Returns:
            bool: 是否发送成功
        """
        pass


class FeishuNotifier(BaseNotifier):
    """飞书通知器"""
    
    def __init__(self, app_id: str, app_secret: str, receive_id_type: str, receive_id: str):
        """
        初始化飞书通知器
        
        Args:
            app_id: 飞书应用的App ID
            app_secret: 飞书应用的App Secret
            receive_id_type: 接收者ID类型，可选值: "open_id", "user_id", "union_id", "email", "chat_id"
            receive_id: 接收者ID
        """
        try:
            self.client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
            self.receive_id_type = receive_id_type
            self.receive_id = receive_id
        except ImportError:
            logger.error("未安装lark_oapi库，请使用pip install lark_oapi安装")
            raise
    
    def send(self, title: str, content: str) -> bool:
        try:           
            # 构建消息请求
            req_content = json.dumps({"text": title + "\n" + content})
            req: CreateMessageRequest = CreateMessageRequest.builder() \
                    .receive_id_type(self.receive_id_type) \
                    .request_body(CreateMessageRequestBody.builder()
                        .receive_id(self.receive_id)
                        .msg_type("text")
                        .content(req_content)
                        .build()) \
                    .build()
            
            logger.debug(f"Receive ID : {self.receive_id}")
            # 发送消息
            resp: CreateMessageResponse = self.client.im.v1.message.create(req)
            
            if resp.success():
                logger.info(f"飞书通知发送成功: {title}")
                return True
            else:
                logger.error(f"飞书通知发送失败: {resp.msg}")
                return False
        except Exception as e:
            logger.error(f"飞书通知发送失败: {e}")
            return False


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifiers: List[BaseNotifier] = []
    
    def add_notifier(self, notifier: BaseNotifier):
        """添加通知器"""
        self.notifiers.append(notifier)
        
    def notify(self, title: str, content: str) -> bool:
        """发送通知到所有通知器"""
        success = False
        for notifier in self.notifiers:
            if notifier.send(title, content):
                success = True
        return success
    
    def notify_error(self, error_type: str, error_msg: str, details: str = "") -> bool:
        """发送错误通知"""
        title = f"闲鱼自动客服系统错误: {error_type}"
        content = f"错误信息: {error_msg}\n\n详细信息: {details}"
        return self.notify(title, content)
    
    def notify_cookie_expired(self) -> bool:
        """发送Cookie过期通知"""
        title = "闲鱼自动客服系统警告: Cookie已过期"
        content = "您的闲鱼Cookie已过期，请尽快更新Cookie以保持系统正常运行。"
        return self.notify(title, content)
    
    def notify_system_start(self) -> bool:
        """发送系统启动通知"""
        title = "闲鱼自动客服系统: 已启动"
        content = f"系统已成功启动，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.notify(title, content) 