# 闲鱼自动回复 Chrome 插件

Chrome 浏览器插件，直接在闲鱼网页中运行，复用浏览器登录态实现自动回复，零风控。

## 安装

1. 打开 Chrome，访问 `chrome://extensions/`
2. 开启右上角的 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择 `chrome-extension/` 目录

## 配置

安装后点击插件图标 → **设置**（或右键插件图标 → 选项），填写：

### 必填
- **API Key** — LLM API 密钥（支持 OpenAI 兼容格式，如通义千问 DashScope）
- **Model Base URL** — API 地址，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **Model Name** — 模型名称，默认 `qwen-max`

### 可选（Supabase 云同步）
- **Supabase URL** — Supabase 项目地址
- **Supabase Key** — Supabase anon key
- **Account ID** — 账号标识
- **Dashboard URL** — Dashboard 面板地址

### 行为设置
- **模拟人工打字** — 开启后逐字输入，更像真人
- **打字延迟** — 基础延迟和每字符延迟范围（毫秒）
- **消息过期时间** — 超过此时间的消息不自动回复（默认 300 秒）
- **手动接管超时** — 卖家手动接管后自动恢复的时间（默认 3600 秒）
- **接管切换关键词** — 卖家在聊天中发送此关键词切换手动/自动模式（默认 `。`）

## 使用

1. 在 Chrome 中登录闲鱼 (www.goofish.com)
2. 进入闲鱼 IM 聊天页面 (www.goofish.com/im)
3. 插件自动开始工作：
   - 拦截 WebSocket 消息
   - 解析买家消息
   - 调用 LLM 生成回复
   - 通过 DOM 模拟发送

### 手动接管
- 在聊天中发送 `。`（默认关键词）切换该会话的手动/自动模式
- 手动模式下插件不会自动回复该会话
- 超时后自动恢复（默认 1 小时）

### Popup 面板
点击插件图标可以：
- 开/关自动回复
- 查看今日统计（回复数、跳过数、错误数）
- 查看 WebSocket 连接状态

## 架构

```
闲鱼网页 (goofish.com/im)
  └── Chrome Extension
       ├── inject.js          → 拦截 WebSocket 消息
       ├── main.js            → 解析消息、过滤
       ├── dom-sender.js      → DOM 模拟输入发送
       ├── service-worker.js  → LLM 调用、状态管理
       └── popup/options      → UI 面板
```

## 验证

1. 加载插件后打开 `goofish.com/im`
2. 打开 DevTools (F12) → Console
3. 确认看到 `[XianyuBot] Content script initialized`
4. 确认看到 `[XianyuAutoReply:inject] WebSocket hook installed`
5. 用另一个账号发送消息测试自动回复
