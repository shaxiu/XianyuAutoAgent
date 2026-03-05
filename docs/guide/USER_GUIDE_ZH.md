# XianyuAutoAgent 使用指导书（中文）

本指南面向第一次使用项目的用户，目标是：
- 先跑通最基础的 AI 自动回复。
- 再按需开启订单业务路由（不同商品走不同 webhook）。

## 1. 项目是做什么的

XianyuAutoAgent 是一个闲鱼自动客服机器人：
- 默认能力：收到聊天消息后由 AI 自动回复。
- 可选能力：把订单事件按商品路由给不同外部业务服务（webhook），由外部服务返回动作（例如自动回一句话）。

你可以先只用默认 AI 回复，不配置任何 webhook。

## 2. 环境准备

### 2.1 基础要求
- Python 3.8+
- 可联网（访问模型 API 和闲鱼服务）

### 2.2 安装依赖
```bash
cd /path/to/XianyuAutoAgent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 第一次运行（最小可用）

### 3.1 配置 `.env`
复制模板：
```bash
cp .env.example .env
```

最少需要配置：
```bash
API_KEY=你的模型API密钥
COOKIES_STR=你的闲鱼网页Cookie
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-max
```

说明：
- `API_KEY`：你自己的大模型平台 key。
- `COOKIES_STR`：从闲鱼网页端抓取。

### 3.2 获取 `COOKIES_STR`（网页端）
1. 打开闲鱼网页版并登录。
2. 按 `F12` 打开开发者工具。
3. 进入 `Network`，过滤 `Fetch/XHR`。
4. 点开任意请求，在请求头里找到 `Cookie`。
5. 复制完整 cookie 字符串，填入 `.env` 的 `COOKIES_STR`。

### 3.3 启动
```bash
python3 main.py
```

看到日志后，去闲鱼聊天窗口发一条消息，观察是否自动回复。

## 4. 常用配置

### 4.1 人工接管开关
```bash
TOGGLE_KEYWORDS=。
```
- 在聊天中发送该关键字（默认是句号）可切换会话人工接管/自动回复。

### 4.2 模拟人工输入延迟
```bash
SIMULATE_HUMAN_TYPING=False
```
- `True`：发送回复前会有随机延时。

## 5. 订单业务路由（可选）

如果你有多个商品，且只有部分商品需要订单业务处理，请用下面配置。

### 5.1 开启订单路由
```bash
ORDER_ROUTER_ENABLED=true
```

### 5.2 单商品路由（精确）
```bash
ORDER_ITEM_WEBHOOK_ROUTES={"itemA":{"url":"https://biz-a.example.com/events","secret":"sa"},"itemB":{"url":"https://biz-b.example.com/events","secret":"sb","retries":3}}
```

### 5.3 分组路由（批量）
```bash
ORDER_GROUP_WEBHOOK_ROUTES={"ship_group":{"items":["itemC","itemD"],"url":"https://biz-group.example.com/events","secret":"sg"}}
```

### 5.4 路由优先级
- 单商品路由高于分组路由。
- 都没命中时，不发订单 webhook，聊天仍走默认 AI 自动回复。

### 5.5 超时和重试
```bash
ORDER_ROUTER_TIMEOUT_MS=3000
ORDER_ROUTER_RETRIES=2
```

## 6. Webhook 接口应该怎么写

你的业务服务接收事件后，返回动作列表：

```json
{
  "actions": [
    {
      "action_type": "send_text",
      "payload": {
        "chat_id": "chat123",
        "to_user_id": "user123",
        "text": "订单已收到，我们会尽快处理。"
      }
    }
  ]
}
```

签名头：
- Header: `X-Agent-Signature`
- 算法：`HMAC-SHA256`

完整示例见：
- `docs/integration/webhook-example.md`
- `docs/events.md`
- `docs/actions.md`

## 7. 调试与排错

### 7.1 先跑构建检查
```bash
python3 -m py_compile main.py context_manager.py XianyuApis.py XianyuAgent.py
python3 -m compileall -q core utils
```

### 7.2 常见问题

1. `ModuleNotFoundError: loguru` 或其他依赖缺失
- 先激活虚拟环境，再 `pip install -r requirements.txt`。

2. 启动后没有自动回复
- 检查 `.env` 是否存在且 `API_KEY/COOKIES_STR` 正确。
- 检查是否切到了人工接管模式。
- 查看日志里是否有“过期消息丢弃/系统消息跳过”。

3. webhook 没触发
- 确认 `ORDER_ROUTER_ENABLED=true`。
- 确认商品命中 `ORDER_ITEM_WEBHOOK_ROUTES` 或 `ORDER_GROUP_WEBHOOK_ROUTES`。
- 检查 webhook URL 是否可达，服务是否返回 2xx。

4. 同一订单事件重复处理
- 默认有事件去重：`EVENT_DEDUP_TTL_SECONDS=86400`。

## 8. 推荐上线步骤

1. 先只开默认 AI 回复，观察 1-2 天。
2. 给少量商品配置订单路由，灰度验证 webhook 稳定性。
3. 再逐步扩大到更多商品。

## 9. 你下一步可以直接做

1. 先按第 3 章跑通默认自动回复。
2. 把你要接业务服务的商品 `item_id` 列出来。
3. 按第 5 章填 `ORDER_ITEM_WEBHOOK_ROUTES`/`ORDER_GROUP_WEBHOOK_ROUTES`。

如果你愿意，我可以根据你真实的商品 ID 和 webhook 地址，帮你直接生成可粘贴的 `.env` 片段。
