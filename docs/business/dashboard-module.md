# Dashboard 管理后台模块

> 一句话总结：这个模块是一个 Web 管理界面，让卖家在浏览器里监控机器人状态、查看对话记录、修改配置。

---

## 1. 核心概念

Dashboard 是一个独立的 Next.js Web 应用，通过 Supabase 作为中间数据层与 Python Bot 间接交互。卖家不需要懂技术，打开浏览器就能管理自己的闲鱼自动客服。

---

## 2. 功能列表

| 功能 | 页面 | 数据来源 |
|---|---|---|
| 查看账户在线状态 | 首页 | Supabase accounts 表 |
| 查看消息统计 | 首页 | Supabase conversations 表 |
| 查看错误数量 | 首页 | Supabase logs 表 |
| 浏览对话记录 | 对话记录页 | Supabase conversations 表 |
| 查看系统日志 | 日志页 | Supabase logs 表 |
| 编辑提示词 | 设置页 | Supabase prompts 表 |
| 更新 Cookie | 设置页 | Supabase accounts 表 |
| 修改账户名称 | 设置页 | Supabase accounts 表 |
| 切换明暗主题 | 全局 | 本地存储 |

---

## 3. 页面结构

```
/login                    登录页（密码认证 → JWT Cookie）
/(dashboard)/             首页（账户状态总览）
/(dashboard)/conversations  对话记录页
/(dashboard)/logs           日志页
/(dashboard)/settings       设置页
```

---

## 4. 认证机制

**场景**："只有我自己能访问 Dashboard"

1. 用户访问任意 Dashboard 页面
2. Middleware 检查是否有有效的 `auth_token` Cookie
3. 没有 → 重定向到 `/login`
4. 有 → 验证 JWT → 通过则放行

**登录密码**：通过环境变量 `DASHBOARD_PASSWORD` 设置

---

## 5. 多账户支持

**场景**："我有多个闲鱼账户，都想用自动客服"

- Dashboard 通过 Supabase accounts 表管理多个账户
- 每个账户独立的 Cookie、API Key、提示词、对话记录
- 首页以卡片形式展示所有账户的状态
- 设置页可切换不同账户进行配置

---

## 6. 与 Bot 的交互方式

Dashboard 和 Python Bot **不直接通信**，全部通过 Supabase 中转：

| 方向 | 数据 | 路径 |
|---|---|---|
| Dashboard → Bot | Cookie 更新 | Dashboard 写 accounts 表 → Bot 风控时读取 |
| Dashboard → Bot | Prompt 修改 | Dashboard 写 prompts 表 → Bot 下次初始化时读取 |
| Bot → Dashboard | 在线状态 | Bot 写 accounts 表 status 字段 → Dashboard 轮询展示 |
| Bot → Dashboard | 对话记录 | Bot 写 conversations 表 → Dashboard 按需查询 |
| Bot → Dashboard | 错误日志 | Bot 缓冲写 logs 表 → Dashboard 按需查询 |
