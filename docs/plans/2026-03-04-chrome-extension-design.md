# Xianyu AutoReply Chrome Extension — 设计文档

> 日期：2026-03-04
> 状态：待实施

---

## 1. 背景与目标

### 现有方案的问题
当前 Python Bot 通过独立 WebSocket 连接闲鱼服务器，每 2 小时刷新 Token 时频繁触发风控（`RGV587_ERROR`），需要手动过滑块验证 + 更新 Cookie 才能恢复。

### 新方案目标
用 Chrome 浏览器插件替代 Python Bot。插件直接在闲鱼网页里运行，复用浏览器的登录态，彻底消除风控问题。

---

## 2. 核心架构

```
闲鱼网页 (goofish.com/im)
  └── Chrome Extension
       ├── inject.js          — 拦截页面 WebSocket 消息
       ├── content script     — 解析消息 + DOM 模拟发送回复
       ├── background worker  — LLM 调用 + Supabase 同步
       └── popup              — 状态面板 + 开关控制

Dashboard (Vercel) ←→ Supabase ←→ Chrome Extension
```

### 数据流

```
1. 买家发送消息
       ↓
2. 闲鱼服务器通过 WebSocket 推送到浏览器
       ↓
3. inject.js 拦截 WS 消息，转发给 content script
       ↓
4. content script 解析消息（MessagePack 解码），提取：
   - chatId, senderId, senderName, message, itemId
       ↓
5. 发送给 background worker
       ↓
6. background worker:
   a. 加载上下文（chrome.storage.local）
   b. 意图分类（关键词匹配 → LLM 兜底）
   c. 选择 Agent（price/tech/default/no_reply）
   d. 调用 LLM API 生成回复
   e. 安全过滤
   f. 返回回复给 content script
       ↓
7. content script:
   a. 导航到对应聊天（如果不在当前会话）
   b. 模拟打字输入回复
   c. 点击发送按钮
       ↓
8. 同时：background worker 异步写入 Supabase（对话记录 + 日志）
       ↓
9. Dashboard 上可查看对话记录、日志、状态
```

---

## 3. 与 Python Bot 的对比

| 方面 | Python Bot | Chrome Extension |
|------|-----------|-----------------|
| 认证方式 | 手动维护 Cookie + Token 刷新 | 浏览器自动处理，零维护 |
| 风控风险 | 频繁触发，需手动恢复 | 零风控，正常浏览器行为 |
| 部署方式 | 需要云服务器 + Python 环境 | 浏览器装插件即可 |
| 消息接收 | 独立 WebSocket 连接 | 复用页面已有的 WebSocket |
| 消息发送 | WebSocket 协议构造 | DOM 模拟输入（最安全） |
| 商品信息 | API 调用（可能触发风控） | 浏览器 Cookie 调 API（零风控） |
| 本地存储 | SQLite | chrome.storage.local |
| 云端同步 | Supabase（相同） | Supabase（相同） |
| Dashboard | 兼容 | 完全兼容（同一套 Supabase 表） |
| 多账号 | 多个 Docker 容器 | 多个 Chrome Profile 或标签页 |
| 稳定性 | 风控导致频繁停机 | 浏览器开着就一直工作 |

---

## 4. 技术方案详述

### 4.1 消息接收：WebSocket 拦截

**为什么不用 DOM 监听？**
- DOM 监听只能看到当前渲染的消息，其他会话的消息看不到
- 闲鱼随时可能改 DOM 结构，容易失效
- 需要逐个点击聊天才能获取消息，效率低

**WebSocket 拦截方案：**
- 在 `document_start` 时注入 `inject.js` 到页面的 MAIN world
- Hook `window.WebSocket`，在页面创建 WS 连接之前拦截
- 闲鱼页面连接 `wss://wss-goofish.dingtalk.com/` 时，自动监听所有收发消息
- 通过 `window.postMessage` 将拦截的消息传给 content script（隔离 world）

```javascript
// inject.js 核心逻辑（简化）
const OriginalWebSocket = window.WebSocket;
window.WebSocket = function(url, protocols) {
  const ws = new OriginalWebSocket(url, protocols);
  if (url.includes('wss-goofish.dingtalk.com')) {
    ws.addEventListener('message', (event) => {
      window.postMessage({ type: 'XIANYU_WS_MESSAGE', data: event.data }, '*');
    });
  }
  return ws;
};
```

