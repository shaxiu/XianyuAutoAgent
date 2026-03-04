# Xianyu AutoAgent 文档索引

> **阅读顺序**：先读业务文档理解"要做什么"，再读技术文档理解"怎么实现的"。

---

## 业务文档（Business）

定义**业务目标、用户场景、交互规格**。是设计标准，代码要按这个来。

### 全局

| 文档 | 内容 |
|---|---|
| [README.md](./business/README.md) | 业务全貌、完整流程、核心约束、数据分层 |
| [module-coupling.md](./business/module-coupling.md) | 模块间关联关系（改代码前必看） |

### 模块视角

| 文档 | 模块 | 关联技术文档 |
|---|---|---|
| [agent-module.md](./business/agent-module.md) | AI 智能客服 Agent | → [message-pipeline-spec.md](./technical/message-pipeline-spec.md) |
| [websocket-module.md](./business/websocket-module.md) | WebSocket 通信 | → [architecture.md](./technical/architecture.md) |
| [dashboard-module.md](./business/dashboard-module.md) | Dashboard 管理后台 | → [architecture.md](./technical/architecture.md) |

### 页面视角

| 文档 | 页面 | 核心问题 |
|---|---|---|
| [page-dashboard.md](./business/page-dashboard.md) | Dashboard 首页 | "我的店铺机器人运行正常吗？" |
| [page-conversations.md](./business/page-conversations.md) | 对话记录页 | "机器人都跟客户聊了什么？" |
| [page-settings.md](./business/page-settings.md) | 设置页 | "怎么配置机器人的行为？" |

---

## 技术文档（Technical）

| 文档 | 内容 | 服务于业务模块 |
|---|---|---|
| [architecture.md](./technical/architecture.md) | 系统架构、技术栈、项目结构、数据库 Schema | 全局 |
| [message-pipeline-spec.md](./technical/message-pipeline-spec.md) | 消息处理管线：从 WebSocket 到 AI 回复的全流程 | AI Agent + WebSocket |

---

## 复盘与避坑（Postmortems）

| 文档 | 内容 |
|---|---|
| [README.md](./postmortems/README.md) | 复盘机制、索引、避坑清单 |

---

## 如何使用这些文档

### 要改某个功能时
1. 先读业务文档 → 理解用户目标和场景
2. 再读模块关联文档 → 确认改动会不会影响其他模块
3. 然后读技术文档 → 理解当前实现细节
4. 最后动手改代码

### 要加新功能时
1. 先在业务文档中补充新功能的用户场景和交互规格
2. 检查模块关联文档 → 新功能和现有模块怎么联动
3. 确认方案 → 再开始编码

### 出问题后
1. 先修复问题
2. 写复盘文档 → `docs/postmortems/YYYY-MM-DD_描述.md`
3. 更新避坑清单 → `docs/postmortems/README.md`
