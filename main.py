import base64
import json
import asyncio
import time
import os
import websockets
from loguru import logger
from dotenv import load_dotenv
from XianyuApis import XianyuApis
import sys


from utils.xianyu_utils import (
    generate_mid,
    generate_uuid,
    trans_cookies,
    generate_device_id,
    decrypt,
)
from XianyuAgent import XianyuReplyBot
from context_manager import ChatContextManager


class XianyuLive:
    def __init__(self, cookies_str):
        self.xianyu = XianyuApis()
        self.base_url = "wss://wss-goofish.dingtalk.com/"
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)
        self.xianyu.session.cookies.update(
            self.cookies
        )  # 直接使用 session.cookies.update
        self.myid = self.cookies["unb"]
        self.device_id = generate_device_id(self.myid)
        self.context_manager = ChatContextManager()

        # 心跳相关配置
        self.heartbeat_interval = int(
            os.getenv("HEARTBEAT_INTERVAL", "15")
        )  # 心跳间隔，默认15秒
        self.heartbeat_timeout = int(
            os.getenv("HEARTBEAT_TIMEOUT", "5")
        )  # 心跳超时，默认5秒
        self.last_heartbeat_time = 0
        self.last_heartbeat_response = 0
        self.heartbeat_task = None
        self.ws = None

        # Token刷新相关配置
        self.token_refresh_interval = int(
            os.getenv("TOKEN_REFRESH_INTERVAL", "3600")
        )  # Token刷新间隔，默认1小时
        self.token_retry_interval = int(
            os.getenv("TOKEN_RETRY_INTERVAL", "300")
        )  # Token重试间隔，默认5分钟
        self.last_token_refresh_time = 0
        self.current_token = None
        self.token_refresh_task = None
        self.connection_restart_flag = False  # 连接重启标志

        # 人工接管相关配置
        self.manual_mode_conversations = set()  # 存储处于人工接管模式的会话ID
        self.manual_mode_timeout = int(
            os.getenv("MANUAL_MODE_TIMEOUT", "3600")
        )  # 人工接管超时时间，默认1小时
        self.manual_mode_timestamps = {}  # 记录进入人工模式的时间

        # 消息过期时间配置
        self.message_expire_time = int(
            os.getenv("MESSAGE_EXPIRE_TIME", "300000")
        )  # 消息过期时间，默认5分钟

        # 人工接管关键词，从环境变量读取
        self.toggle_keywords = os.getenv("TOGGLE_KEYWORDS", "。")

    async def refresh_token(self):
        """刷新token"""
        try:
            logger.info("开始刷新token...")

            # 获取新token（如果Cookie失效，get_token会直接退出程序）
            token_result = self.xianyu.get_token(self.device_id)
            if "data" in token_result and "accessToken" in token_result["data"]:
                new_token = token_result["data"]["accessToken"]
                self.current_token = new_token
                self.last_token_refresh_time = time.time()
                logger.info("Token刷新成功")
                return new_token
            else:
                logger.error(f"Token刷新失败: {token_result}")
                return None

        except Exception as e:
            logger.error(f"Token刷新异常: {str(e)}")
            return None

    async def token_refresh_loop(self):
        """Token刷新循环"""
        while True:
            try:
                current_time = time.time()

                # 检查是否需要刷新token
                if (
                    current_time - self.last_token_refresh_time
                    >= self.token_refresh_interval
                ):
                    logger.info("Token即将过期，准备刷新...")

                    new_token = await self.refresh_token()
                    if new_token:
                        logger.info("Token刷新成功，准备重新建立连接...")
                        # 设置连接重启标志
                        self.connection_restart_flag = True
                        # 关闭当前WebSocket连接，触发重连
                        if self.ws:
                            await self.ws.close()
                        break
                    else:
                        logger.error(
                            "Token刷新失败，将在{}分钟后重试".format(
                                self.token_retry_interval // 60
                            )
                        )
                        await asyncio.sleep(
                            self.token_retry_interval
                        )  # 使用配置的重试间隔
                        continue

                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Token刷新循环出错: {e}")
                await asyncio.sleep(60)

    async def send_msg(self, ws, cid, toid, text):
        text = {"contentType": 1, "text": {"text": text}}
        text_base64 = str(base64.b64encode(json.dumps(text).encode("utf-8")), "utf-8")
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "uuid": generate_uuid(),
                    "cid": f"{cid}@goofish",
                    "conversationType": 1,
                    "content": {
                        "contentType": 101,
                        "custom": {"type": 1, "data": text_base64},
                    },
                    "redPointPolicy": 0,
                    "extension": {"extJson": "{}"},
                    "ctx": {"appVersion": "1.0", "platform": "web"},
                    "mtags": {},
                    "msgReadStatusSetting": 1,
                },
                {"actualReceivers": [f"{toid}@goofish", f"{self.myid}@goofish"]},
            ],
        }
        await ws.send(json.dumps(msg))

    async def init(self, ws):
        # 如果没有token或者token过期，获取新token
        if (
            not self.current_token
            or (time.time() - self.last_token_refresh_time)
            >= self.token_refresh_interval
        ):
            logger.info("获取初始token...")
            await self.refresh_token()

        if not self.current_token:
            logger.error("无法获取有效token，初始化失败")
            raise Exception("Token获取失败")

        msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "444e9908a51d1cb236a27862abc769c9",
                "token": self.current_token,
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid(),
            },
        }
        await ws.send(json.dumps(msg))
        # 等待一段时间，确保连接注册完成
        await asyncio.sleep(1)
        msg = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": "5701741704675979 0"},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": int(time.time() * 1000) * 1000,
                    "seq": 0,
                    "timestamp": int(time.time() * 1000),
                }
            ],
        }
        await ws.send(json.dumps(msg))
        logger.info("连接注册完成")

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

    def is_system_message(self, message):
        """判断是否为系统消息"""
        try:
            return (
                isinstance(message, dict)
                and "3" in message
                and isinstance(message["3"], dict)
                and "needPush" in message["3"]
                and message["3"]["needPush"] == "false"
            )
        except Exception:
            return False

    def check_toggle_keywords(self, message):
        """检查消息是否包含切换关键词"""
        message_stripped = message.strip()
        return message_stripped in self.toggle_keywords

    def is_manual_mode(self, chat_id):
        """检查特定会话是否处于人工接管模式"""
        if chat_id not in self.manual_mode_conversations:
            return False

        # 检查是否超时
        current_time = time.time()
        if chat_id in self.manual_mode_timestamps:
            if (
                current_time - self.manual_mode_timestamps[chat_id]
                > self.manual_mode_timeout
            ):
                # 超时，自动退出人工模式
                self.exit_manual_mode(chat_id)
                return False

        return True

    def enter_manual_mode(self, chat_id):
        """进入人工接管模式"""
        self.manual_mode_conversations.add(chat_id)
        self.manual_mode_timestamps[chat_id] = time.time()

    def exit_manual_mode(self, chat_id):
        """退出人工接管模式"""
        self.manual_mode_conversations.discard(chat_id)
        if chat_id in self.manual_mode_timestamps:
            del self.manual_mode_timestamps[chat_id]

    def toggle_manual_mode(self, chat_id):
        """切换人工接管模式"""
        if self.is_manual_mode(chat_id):
            self.exit_manual_mode(chat_id)
            return "auto"
        else:
            self.enter_manual_mode(chat_id)
            return "manual"

    async def handle_message(self, message_data, websocket):
        """处理所有类型的消息"""
        try:
            try:
                message = message_data
                ack = {
                    "code": 200,
                    "headers": {
                        "mid": message["headers"]["mid"]
                        if "mid" in message["headers"]
                        else generate_mid(),
                        "sid": message["headers"]["sid"]
                        if "sid" in message["headers"]
                        else "",
                    },
                }
                if "app-key" in message["headers"]:
                    ack["headers"]["app-key"] = message["headers"]["app-key"]
                if "ua" in message["headers"]:
                    ack["headers"]["ua"] = message["headers"]["ua"]
                if "dt" in message["headers"]:
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
                if message["3"]["redReminder"] == "等待买家付款":
                    user_id = message["1"].split("@")[0]
                    user_url = f"https://www.goofish.com/personal?userId={user_id}"
                    logger.info(f"等待买家 {user_url} 付款")
                    return
                elif message["3"]["redReminder"] == "交易关闭":
                    user_id = message["1"].split("@")[0]
                    user_url = f"https://www.goofish.com/personal?userId={user_id}"
                    logger.info(f"买家 {user_url} 交易关闭")
                    return
                elif message["3"]["redReminder"] == "等待卖家发货":
                    user_id = message["1"].split("@")[0]
                    user_url = f"https://www.goofish.com/personal?userId={user_id}"
                    logger.info(f"交易成功 {user_url} 等待卖家发货")
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
            if (time.time() * 1000 - create_time) > self.message_expire_time:
                logger.debug("过期消息丢弃")
                return

            # 获取商品ID和会话ID
            url_info = message["1"]["10"]["reminderUrl"]
            item_id = (
                url_info.split("itemId=")[1].split("&")[0]
                if "itemId=" in url_info
                else None
            )
            chat_id = message["1"]["2"].split("@")[0]

            if not item_id:
                logger.warning("无法获取商品ID")
                return

            # 检查是否为卖家（自己）发送的控制命令
            if send_user_id == self.myid:
                logger.debug("检测到卖家消息，检查是否为控制命令")

                # 检查切换命令
                if self.check_toggle_keywords(send_message):
                    mode = self.toggle_manual_mode(chat_id)
                    if mode == "manual":
                        logger.info(f"🔴 已接管会话 {chat_id} (商品: {item_id})")
                    else:
                        logger.info(
                            f"🟢 已恢复会话 {chat_id} 的自动回复 (商品: {item_id})"
                        )
                    return

                # 记录卖家人工回复
                self.context_manager.add_message_by_chat(
                    chat_id, self.myid, item_id, "assistant", send_message
                )
                logger.info(
                    f"卖家人工回复 (会话: {chat_id}, 商品: {item_id}): {send_message}"
                )
                return

            logger.info(
                f"用户: {send_user_name} (ID: {send_user_id}), 商品: {item_id}, 会话: {chat_id}, 消息: {send_message}"
            )

            # 检测是否为新会话，如果是则发送欢迎消息
            if self.context_manager.is_new_chat(chat_id):
                logger.info(f"检测到新会话 {chat_id}，发送欢迎消息")
                
                # 标记会话已开始
                self.context_manager.mark_chat_as_started(chat_id, send_user_id, item_id)
                
                # 发送欢迎消息
                welcome_message = (
                    "[紫奈模型屋大模型客服测试中]\n"
                    "由于卖家现在白天上班很忙，也没有专门的客服，因此试接入LLM客服完成部分客服工作。"
                    "机器人回复会以[机器人回复]开头。卖家下班后（工作日11点左右）会进行模型上传工作。"
                    "后续将尝试实现通过机器人进行模型上传的工作方便大家"
                )
                
                try:
                    await self.send_msg(websocket, chat_id, send_user_id, welcome_message)
                    logger.info(f"欢迎消息已发送到会话 {chat_id}")
                    
                    # 将欢迎消息添加到上下文中
                    self.context_manager.add_message_by_chat(
                        chat_id, self.myid, item_id, "assistant", welcome_message
                    )
                except Exception as e:
                    logger.error(f"发送欢迎消息失败: {e}")

            # 添加用户消息到上下文
            self.context_manager.add_message_by_chat(
                chat_id, send_user_id, item_id, "user", send_message
            )

            # 如果当前会话处于人工接管模式，不进行自动回复
            if self.is_manual_mode(chat_id):
                logger.info(f"🔴 会话 {chat_id} 处于人工接管模式，跳过自动回复")
                return
            if self.is_system_message(message):
                logger.debug("系统消息，跳过处理")
                return
            # 从数据库中获取商品信息，如果不存在则从API获取并保存
            item_info = self.context_manager.get_item_info(item_id)
            if not item_info:
                logger.info(f"从API获取商品信息: {item_id}")
                api_result = self.xianyu.get_item_info(item_id)
                if "data" in api_result and "itemDO" in api_result["data"]:
                    item_info = api_result["data"]["itemDO"]
                    # 保存商品信息到数据库
                    self.context_manager.save_item_info(item_id, item_info)
                else:
                    logger.warning(f"获取商品信息失败: {api_result}")
                    return
            else:
                logger.info(f"从数据库获取商品信息: {item_id}")

            item_description = (
                f"{item_info['desc']};当前商品售卖价格为:{str(item_info['soldPrice'])}"
            )

            # 获取完整的对话上下文
            context = self.context_manager.get_context_by_chat(chat_id)
            # 生成回复
            bot_reply = bot.generate_reply(
                send_message, item_description, context=context
            )

            # 检查是否为价格意图，如果是则增加议价次数
            if bot.last_intent == "price":
                self.context_manager.increment_bargain_count_by_chat(chat_id)
                bargain_count = self.context_manager.get_bargain_count_by_chat(chat_id)
                logger.info(
                    f"用户 {send_user_name} 对商品 {item_id} 的议价次数: {bargain_count}"
                )

            # 添加机器人回复到上下文
            self.context_manager.add_message_by_chat(
                chat_id, self.myid, item_id, "assistant", bot_reply
            )

            logger.info(f"机器人回复: {bot_reply}")
            await self.send_msg(websocket, chat_id, send_user_id, bot_reply)

        except Exception as e:
            logger.error(f"处理消息时发生错误: {str(e)}")
            logger.debug(f"原始消息: {message_data}")

    async def send_heartbeat(self, ws):
        """发送心跳包并等待响应"""
        try:
            heartbeat_mid = generate_mid()
            heartbeat_msg = {"lwp": "/!", "headers": {"mid": heartbeat_mid}}
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
                if (current_time - self.last_heartbeat_response) > (
                    self.heartbeat_interval + self.heartbeat_timeout
                ):
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
                # 重置连接重启标志
                self.connection_restart_flag = False

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

                async with websockets.connect(
                    self.base_url, extra_headers=headers
                ) as websocket:
                    self.ws = websocket
                    await self.init(websocket)

                    # 初始化心跳时间
                    self.last_heartbeat_time = time.time()
                    self.last_heartbeat_response = time.time()

                    # 启动心跳任务
                    self.heartbeat_task = asyncio.create_task(
                        self.heartbeat_loop(websocket)
                    )

                    # 启动token刷新任务
                    self.token_refresh_task = asyncio.create_task(
                        self.token_refresh_loop()
                    )

                    async for message in websocket:
                        try:
                            # 检查是否需要重启连接
                            if self.connection_restart_flag:
                                logger.info("检测到连接重启标志，准备重新建立连接...")
                                break

                            message_data = json.loads(message)

                            # 处理心跳响应
                            if await self.handle_heartbeat_response(message_data):
                                continue

                            # 发送通用ACK响应
                            if (
                                "headers" in message_data
                                and "mid" in message_data["headers"]
                            ):
                                ack = {
                                    "code": 200,
                                    "headers": {
                                        "mid": message_data["headers"]["mid"],
                                        "sid": message_data["headers"].get("sid", ""),
                                    },
                                }
                                # 复制其他可能的header字段
                                for key in ["app-key", "ua", "dt"]:
                                    if key in message_data["headers"]:
                                        ack["headers"][key] = message_data["headers"][
                                            key
                                        ]
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

            except Exception as e:
                logger.error(f"连接发生错误: {e}")

            finally:
                # 清理任务
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    try:
                        await self.heartbeat_task
                    except asyncio.CancelledError:
                        pass

                if self.token_refresh_task:
                    self.token_refresh_task.cancel()
                    try:
                        await self.token_refresh_task
                    except asyncio.CancelledError:
                        pass

                # 如果是主动重启，立即重连；否则等待5秒
                if self.connection_restart_flag:
                    logger.info("主动重启连接，立即重连...")
                else:
                    logger.info("等待5秒后重连...")
                    await asyncio.sleep(5)


if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()

    # 配置日志级别
    log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()
    logger.remove()  # 移除默认handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.info(f"日志级别设置为: {log_level}")

    cookies_str = os.getenv("COOKIES_STR")
    bot = XianyuReplyBot()
    xianyuLive = XianyuLive(cookies_str)
    # 常驻进程
    asyncio.run(xianyuLive.main())
