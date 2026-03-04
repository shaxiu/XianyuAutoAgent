# Xianyu AutoAgent 系统架构

## 1. 技术栈

| 层级 | 技术 | 用途 |
|---|---|---|
| AI 推理 | 通义千问（qwen-max）/ OpenAI 兼容 API | 对话生成、意图分类 |
| Bot 运行时 | Python 3 + asyncio + websockets | 核心业务逻辑 |
| 本地存储 | SQLite | 对话上下文、商品缓存、议价计数 |
| 云端存储 | Supabase（PostgreSQL） | 多端同步、Dashboard 数据源 |
| 管理后台 | Next.js 14 + React + Tailwind CSS | Web Dashboard |
| UI 组件 | shadcn/ui | Dashboard UI 组件库 |
| 浏览器端 | Chrome Extension (Manifest V3) | 备选方案：浏览器内消息拦截 |
| 部署 | Docker / 直接运行 | Bot 部署 |

## 2. 项目结构

```
Xianyu AutoAgent/
├── main.py                     # 入口：WebSocket 连接 + 消息调度
├── XianyuAgent.py              # AI Agent 系统（路由 + 4个Agent）
├── XianyuApis.py               # 闲鱼 HTTP API 封装（Token、商品信息）
├── context_manager.py          # SQLite 对话上下文管理
├── supabase_sync.py            # Supabase 云端同步（单例）
├── utils/
│   └── xianyu_utils.py         # 工具函数（签名、加密、解密、ID生成）
├── prompts/                    # Prompt 模板文件
│   ├── classify_prompt.txt     # 意图分类 Prompt
│   ├── price_prompt.txt        # 议价 Prompt
│   ├── tech_prompt.txt         # 技术咨询 Prompt
│   └── default_prompt.txt      # 默认回复 Prompt
├── data/
│   └── chat_history.db         # SQLite 数据库（运行时生成）
├── .env                        # 环境变量配置
├── .env.example                # 环境变量示例
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 构建
│
├── dashboard/                  # Next.js Dashboard
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx              # 根布局
│   │   │   ├── login/
│   │   │   │   └── page.tsx            # 登录页
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx          # Dashboard 布局（导航栏）
│   │   │   │   ├── page.tsx            # 首页（账户状态）
│   │   │   │   ├── conversations/
│   │   │   │   │   └── page.tsx        # 对话记录页
│   │   │   │   ├── logs/
│   │   │   │   │   └── page.tsx        # 日志页
│   │   │   │   └── settings/
│   │   │   │       └── page.tsx        # 设置页
│   │   │   └── api/
│   │   │       ├── auth/
│   │   │       │   ├── login/route.ts  # 登录接口
│   │   │       │   └── logout/route.ts # 登出接口
│   │   │       ├── accounts/route.ts   # 账户查询接口
│   │   │       ├── conversations/route.ts # 对话查询接口
│   │   │       ├── logs/route.ts       # 日志查询接口
│   │   │       └── settings/
│   │   │           ├── route.ts        # 设置读写接口
│   │   │           └── prompts/route.ts # Prompt 读写接口
│   │   ├── components/
│   │   │   ├── ui/                     # shadcn/ui 基础组件
│   │   │   ├── nav.tsx                 # 侧边导航
│   │   │   ├── account-selector.tsx    # 账户选择器
│   │   │   └── theme-toggle.tsx        # 主题切换
│   │   ├── lib/
│   │   │   ├── supabase.ts            # Supabase 客户端
│   │   │   ├── auth.ts                # JWT 认证工具
│   │   │   └── utils.ts               # 通用工具
│   │   └── middleware.ts               # 路由中间件（认证检查）
│   ├── package.json
│   └── .env.local                      # Dashboard 环境变量
│
├── chrome-extension/           # Chrome 扩展（开发中）
│   ├── manifest.json           # 扩展配置
│   ├── background/
│   │   └── service-worker.js   # 后台服务（消息处理核心）
│   ├── content/
│   │   └── main.js             # 内容脚本（WebSocket 拦截）
│   └── popup/                  # 弹出界面
│
└── docs/                       # 文档体系
    ├── README.md               # 文档索引
    ├── business/               # 业务文档
    ├── technical/              # 技术文档
    └── postmortems/            # 复盘避坑
```

## 3. 数据库 Schema

### 3.1 本地 SQLite（`data/chat_history.db`）

