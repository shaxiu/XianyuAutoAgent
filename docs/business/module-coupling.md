# 模块间关联关系

> 任何涉及跨模块的功能改动，必须参考本文档确认不会破坏关联逻辑。

---

## 1. 实体关系图

```
Account (1)
  │
  ├── WebSocket Connection (1)     每个账户一个 WS 长连接
  │     └── Token                  认证令牌，2h 过期
  │
  ├── Agents (4)                   四个 AI Agent
  │     ├── ClassifyAgent          意图分类（内部，不直接回复）
  │     ├── PriceAgent             议价（引用 BargainCount）
  │     ├── TechAgent              技术咨询（启用联网搜索）
  │     └── DefaultAgent           默认回复
  │
  ├── ChatContextManager (1)       本地 SQLite 数据管理
  │     ├── Messages[]             对话消息历史
  │     ├── BargainCounts[]        议价次数统计
  │     └── Items[]                商品信息缓存
  │
  ├── SupabaseSync (0..1)          云端同步（可选）
  │     ├── Conversations[]        云端对话记录
  │     ├── Logs[]                 云端运行日志
  │     └── Prompts[]              云端提示词配置
  │
  └── ManualMode                   人工接管状态（内存）
        ├── conversations: Set     被接管的会话 ID 集合
        └── timestamps: Dict       进入人工模式的时间戳
```

---

## 2. 关联点 1：WebSocket → Agent 的消息触发

### 数据流

```
WebSocket 收到原始消息
  ├── message_data (JSON)
  │     └── body.syncPushPackage.data[0].data (加密)
  │           │
  │           ▼ decrypt()
  │     解密后消息 (JSON)
  │           │
  │           ├── send_message (买家发的文字)
  │           ├── item_id (商品 ID)
  │           ├── chat_id (会话 ID)
  │           └── send_user_id (发送者 ID)
  │
  ├── item_info ← ContextManager.get_item_info() 或 XianyuApis.get_item_info()
  │
  ├── context ← ContextManager.get_context_by_chat(chat_id)
  │
  └── 组装后传入 ──→ XianyuReplyBot.generate_reply(send_message, item_desc, context)
                          │
                          ├── IntentRouter.detect() → 路由到具体 Agent
                          └── Agent.generate() → 返回回复文本
```

### 规则

1. **消息时效性**：超过 `MESSAGE_EXPIRE_TIME`（默认 5 分钟）的消息直接丢弃
2. **卖家消息不触发 AI**：`send_user_id == self.myid` 时仅记录上下文或处理控制指令
3. **人工接管优先**：`is_manual_mode(chat_id)` 为 True 时仅存上下文不回复
4. **系统消息跳过**：`[xxx]` 格式的消息和 `needPush=false` 的消息不处理

### 影响（改了这里，那里会怎样）

- **改消息解密逻辑时**：所有消息处理都会受影响，必须保证解密后的 JSON 结构不变
- **改 Agent 路由规则时**：会影响哪些消息走哪个 Agent，可能影响回复质量
- **改 ContextManager 的存储格式时**：Agent 拿到的 context 格式会变，需要同步改 Agent 的 `_build_messages`

---

## 3. 关联点 2：ContextManager ↔ SupabaseSync 的数据双写

### 数据流

```
用户消息到达
  │
  ├── ContextManager.add_message_by_chat()    ← 写本地 SQLite
  │
  └── SupabaseSync.log_conversation()          ← 写云端 Supabase
        │
        └── 同时写 chat_id, item_id, item_title, role, content, intent
```

### 规则

1. **本地优先**：ContextManager 是主存储，AI 生成回复时只读本地
2. **云端仅追加**：Supabase 的 conversations 表只写入不读回（Bot 端不从云端读对话）
3. **Supabase 可选**：没配置 Supabase 环境变量时，所有 sync 操作静默跳过

### 影响（改了这里，那里会怎样）

- **改 ContextManager 的消息格式时**：不影响 Supabase（两者独立写入）
- **改 Supabase 表结构时**：需要同时更新 Dashboard 的 API 读取逻辑
- **清空 SQLite 数据时**：不影响 Dashboard 已有数据，但 Bot 会丢失对话上下文

---

## 4. 关联点 3：SupabaseSync → Dashboard 的数据展示

### 数据流

```
Dashboard 页面请求
  │
  ├── /api/accounts        ← Supabase.accounts 表
  ├── /api/conversations   ← Supabase.conversations 表
  ├── /api/logs            ← Supabase.logs 表
  └── /api/settings/prompts ← Supabase.prompts 表
```

### 规则

1. **Dashboard 只读 Supabase**：Dashboard 不直接访问 Python Bot 的 SQLite
2. **账户状态实时更新**：Bot 在连接/断开时通过 `SupabaseSync.update_status()` 更新状态
3. **日志缓冲写入**：WARNING 及以上级别的日志先缓冲，每 5 秒批量写入 Supabase

