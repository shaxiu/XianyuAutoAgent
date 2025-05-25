import base64
import json
import asyncio
import time
import os
import websockets
from loguru import logger
from dotenv import load_dotenv
from XianyuApis import XianyuApis


from utils.xianyu_utils import generate_mid, generate_uuid, trans_cookies, generate_device_id, decrypt
from utils.db_manager import DatabaseManager  # 导入数据库管理器
from XianyuAgent import XianyuReplyBot
from context_manager import ChatContextManager


class XianyuLive:
    def __init__(self, cookies_str):
        self.xianyu = XianyuApis()
        self.base_url = 'wss://wss-goofish.dingtalk.com/'
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)
        self.xianyu.session.cookies.update(self.cookies)  # 直接使用 session.cookies.update
        self.myid = self.cookies['unb']
        self.device_id = generate_device_id(self.myid)
        self.context_manager = ChatContextManager()
        self.db_manager = DatabaseManager()  # 初始化数据库管理器
        
        # 心跳相关配置
        self.heartbeat_interval = 15  # 心跳间隔15秒
        self.heartbeat_timeout = 5    # 心跳超时5秒
        self.last_heartbeat_time = 0
        self.last_heartbeat_response = 0
        self.heartbeat_task = None
        self.ws = None

    async def send_msg(self, ws, cid, toid, text):
        text = {
            "contentType": 1,
            "text": {
                "text": text
            }
        }
        text_base64 = str(base64.b64encode(json.dumps(text).encode('utf-8')), 'utf-8')
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {
                "mid": generate_mid()
            },
            "body": [
                {
                    "uuid": generate_uuid(),
                    "cid": f"{cid}@goofish",
                    "conversationType": 1,
                    "content": {
                        "contentType": 101,
                        "custom": {
                            "type": 1,
                            "data": text_base64
                        }
                    },
                    "redPointPolicy": 0,
                    "extension": {
                        "extJson": "{}"
                    },
                    "ctx": {
                        "appVersion": "1.0",
                        "platform": "web"
                    },
                    "mtags": {},
                    "msgReadStatusSetting": 1
                },
                {
                    "actualReceivers": [
                        f"{toid}@goofish",
                        f"{self.myid}@goofish"
                    ]
                }
            ]
        }
        await ws.send(json.dumps(msg))

    async def init(self, ws):
        token = self.xianyu.get_token(self.device_id)['data']['accessToken']
        msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "444e9908a51d1cb236a27862abc769c9",
                "token": token,
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid()
            }
        }
        await ws.send(json.dumps(msg))
        # 等待一段时间，确保连接注册完成
        await asyncio.sleep(1)
        msg = {"lwp": "/r/SyncStatus/ackDiff", "headers": {"mid": "5701741704675979 0"}, "body": [
            {"pipeline": "sync", "tooLong2Tag": "PNM,1", "channel": "sync", "topic": "sync", "highPts": 0,
             "pts": int(time.time() * 1000) * 1000, "seq": 0, "timestamp": int(time.time() * 1000)}]}
        await ws.send(json.dumps(msg))
        logger.info('连接注册完成')

    def is_chat_message(self, message):
        """判断是否为用户聊天消息"""
        try:
            return (
                isinstance(message, dict) 
                and "1" in message 
                and isinstance(message["1"], dict)  # 确保是字典类型
                and "10" in message["1"]
                and isinstance(message["1"]["10"], dict)  # 确保是字典类型
                and "reminderContent" in message["1"]["10"]
            )
        except Exception:
            return False

    def is_sync_package(self, message_data):
        """判断是否为同步包消息"""
        try:
            return (
                isinstance(message_data, dict)
                and "body" in message_data
                and "syncPushPackage" in message_data["body"]
                and "data" in message_data["body"]["syncPushPackage"]
                and len(message_data["body"]["syncPushPackage"]["data"]) > 0
            )
        except Exception:
            return False

    def is_typing_status(self, message):
        """判断是否为用户正在输入状态消息"""
        try:
            return (
                isinstance(message, dict)
                and "1" in message
                and isinstance(message["1"], list)
                and len(message["1"]) > 0
                and isinstance(message["1"][0], dict)
                and "1" in message["1"][0]
                and isinstance(message["1"][0]["1"], str)
                and "@goofish" in message["1"][0]["1"]
            )
        except Exception:
            return False

    async def handle_message(self, message_data, websocket):
        """处理所有类型的消息"""
        try:

            try:
                message = message_data
                ack = {
                    "code": 200,
                    "headers": {
                        "mid": message["headers"]["mid"] if "mid" in message["headers"] else generate_mid(),
                        "sid": message["headers"]["sid"] if "sid" in message["headers"] else '',
                    }
                }
                if 'app-key' in message["headers"]:
                    ack["headers"]["app-key"] = message["headers"]["app-key"]
                if 'ua' in message["headers"]:
                    ack["headers"]["ua"] = message["headers"]["ua"]
                if 'dt' in message["headers"]:
                    ack["headers"]["dt"] = message["headers"]["dt"]
                await websocket.send(json.dumps(ack))
            except Exception as e:
                pass

            # 如果不是同步包消息，直接返回
            if not self.is_sync_package(message_data):
                return

            # 获取并解密数据
            sync_data = message_data["body"]["syncPushPackage"]["data"][0]
            
            # 检查是否有必要的字段
            if "data" not in sync_data:
                logger.debug("同步包中无data字段")
                return

            # 解密数据
            try:
                data = sync_data["data"]
                try:
                    data = base64.b64decode(data).decode("utf-8")
                    data = json.loads(data)
                    # logger.info(f"无需解密 message: {data}")
                    return
                except Exception as e:
                    # logger.info(f'加密数据: {data}')
                    decrypted_data = decrypt(data)
                    message = json.loads(decrypted_data)
            except Exception as e:
                logger.error(f"消息解密失败: {e}")
                return

            try:
                # 判断是否为订单消息,需要自行编写付款后的逻辑
                if message['3']['redReminder'] == '等待买家付款':
                    user_id = message['1'].split('@')[0]
                    user_url = f'https://www.goofish.com/personal?userId={user_id}'
                    logger.info(f'等待买家 {user_url} 付款')
                    return
                elif message['3']['redReminder'] == '交易关闭':
                    user_id = message['1'].split('@')[0]
                    user_url = f'https://www.goofish.com/personal?userId={user_id}'
                    logger.info(f'卖家 {user_url} 交易关闭')
                    return
                elif message['3']['redReminder'] == '等待卖家发货':
                    user_id = message['1'].split('@')[0]
                    user_url = f'https://www.goofish.com/personal?userId={user_id}'
                    logger.info(f'交易成功 {user_url} 等待卖家发货')
                    return

            except:
                pass

            # 判断消息类型
            if self.is_typing_status(message):
                logger.debug("用户正在输入")
                return
            elif not self.is_chat_message(message):
                logger.debug("其他非聊天消息")
                logger.debug(f"原始消息: {message}")
                return

            # 处理聊天消息
            create_time = int(message["1"]["5"])
            send_user_name = message["1"]["10"]["reminderTitle"]
            send_user_id = message["1"]["10"]["senderUserId"]
            send_message = message["1"]["10"]["reminderContent"]
            
            # 时效性验证（过滤5分钟前消息）
            if (time.time() * 1000 - create_time) > 300000:
                logger.debug("过期消息丢弃")
                return
                
            if send_user_id == self.myid:
                logger.debug("过滤自身消息")
                return
                
            url_info = message["1"]["10"]["reminderUrl"]
            item_id = url_info.split("itemId=")[1].split("&")[0] if "itemId=" in url_info else None
            
            if not item_id:
                logger.warning("无法获取商品ID")
                return
            
            # 从数据库中获取商品信息，如果不存在则从API获取并保存
            item_info = self.context_manager.get_item_info(item_id)
            if not item_info:
                logger.info(f"从API获取商品信息: {item_id}")
                api_result = self.xianyu.get_item_info(item_id)
                if 'data' in api_result and 'itemDO' in api_result['data']:
                    item_info = api_result['data']['itemDO']
                    # 保存商品信息到数据库
                    self.context_manager.save_item_info(item_id, item_info)
                    
                    # 同时保存到SQLite数据库
                    self.db_manager.save_item(item_id, item_info)
                else:
                    logger.warning(f"获取商品信息失败: {api_result}")
                    return
            else:
                logger.info(f"从数据库获取商品信息: {item_id}")
                # 确保商品信息也存在于SQLite数据库中
                self.db_manager.save_item(item_id, item_info)
                
            item_description = f"{item_info['desc']};当前商品售卖价格为:{str(item_info['soldPrice'])}"
            logger.info(f"user: {send_user_name}, 发送消息: {send_message}")
            
            # 将用户保存到数据库
            self.db_manager.save_user(send_user_id)
            
            # 获取或创建会话ID
            conversation_id = self.db_manager.get_or_create_conversation(send_user_id, item_id)
            logger.info(f"会话ID: {conversation_id}")
            
            # 添加用户消息到上下文
            self.context_manager.add_message(send_user_id, item_id, "user", send_message)
            
            # 同时保存到SQLite数据库
            user_msg_id = self.db_manager.save_message(conversation_id, "user", send_message)
            logger.info(f"保存用户消息: ID={user_msg_id}, 内容={send_message[:30]}...")
            
            # 获取完整的对话上下文
            context = self.context_manager.get_context(send_user_id, item_id)
            
            # 生成回复
            bot_reply = bot.generate_reply(
                send_message,
                item_description,
                context=context
            )
            
            # 检查是否为价格意图，如果是则增加议价次数
            intent = None
            if bot.last_intent == "price":
                self.context_manager.increment_bargain_count(send_user_id, item_id)
                bargain_count = self.context_manager.get_bargain_count(send_user_id, item_id)
                logger.info(f"用户 {send_user_name} 对商品 {item_id} 的议价次数: {bargain_count}")
                
                # 同时更新SQLite数据库中的议价次数
                self.db_manager.increment_bargain_count(conversation_id)
                intent = "price"
            
            # 添加机器人回复到上下文
            self.context_manager.add_message(send_user_id, item_id, "assistant", bot_reply)
            
            # 同时保存到SQLite数据库
            bot_msg_id = self.db_manager.save_message(conversation_id, "assistant", bot_reply, intent)
            logger.info(f"保存机器人回复: ID={bot_msg_id}, 意图={intent}, 内容={bot_reply[:30]}...")
            
            logger.info(f"机器人回复: {bot_reply}")
            cid = message["1"]["2"].split('@')[0]
            await self.send_msg(websocket, cid, send_user_id, bot_reply)
            
        except Exception as e:
            logger.error(f"处理消息时发生错误: {str(e)}")
            logger.debug(f"原始消息: {message_data}")

    async def send_heartbeat(self, ws):
        """发送心跳包并等待响应"""
        try:
            heartbeat_mid = generate_mid()
            heartbeat_msg = {
                "lwp": "/!",
                "headers": {
                    "mid": heartbeat_mid
                }
            }
            await ws.send(json.dumps(heartbeat_msg))
            self.last_heartbeat_time = time.time()
            logger.debug("心跳包已发送")
            return heartbeat_mid
        except Exception as e:
            logger.error(f"发送心跳包失败: {e}")
            raise

    async def heartbeat_loop(self, ws):
        """心跳维护循环"""
        while True:
            try:
                current_time = time.time()
                
                # 检查是否需要发送心跳
                if current_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    await self.send_heartbeat(ws)
                
                # 检查上次心跳响应时间，如果超时则认为连接已断开
                if (current_time - self.last_heartbeat_response) > (self.heartbeat_interval + self.heartbeat_timeout):
                    logger.warning("心跳响应超时，可能连接已断开")
                    break
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"心跳循环出错: {e}")
                break

    async def handle_heartbeat_response(self, message_data):
        """处理心跳响应"""
        try:
            if (
                isinstance(message_data, dict)
                and "headers" in message_data
                and "mid" in message_data["headers"]
                and "code" in message_data
                and message_data["code"] == 200
            ):
                self.last_heartbeat_response = time.time()
                logger.debug("收到心跳响应")
                return True
        except Exception as e:
            logger.error(f"处理心跳响应出错: {e}")
        return False

    async def main(self):
        while True:
            try:
                headers = {
                    "Cookie": self.cookies_str,
                    "Host": "wss-goofish.dingtalk.com",
                    "Connection": "Upgrade",
                    "Pragma": "no-cache",
                    "Cache-Control": "no-cache",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                    "Origin": "https://www.goofish.com",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                }

                async with websockets.connect(self.base_url, extra_headers=headers) as websocket:
                    self.ws = websocket
                    await self.init(websocket)
                    
                    # 初始化心跳时间
                    self.last_heartbeat_time = time.time()
                    self.last_heartbeat_response = time.time()
                    
                    # 启动心跳任务
                    self.heartbeat_task = asyncio.create_task(self.heartbeat_loop(websocket))
                    
                    async for message in websocket:
                        try:
                            message_data = json.loads(message)
                            
                            # 处理心跳响应
                            if await self.handle_heartbeat_response(message_data):
                                continue
                            
                            # 发送通用ACK响应
                            if "headers" in message_data and "mid" in message_data["headers"]:
                                ack = {
                                    "code": 200,
                                    "headers": {
                                        "mid": message_data["headers"]["mid"],
                                        "sid": message_data["headers"].get("sid", "")
                                    }
                                }
                                # 复制其他可能的header字段
                                for key in ["app-key", "ua", "dt"]:
                                    if key in message_data["headers"]:
                                        ack["headers"][key] = message_data["headers"][key]
                                await websocket.send(json.dumps(ack))
                            
                            # 处理其他消息
                            await self.handle_message(message_data, websocket)
                                
                        except json.JSONDecodeError:
                            logger.error("消息解析失败")
                        except Exception as e:
                            logger.error(f"处理消息时发生错误: {str(e)}")
                            logger.debug(f"原始消息: {message}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket连接已关闭")
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    try:
                        await self.heartbeat_task
                    except asyncio.CancelledError:
                        pass
                await asyncio.sleep(5)  # 等待5秒后重连
                
            except Exception as e:
                logger.error(f"连接发生错误: {e}")
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    try:
                        await self.heartbeat_task
                    except asyncio.CancelledError:
                        pass
                await asyncio.sleep(5)  # 等待5秒后重连

    def __del__(self):
        """确保在销毁对象时关闭数据库连接"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()


if __name__ == '__main__':
    #加载环境变量 cookie
    load_dotenv()
    cookies_str = os.getenv("COOKIES_STR")
    bot = XianyuReplyBot()
    xianyuLive = XianyuLive(cookies_str)
    
    try:
        # 常驻进程
        asyncio.run(xianyuLive.main())
    except KeyboardInterrupt:
        # 优雅关闭
        logger.info("程序正在关闭...")
        xianyuLive.db_manager.close()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        xianyuLive.db_manager.close()
