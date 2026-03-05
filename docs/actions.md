# Action Schema

处理器返回动作列表，执行器按顺序执行：

```json
[
  {
    "action_type": "string",
    "payload": {},
    "meta": {}
  }
]
```

## Built-in Action Types

### 1. `send_text`
向目标会话发送文本消息。

```json
{
  "action_type": "send_text",
  "payload": {
    "chat_id": "chat123",
    "to_user_id": "user123",
    "text": "您好，库存充足。"
  },
  "meta": {}
}
```

### 2. `set_manual_mode`
切换会话人工接管模式。

```json
{
  "action_type": "set_manual_mode",
  "payload": {
    "chat_id": "chat123",
    "enabled": true
  },
  "meta": {}
}
```

未知 `action_type` 会被安全忽略并记录 warning。