### 影响（改了这里，那里会怎样）

- **改 Dashboard API 的返回格式时**：只影响前端展示，不影响 Bot
- **改 Supabase 表结构时**：需要同时更新 Dashboard API + Python SupabaseSync
- **改 Prompt 内容时（通过 Dashboard）**：Bot 下次初始化或调用 `reload_prompts()` 时生效

---

## 5. 关联点 4：PriceAgent ↔ BargainCount 的议价联动

### 数据流

```
消息被识别为 price 意图
  │
  ├── ContextManager.increment_bargain_count_by_chat(chat_id)
  │     └── SQLite: chat_bargain_counts 表 count + 1
  │
  ├── ContextManager.get_context_by_chat(chat_id)
  │     └── 自动把 bargain_count 作为 system message 附加到 context
  │
  └── PriceAgent.generate()
        └── _calc_temperature(bargain_count) → min(0.3 + count * 0.15, 0.9)
```

### 规则

1. **仅 price 意图触发计数**：只有 `bot.last_intent == "price"` 时才增加议价次数
2. **计数跟随会话**：基于 chat_id 统计，同一买家不同商品在同一会话中共享计数
3. **温度上限**：动态温度最高 0.9，防止回复过于随机

### 影响（改了这里，那里会怎样）

- **改议价计数逻辑时**：会影响 PriceAgent 的温度策略，间接影响议价回复风格
- **改 IntentRouter 的 price 关键词时**：会影响哪些消息被识别为议价，进而影响计数

---

## 6. 关联点 5：Cookie/Token → 连接可用性

### 数据流

```
Cookie 失效/风控触发
  │
  ├── get_token() 返回 RGV587_ERROR
  │     │
  │     ├── 尝试从 Supabase 拉最新 Cookie ← Dashboard Settings 更新的
  │     │     └── SupabaseSync.get_latest_cookies()
  │     │
  │     ├── 回退：提示手动输入
  │     │
  │     └── 都失败 → sys.exit(1)
  │
  └── Token 正常刷新
        ├── 设置 connection_restart_flag = True
        ├── 关闭当前 WebSocket
        └── 自动重连并使用新 Token
```

### 规则

1. **Cookie 更新来源**：Dashboard Settings 页面 → Supabase accounts 表 → Bot 风控时读取
2. **Token 刷新不丢消息**：重连后 Xianyu 会重发未读消息
3. **hasLogin 恢复**：Token 获取失败时先尝试 `hasLogin()` 刷新登录状态

### 影响（改了这里，那里会怎样）

- **改 Dashboard 的 Cookie 更新接口时**：Bot 风控恢复流程会受影响
- **改 Token 刷新间隔时**：过短会频繁断连，过长可能导致 Token 过期后消息丢失

---

## 7. 模块依赖关系图

```
         ┌─────────────────┐
         │  Dashboard (Web) │ ← 管理界面
         └────────┬────────┘
                  │ 读/写
                  ▼
         ┌─────────────────┐
         │    Supabase      │ ← 云端数据中心
         └────────┬────────┘
                  │ 读配置 / 写日志+对话
                  ▼
         ┌─────────────────┐
         │  Python Bot      │ ← 核心业务
         └────┬────────┬───┘
              │        │
     ┌────────┘        └────────┐
     ▼                          ▼
┌──────────┐           ┌──────────────────┐
│ WebSocket │──消息──→ │ XianyuReplyBot    │
│ (通信层)  │          │ (Agent 路由+回复)  │
└──────────┘           └────────┬─────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            ┌──────────────┐       ┌──────────────┐
            │ContextManager│       │ XianyuApis    │
            │ (SQLite 存储) │       │ (HTTP API)   │
            └──────────────┘       └──────────────┘
```

**关键原则**：
- Dashboard 只通过 Supabase 和 Bot 交互，不直接调用 Bot
- Bot 的核心逻辑不依赖 Supabase（Supabase 挂了 Bot 照常工作）
- WebSocket 层只负责收发，不处理业务逻辑
- Agent 层只负责生成回复，不关心消息怎么来的

---

## 跨模块操作的数据一致性

| 操作 | 涉及模块 | 一致性保证 |
|---|---|---|
| 买家消息处理 | WebSocket + ContextManager + Agent + Supabase | 先存本地 SQLite，再写 Supabase，Supabase 失败不影响主流程 |
| 议价计数 | ContextManager + PriceAgent | 先写 SQLite 计数，再读回注入 context，Agent 内部不维护计数状态 |
| Cookie 更新 | Dashboard + Supabase + Bot | Dashboard 写 Supabase → Bot 风控时读取，非实时同步 |
| Prompt 更新 | Dashboard + Supabase + Bot | Dashboard 写 Supabase → Bot 下次 init 或 reload 时读取 |
| 状态更新 | Bot + Supabase + Dashboard | Bot 连接/断开时写 Supabase → Dashboard 轮询读取展示 |
