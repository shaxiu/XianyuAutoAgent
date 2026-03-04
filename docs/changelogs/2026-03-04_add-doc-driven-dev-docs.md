# 2026-03-04 新增文档驱动开发体系

## 改了什么
- 为整个项目建立了完整的文档驱动开发（Doc-Driven Dev）文档体系
- 新增业务文档：业务全貌、模块关联关系、AI Agent 模块、WebSocket 模块、Dashboard 模块
- 新增页面文档：Dashboard 首页、对话记录页、设置页的用户意图与信息规格
- 新增技术文档：系统架构总览、消息处理管线技术规格
- 新增复盘机制：复盘模板、避坑清单
- 新增 CLAUDE.md：AI 改代码前必须先读文档的强制规则

## 修改的文件
- `CLAUDE.md` — 新增 AI 开发规则（改代码前读文档、复盘机制、安全红线）
- `docs/README.md` — 新增文档索引导航页
- `docs/business/README.md` — 新增业务全貌文档（核心流程、约束、数据分层）
- `docs/business/module-coupling.md` — 新增模块关联关系文档（5 个关联点 + 依赖图）
- `docs/business/agent-module.md` — 新增 AI Agent 模块文档（意图路由、温度策略）
- `docs/business/websocket-module.md` — 新增 WebSocket 模块文档（连接生命周期、心跳）
- `docs/business/dashboard-module.md` — 新增 Dashboard 模块文档（功能列表、认证）
- `docs/business/page-dashboard.md` — 新增 Dashboard 首页文档
- `docs/business/page-conversations.md` — 新增对话记录页文档
- `docs/business/page-settings.md` — 新增设置页文档
- `docs/technical/architecture.md` — 新增系统架构文档（技术栈、项目结构、DB Schema）
- `docs/technical/message-pipeline-spec.md` — 新增消息管线技术规格文档
- `docs/postmortems/README.md` — 新增复盘机制 + 避坑清单

## 需要手动操作
- 无
