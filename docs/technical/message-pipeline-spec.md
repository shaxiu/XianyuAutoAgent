# 消息处理管线 — Technical Design Document

Date: 2026-03-04
Status: Approved
Module: `main.py`, `XianyuAgent.py`, `context_manager.py`, `utils/xianyu_utils.py`

---

## 1. Design Goal

实现从 WebSocket 原始消息到 AI 智能回复的完整处理管线，确保消息不丢、不重复回复、安全合规。

### Core Principles

1. 消息时效性优先——超时消息直接丢弃，不回复过时内容
2. 本地存储为主——AI 回复依赖本地 SQLite，不依赖网络
3. 安全过滤兜底——所有 AI 输出都经过安全过滤再发送

---

## 2. 核心逻辑

### 2.1 消息接收与解密

```
WebSocket 原始 JSON
    │
    ▼
检查 body.syncPushPackage.data[0].data 字段
    │
    ▼
尝试 base64 解码
    │
    ├── 成功解码为 JSON → 非加密消息，直接返回（不处理）
    │
    └── 解码失败 → 调用 decrypt(data)
                     │
                     ▼
                 MessagePack 解密 → JSON 对象
```

### 2.2 意图路由策略

| # | 策略 | 模式 | 示例 |
|---|---|---|---|
| 1 | 技术关键词匹配 | `参数 / 规格 / 型号 / 连接 / 对比` | "这个参数是什么？" |
| 2 | 技术正则匹配 | `r'和.+比'` | "和索尼比怎么样？" |
| 3 | 价格关键词匹配 | `便宜 / 价 / 砍价 / 少点` | "能便宜点吗？" |
| 4 | 价格正则匹配 | `r'\d+元'`, `r'能少\d+'` | "200元卖不？" |
| 5 | 大模型分类兜底 | ClassifyAgent | "你好在吗" → default |

**优先级**：tech 关键词 → tech 正则 → price 关键词 → price 正则 → LLM 兜底

### 2.3 Agent 调用链

```
XianyuReplyBot.generate_reply(user_msg, item_desc, context)
    │
    ├── format_history(context) → 过滤 system 消息，保留 user/assistant
    │
    ├── IntentRouter.detect(user_msg, item_desc, formatted_context)
    │     └── 返回 intent: price / tech / default / no_reply
    │
    ├── intent == no_reply → 返回 "-"（不回复标记）
    │
    ├── 获取对应 Agent
    │
    ├── _extract_bargain_count(context) → 从 system 消息中提取议价次数
    │
    └── Agent.generate(user_msg, item_desc, context, bargain_count)
          │
          ├── _build_messages() → 构建 LLM 消息链
          │     System: "【商品信息】...\n【对话历史】...\n{prompt}"
          │     User: "{user_msg}"
          │
          ├── _call_llm(messages, temperature) → OpenAI API 调用
          │     model: qwen-max (可配置)
          │     max_tokens: 500
          │     top_p: 0.8
          │
          └── safety_filter(response) → 安全过滤
```

---

## 3. Edge Cases

| 场景 | 输入 | 处理后 | 行为 |
|---|---|---|---|
| 消息过期 | 5 分钟前的消息 | 时间戳对比 | 直接丢弃，不回复 |
| 卖家自己发消息 | send_user_id == myid | 身份检查 | 仅记录上下文或处理控制指令 |
| 系统消息 [xxx] | `[对方已确认收货]` | 正则匹配 | 跳过不回复 |
| AI 输出包含微信号 | "加我微信xxx" | 安全过滤 | 替换为安全提醒 |
| AI 返回 no_reply | 买家说"好的谢谢" | 返回 "-" | 不发送任何消息 |
| 商品信息获取失败 | API 异常 | 返回空 | 放弃本次回复 |
| 人工接管中 | manual_mode = True | 状态检查 | 仅存上下文，不回复 |
| 人工接管超时 | 超过 1 小时 | 时间检查 | 自动恢复 AI 模式 |
| WebSocket 断连 | 心跳超时 | 心跳检测 | 等 5 秒后自动重连 |
| Token 过期 | 2 小时到期 | 定时检查 | 刷新 Token 后重连 |
| Cookie 被风控 | RGV587_ERROR | API 返回检查 | 尝试从 Supabase 获取新 Cookie |

---

## 4. 交互流程

