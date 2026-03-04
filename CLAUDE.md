# CLAUDE.md - Xianyu AutoAgent AI 开发规则

## 强制规则：改代码之前必须先读文档

**在修改任何功能代码之前，必须先阅读相关的业务文档和技术文档。**

文档索引在 `docs/README.md`，按以下流程操作：

1. 读 `docs/README.md` → 找到要改的功能对应哪个业务文档和技术文档
2. 读 `docs/postmortems/README.md` 的避坑清单 → 检查当前改动是否涉及已知的坑
3. 读对应的业务文档（`docs/business/`）→ 理解用户目标、操作场景、边界状态
4. 读 `docs/business/module-coupling.md` → 确认改动会不会影响其他模块
5. 读对应的技术文档（`docs/technical/`）→ 理解当前实现细节
6. 然后再动手改代码

**不确定该读哪个文档时，先读 `docs/business/README.md`（业务全貌）。**

## 强制规则：出问题后必须写复盘

遇到以下情况时，**必须**写复盘文档并更新避坑清单：

1. Bot 掉线超过 30 分钟未自动恢复
2. AI 回复了不当内容
3. Cookie 失效导致服务中断
4. 数据丢失或不一致
5. 花了超过 30 分钟排查的问题
6. 差点引入的重大隐患

复盘流程：
1. 写复盘文档 → `docs/postmortems/YYYY-MM-DD_描述.md`
2. 更新避坑清单 → `docs/postmortems/README.md`
3. 如果涉及流程改进 → 更新对应的文档
4. 如果涉及编码规范 → 更新对应的技术文档

## 强制规则：改完代码后更新文档

每次修改功能代码后，检查是否需要更新以下文档：
- 业务文档（用户流程或场景有变化时）
- 模块关联文档（跨模块联动逻辑有变化时）
- 技术文档（API、数据结构、算法有变化时）

## 项目概述

Xianyu AutoAgent 是闲鱼平台的 AI 自动客服系统，核心模块：
- **Python Bot**（`main.py`）：WebSocket 长连接 + 消息处理
- **AI Agent**（`XianyuAgent.py`）：多 Agent 意图路由 + 回复生成
- **Dashboard**（`dashboard/`）：Next.js Web 管理后台
- **数据层**：本地 SQLite + 云端 Supabase

## 安全红线

- AI 回复中绝对不能出现：微信、QQ、支付宝、银行卡、线下
- 所有 AI 输出必须经过 `_safe_filter` 过滤
- Cookie 和 API Key 不能出现在日志或代码中
