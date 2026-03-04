# 复盘与避坑（Postmortems）

## 复盘机制

### 什么时候要写复盘？

1. Bot 掉线超过 30 分钟未自动恢复
2. AI 回复了不当内容（如泄露联系方式）
3. Cookie 失效导致服务中断
4. 数据丢失或不一致
5. 花了超过 30 分钟排查的问题
6. 差点引入的重大隐患

### 怎么写复盘？

1. 创建文件 `docs/postmortems/YYYY-MM-DD_简短描述.md`
2. 按模板填写（模板在 `docs/doc-driven-dev/templates/postmortem.md`）
3. 更新下方的复盘索引表
4. 提炼避坑条目，添加到下方避坑清单

---

## 复盘索引

| 日期 | 问题 | 核心教训 | 改进措施 |
|------|------|----------|----------|
| （暂无复盘记录） | | | |

---

## 避坑清单（Quick Reference）

改代码前快速过一遍：

### Cookie / Token

- 闲鱼 Cookie 会不定期过期或被风控，必须有 Cookie 更新机制
- Token 刷新时会断开 WebSocket，刷新逻辑要保证重连后消息不丢
- 触发 `RGV587_ERROR` 说明被风控，需要更新 Cookie
- Cookie 更新后要同步更新 `.env` 文件，否则下次重启又是旧 Cookie

### WebSocket 连接

- 心跳必须持续发送，不能因为处理消息阻塞导致心跳中断
- 断连后必须有自动重连逻辑，不能静默失败
- Token 刷新和心跳是两个独立的异步任务，互不影响

### AI 回复安全

- 所有 AI 输出必须经过安全过滤，不能直接发送
- 屏蔽词列表：微信、QQ、支付宝、银行卡、线下
- AI 可能在上下文影响下输出屏蔽内容，安全过滤是最后防线

### 数据一致性

- 本地 SQLite 是 Bot 的主数据源，Supabase 是辅助（挂了不影响核心功能）
- 写 Supabase 失败不能阻塞主流程，需要 try-catch 静默处理
- 议价计数基于 chat_id，改了 chat_id 的生成逻辑会影响计数

### 多模块联动

- 改 Prompt 格式要同时检查 Agent 的 `_build_messages` 是否兼容
- 改 Supabase 表结构要同时更新 Dashboard API 和 Python supabase_sync
- 改意图路由关键词要评估对议价计数和回复质量的影响