**消息解析：**
- 复用 Python Bot 已逆向的消息格式
- 移植 MessagePackDecoder 到 JavaScript
- 消息结构：`body.syncPushPackage.data[0].data` → Base64 解码 → MessagePack 解码
- 提取字段：`message["1"]["10"]["reminderContent"]`（文本）、`senderUserId`、`reminderUrl`（含 itemId）、`message["1"]["2"]`（chatId）

### 4.2 消息发送：DOM 模拟

**为什么不通过 WebSocket 发送？**
- 通过 WS 发送需要复制闲鱼完整的消息构造协议（加密、签名、格式）
- 协议随时可能变化
- DOM 模拟对闲鱼来说就是正常的人工打字操作，最安全

**发送流程：**
1. 找到输入框（contenteditable div 或 textarea）
2. 模拟逐字输入（`document.execCommand('insertText')`）
3. 找到发送按钮并点击
4. 可配置打字延迟（50-200ms/字），模拟真人

**多会话回复队列：**
- WebSocket 拦截能收到所有会话的消息
- 回复时需要先导航到对应聊天（点击聊天列表项）
- 使用队列机制，逐个处理，避免并发冲突

### 4.3 LLM 调用

- 在 background service worker 中调用（避免 CORS、保护 API Key）
- OpenAI 兼容 API（默认 qwen-max via dashscope）
- 移植 Python 的意图分类逻辑：
  - 第一步：关键词/正则匹配（tech 关键词、price 关键词）
  - 第二步：LLM 兜底分类（classify prompt）
- 四种 Agent：PriceAgent、TechAgent、DefaultAgent、ClassifyAgent
- 安全过滤：屏蔽微信/QQ/支付宝/银行卡等敏感词

### 4.4 Supabase 集成

**不引入完整 SDK**（太大，不适合 service worker），直接用 REST API：

```javascript
// 示例：记录对话
await fetch(`${supabaseUrl}/rest/v1/conversations`, {
  method: 'POST',
  headers: {
    'apikey': supabaseKey,
    'Authorization': `Bearer ${supabaseKey}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ account_id, chat_id, role, content, intent })
});
```

**同步内容：**
- 启动时：从 Supabase 拉取 Prompt 配置，缓存到 chrome.storage.local
- 每次对话：异步写入 conversations 表
- 日志：缓冲后批量写入（chrome.alarms 定时 5 秒刷新）
- 状态：开启时设 `online`，关闭时设 `offline`
- Cookie 管理：**不再需要**，浏览器自动处理

### 4.5 上下文管理

- 使用 `chrome.storage.local` 存储每个 chat 的最近 20 条消息
- 议价次数按 chatId 跟踪
- 与 Supabase 异步同步（完整记录在云端，本地只保留最近上下文）

### 4.6 手动接管

- 检测卖家自己发送的切换关键词（如 `xianyu`）
- 对应 chatId 进入手动模式，暂停自动回复
- 再次发送关键词恢复
- 超时 1 小时自动恢复

---

## 5. 文件结构

```
chrome-extension/
  manifest.json                # Manifest V3 配置

  background/
    service-worker.js          # 消息路由、状态管理、定时任务
    llm-client.js              # LLM API 调用（OpenAI 兼容）
    supabase-client.js         # Supabase REST API 客户端
    state-manager.js           # 开关状态、统计数据
    context-manager.js         # 对话上下文（chrome.storage.local）

  content/
    main.js                    # 入口：注入 inject.js，初始化拦截器
    inject.js                  # MAIN world：Hook WebSocket
    ws-interceptor.js          # 监听拦截的 WS 消息
    message-parser.js          # 解析和过滤消息（移植 Python 逻辑）
    dom-sender.js              # DOM 模拟输入和发送

  popup/
    popup.html                 # 弹窗 UI
    popup.js                   # 弹窗逻辑
    popup.css                  # 弹窗样式

  options/
    options.html               # 配置页面
    options.js                 # 配置逻辑

  shared/
    intent-router.js           # 意图分类（关键词 + LLM）
    safety-filter.js           # 安全过滤器
    constants.js               # 常量定义

  lib/
    msgpack-decoder.js         # MessagePack 解码器（移植自 Python）
    md5.js                     # MD5 签名生成

  icons/
    icon16.png                 # 16x16 图标
    icon48.png                 # 48x48 图标
    icon128.png                # 128x128 图标
