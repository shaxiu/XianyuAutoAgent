# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py

# Run with Docker
docker-compose up -d
```

There is no test suite in this project.

## Configuration

Copy `.env.example` to `.env` and fill in the required values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_KEY` | Yes | — | LLM API key (Alibaba DashScope by default) |
| `COOKIES_STR` | Yes | — | Xianyu/Goofish browser cookies string |
| `MODEL_BASE_URL` | No | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI-compatible API base URL |
| `MODEL_NAME` | No | `qwen-max` | Model name |
| `TOGGLE_KEYWORDS` | No | `。` | Keyword to toggle manual/AI mode per conversation |
| `SIMULATE_HUMAN_TYPING` | No | `False` | Add typing delay before replies |
| `LOG_LEVEL` | No | `DEBUG` | Loguru log level |
| `HEARTBEAT_INTERVAL` | No | `15` | WebSocket heartbeat interval (seconds) |
| `TOKEN_REFRESH_INTERVAL` | No | `3600` | Token refresh interval (seconds) |
| `MANUAL_MODE_TIMEOUT` | No | `3600` | Auto-exit manual mode after this many seconds |
| `MESSAGE_EXPIRE_TIME` | No | `300000` | Ignore messages older than this (milliseconds) |

## Architecture

The bot connects to Goofish's (闲鱼) DingTalk WebSocket server and auto-replies to buyer messages using a multi-agent LLM system.

### Core components

**`main.py` — `XianyuLive`**: WebSocket connection manager. Handles the full connection lifecycle: registration, heartbeat loop, token refresh loop, and message dispatch. Incoming messages are encrypted with MessagePack + base64; decryption happens in `utils/xianyu_utils.py`. The seller can toggle per-conversation manual takeover by sending the `TOGGLE_KEYWORDS` character from their own account.

**`XianyuAgent.py` — `XianyuReplyBot`**: Orchestrates reply generation. `IntentRouter` uses a 3-tier strategy: tech keywords → price keywords → LLM `ClassifyAgent` as fallback. The detected intent routes to one of four agents: `PriceAgent`, `TechAgent`, `DefaultAgent`, or `ClassifyAgent` (internal only). `PriceAgent` uses dynamic temperature that increases with bargain count. `TechAgent` enables web search via `extra_body={"enable_search": True}`. All agents use the OpenAI-compatible client.

**`XianyuApis.py` — `XianyuApis`**: HTTP client for the Goofish platform. Handles token acquisition (`get_token`), item detail fetching (`get_item_info`), and login state checking (`hasLogin`). On token failure it retries, then attempts re-login via `hasLogin`, and exits if cookies are invalid. On risk-control errors (`RGV587_ERROR`) it prompts the user to paste fresh cookies interactively.

**`context_manager.py` — `ChatContextManager`**: SQLite persistence at `data/chat_history.db`. Stores per-conversation message history (keyed by `chat_id`), item info cache, and bargain counts. Bargain count is injected as a `system` message into the context passed to agents.

**`utils/xianyu_utils.py`**: Cookie parsing, request signing (MD5), device/message ID generation, and a pure-Python MessagePack decoder used to decrypt WebSocket messages.

### Prompt customization

Prompts live in `prompts/`. The bot loads `<name>.txt` if it exists, otherwise falls back to `<name>_example.txt`:

- `classify_prompt.txt` — intent classification (returns: `price`, `tech`, `default`, `no_reply`)
- `price_prompt.txt` — price negotiation agent
- `tech_prompt.txt` — technical Q&A agent (has web search enabled)
- `default_prompt.txt` — general customer service agent

### Data flow

```
WebSocket message
  → decrypt (base64 + MessagePack)
  → filter (heartbeat / system / expired / manual mode)
  → fetch item info (SQLite cache → Goofish API)
  → XianyuReplyBot.generate_reply()
      → IntentRouter.detect() [keywords → LLM classify]
      → Agent.generate() [price/tech/default]
  → send_msg() via WebSocket
```