**messages 表**
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| user_id | TEXT | 发送者 ID |
| item_id | TEXT | 商品 ID |
| role | TEXT | user / assistant |
| content | TEXT | 消息内容 |
| timestamp | DATETIME | 时间戳 |
| chat_id | TEXT | 会话 ID |

索引：`idx_user_item(user_id, item_id)`, `idx_chat_id(chat_id)`, `idx_timestamp(timestamp)`

**chat_bargain_counts 表**
| 字段 | 类型 | 说明 |
|---|---|---|
| chat_id | TEXT PK | 会话 ID |
| count | INTEGER | 议价次数 |
| last_updated | DATETIME | 最后更新时间 |

**items 表**
| 字段 | 类型 | 说明 |
|---|---|---|
| item_id | TEXT PK | 商品 ID |
| data | TEXT | 商品完整 JSON 数据 |
| price | REAL | 商品价格 |
| description | TEXT | 商品描述 |
| last_updated | DATETIME | 最后更新时间 |

### 3.2 Supabase（PostgreSQL）

**accounts 表**
| 字段 | 说明 |
|---|---|
| id | 账户 ID（对应 ACCOUNT_ID） |
| name | 账户显示名称 |
| status | online / offline / error |
| cookies_str | 闲鱼登录 Cookie |
| api_key | LLM API Key |
| model_base_url | LLM 端点 |
| model_name | 模型名称 |

**conversations 表**
| 字段 | 说明 |
|---|---|
| account_id | 所属账户 |
| chat_id | 会话 ID |
| item_id | 商品 ID |
| item_title | 商品标题 |
| role | user / assistant |
| content | 消息内容 |
| intent | AI 识别的意图 |
| created_at | 创建时间 |

**prompts 表**
| 字段 | 说明 |
|---|---|
| account_id | 所属账户 |
| type | classify / price / tech / default |
| content | Prompt 内容 |

**logs 表**
| 字段 | 说明 |
|---|---|
| account_id | 所属账户 |
| level | WARNING / ERROR |
| message | 日志内容（最长 2000 字符） |
| created_at | 创建时间 |

## 4. 部署架构

### 方式 1：独立 Python 进程

```
服务器 / 个人电脑
    │
    └── python main.py
          ├── WebSocket → wss://wss-goofish.dingtalk.com/
          ├── HTTP API → h5api.m.goofish.com（商品信息、Token）
          ├── LLM API → dashscope.aliyuncs.com（通义千问）
          └── Supabase → xxx.supabase.co（可选，云同步）
```

### 方式 2：Docker

```
docker build -t xianyu-bot .
docker run --env-file .env xianyu-bot
```

### 方式 3：Chrome 扩展（开发中）

```
浏览器
    │
    └── Chrome Extension
          ├── 拦截 WebSocket 消息（利用浏览器已登录状态）
          ├── Service Worker 处理业务逻辑
          └── 通过 DOM 模拟发送消息
```

## 5. 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `API_KEY` | 是 | — | LLM API Key（通义千问百炼平台获取） |
| `COOKIES_STR` | 是 | — | 闲鱼登录 Cookie |
| `MODEL_BASE_URL` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | LLM API 地址 |
| `MODEL_NAME` | 否 | `qwen-max` | 模型名称 |
| `TOGGLE_KEYWORDS` | 否 | `。` | 人工接管切换关键词 |
| `SIMULATE_HUMAN_TYPING` | 否 | `False` | 模拟人工打字延迟 |
| `HEARTBEAT_INTERVAL` | 否 | `15` | 心跳间隔（秒） |
| `HEARTBEAT_TIMEOUT` | 否 | `5` | 心跳超时（秒） |
| `TOKEN_REFRESH_INTERVAL` | 否 | `7200` | Token 刷新间隔（秒） |
| `TOKEN_RETRY_INTERVAL` | 否 | `300` | Token 重试间隔（秒） |
| `MANUAL_MODE_TIMEOUT` | 否 | `3600` | 人工接管超时（秒） |
| `MESSAGE_EXPIRE_TIME` | 否 | `300000` | 消息过期时间（毫秒） |
| `LOG_LEVEL` | 否 | `DEBUG` | 日志级别 |
| `SUPABASE_URL` | 否 | — | Supabase 项目 URL |
| `SUPABASE_KEY` | 否 | — | Supabase 服务端 Key |
| `ACCOUNT_ID` | 否 | — | Supabase 中的账户 ID |