```

---

## 6. Popup 弹窗设计

```
+------------------------------------+
|  Xianyu AutoReply          v1.0.0  |
+------------------------------------+
|                                    |
|  [======= ON =======]  (开关)     |
|                                    |
|  状态：运行中                       |
|  页面：goofish.com/im              |
|  账号：还是空的呦                    |
|                                    |
|  ---- 今日统计 ----                 |
|  收到消息：  47                     |
|  自动回复：  43                     |
|  跳过：      4                     |
|  错误：      0                     |
|                                    |
|  [打开 Dashboard]                  |
|  [设置]                            |
+------------------------------------+
```

- Badge 图标：绿色=运行中，红色=出错，灰色=关闭

---

## 7. Options 配置页

只管理插件特有的配置，Prompt 编辑继续在 Dashboard 上操作：

- Supabase URL / Service Key / Account ID
- LLM API Key / Base URL / Model Name
- Dashboard URL（快捷链接）
- 打字延迟开关 + 延迟范围（ms）
- 回复前等待时间范围（秒）
- 切换关键词

---

## 8. 实现任务（14 个 Task，6 个阶段）

### Phase 1: 核心基础（Task 1-4）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 1 | 插件脚手架 + manifest.json | `manifest.json` + 目录结构 |
| 2 | WebSocket 拦截 + 消息解析 | `inject.js`, `ws-interceptor.js`, `message-parser.js`, `msgpack-decoder.js` |
| 3 | Background Worker 基础 | `service-worker.js`, `state-manager.js` |
| 4 | Content Script 入口 | `main.js` |

### Phase 2: LLM + 回复（Task 5-7）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 5 | LLM 客户端 + 意图分类 | `llm-client.js`, `intent-router.js`, `safety-filter.js` |
| 6 | 上下文管理 | `context-manager.js` |
| 7 | DOM 发送器 | `dom-sender.js` |

### Phase 3: Supabase 同步（Task 8）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 8 | Supabase REST 客户端 | `supabase-client.js` |

### Phase 4: UI（Task 9-10）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 9 | Popup 弹窗 | `popup.html`, `popup.js`, `popup.css` |
| 10 | Options 配置页 | `options.html`, `options.js` |

### Phase 5: 高级功能（Task 11-12）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 11 | 商品信息获取（浏览器 Cookie 调 API） | content script 内 |
| 12 | 手动接管 + 多标签页去重 + 边界处理 | 多处修改 |

### Phase 6: 测试 + 完善（Task 13-14）

| Task | 描述 | 关键文件 |
|------|------|---------|
| 13 | 错误处理 + 容灾 | 多处修改 |
| 14 | 端到端测试 + 安装说明 | 测试 + 文档 |

---

## 9. Python 源码移植清单

| 要移植的功能 | Python 源文件 | 行号 | JS 目标文件 |
|------------|-------------|------|-----------|
| MessagePack 解码器 | utils/xianyu_utils.py | 72-336 | lib/msgpack-decoder.js |
| MD5 签名生成 | utils/xianyu_utils.py | 61-69 | lib/md5.js |
| 消息类型判断 | main.py | 193-268 | content/message-parser.js |
| 消息字段提取 | main.py | 440-453 | content/message-parser.js |
| 意图分类（关键词+正则） | XianyuAgent.py | 149-199 | shared/intent-router.js |
| LLM Prompt 构建 | XianyuAgent.py | 216-221 | background/llm-client.js |
| 安全过滤 | XianyuAgent.py | 234-260 | shared/safety-filter.js |
| Supabase 同步 | supabase_sync.py | 全文 | background/supabase-client.js |

---

## 10. 风险与应对

| 风险 | 可能性 | 影响 | 应对 |
|------|-------|------|------|
| 闲鱼页面改版导致 DOM 选择器失效 | 中 | 中 | 使用多重选择器降级，快速修复更新 |
| WebSocket Hook 被页面检测 | 低 | 高 | document_start 注入，在页面 JS 执行前完成 Hook |
| MessagePack 格式变化 | 低 | 高 | Python Bot 社区会快速逆向新格式 |
| MV3 Service Worker 休眠 | 中 | 中 | 使用 chrome.alarms 唤醒，消息驱动自然保活 |
| 多标签页重复回复 | 中 | 中 | background worker 按 tabId 去重 |

---

## 11. 验证方法

1. Chrome 开发者模式加载插件（`chrome://extensions` → 加载已解压的扩展）
2. 打开 `goofish.com/im` 并登录
3. F12 DevTools Console 确认 `XIANYU_WS_MESSAGE` 事件正常触发
4. 用另一个账号发消息，验证：
   - 消息被拦截和解析 ✓
   - 意图正确分类 ✓
   - LLM 生成合理回复 ✓
   - 回复自动输入并发送 ✓
   - Dashboard Conversations 页面显示对话记录 ✓
   - Dashboard Logs 页面显示日志 ✓
5. 测试 Popup 开关、手动接管、多会话处理