```
买家在闲鱼 App 发送消息
    │
    ▼
闲鱼服务器 → WebSocket Push
    │
    ▼
main.py: XianyuLive.handle_message()
    ├── 发送 ACK 响应
    ├── 检查是否为 syncPushPackage
    ├── 解密消息数据
    ├── 判断消息类型（订单/系统/输入状态/聊天）
    ├── 检查时效性（5 分钟过期）
    ├── 检查是否为卖家消息
    ├── 检查人工接管状态
    ├── 获取商品信息 → ContextManager 或 XianyuApis
    ├── 获取对话上下文 → ContextManager
    │
    ▼
XianyuAgent.py: XianyuReplyBot.generate_reply()
    ├── 意图路由
    ├── Agent 生成回复
    ├── 安全过滤
    │
    ▼
main.py: 后处理
    ├── 存储用户消息 → SQLite + Supabase
    ├── 存储 Bot 回复 → SQLite + Supabase
    ├── 更新议价计数（如果是 price 意图）
    ├── 模拟打字延迟（可选）
    │
    ▼
main.py: XianyuLive.send_msg()
    └── WebSocket → 闲鱼服务器 → 买家收到回复
```

---

## 5. State Management

### 内存状态（XianyuLive 实例）

```python
self.manual_mode_conversations: set()  # 人工接管中的会话 ID 集合
self.manual_mode_timestamps: dict      # 进入人工模式的时间戳
self.current_token: str                # 当前有效 Token
self.last_heartbeat_time: float        # 上次发送心跳的时间
self.last_heartbeat_response: float    # 上次收到心跳响应的时间
self.connection_restart_flag: bool     # 是否需要重启连接
```

### 持久化状态（SQLite）

```python
ChatContextManager:
    messages          # 对话消息历史（每个 chat_id 最多 100 条）
    chat_bargain_counts  # 议价次数计数
    items             # 商品信息缓存
```

### 数据流

```
WebSocket 消息 → 解密 → 读 SQLite(context + item) → Agent 生成回复
                                                          │
                                                          ▼
                                                    写 SQLite(message)
                                                    写 Supabase(conversation + log)
                                                          │
                                                          ▼
                                                    WebSocket 发送回复
```

---

## 6. API Endpoints

### 闲鱼 API（Python Bot 调用）

```
POST https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/
  → 获取 WebSocket Token

POST https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/
  data: {"itemId": "xxx"}
  → 获取商品详细信息

POST https://passport.goofish.com/newlogin/hasLogin.do
  → 登录状态检查 / 刷新

WebSocket wss://wss-goofish.dingtalk.com/
  → 实时消息收发
```

### LLM API（Agent 调用）

```
POST {MODEL_BASE_URL}/chat/completions
  model: qwen-max (默认)
  messages: [{role, content}]
  temperature: 0.3 ~ 0.9
  max_tokens: 500
  top_p: 0.8
  extra_body: {enable_search: true}  // 仅 TechAgent
```

### Dashboard API（Next.js）

```
POST /api/auth/login          → 登录（密码 → JWT）
POST /api/auth/logout         → 登出（清除 Cookie）
GET  /api/accounts            → 获取所有账户
GET  /api/conversations?account_id=xxx&limit=N  → 获取对话记录
GET  /api/logs?account_id=xxx&level=ERROR       → 获取日志
GET  /api/settings?account_id=xxx               → 获取设置
PUT  /api/settings            → 更新设置
GET  /api/settings/prompts?account_id=xxx       → 获取 Prompts
PUT  /api/settings/prompts    → 更新 Prompts
```

---

## 7. Implementation Files

| File | Role |
|---|---|
| `main.py` | WebSocket 连接管理、消息调度、心跳、Token 刷新 |
| `XianyuAgent.py` | AI Agent 系统：IntentRouter + 4 个 Agent |
| `XianyuApis.py` | 闲鱼 HTTP API 封装：Token 获取、商品查询、Cookie 管理 |
| `context_manager.py` | SQLite 对话管理：消息存储、上下文检索、议价计数、商品缓存 |
| `supabase_sync.py` | Supabase 云同步：配置读取、对话写入、日志缓冲、状态更新 |
| `utils/xianyu_utils.py` | 工具函数：签名生成、消息加解密、ID 生成、Cookie 转换 |
| `prompts/*.txt` | Prompt 模板文件 |

---

## 8. Future Enhancements (Not in v1)

- [ ] Chrome 扩展完善：替代 Python Bot，利用浏览器 Cookie 免配置
- [ ] 多媒体消息支持：图片、视频消息的识别和回复
- [ ] 订单消息自动处理：付款后自动发送发货提醒
- [ ] 对话质量评分：自动评估 AI 回复质量
- [ ] Prompt A/B 测试：同时运行不同 Prompt 对比效果
