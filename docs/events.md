# Event Schema

核心事件对象：

```json
{
  "event_id": "string",
  "event_type": "string",
  "occurred_at": 1700000000000,
  "payload": {},
  "meta": {}
}
```

## Built-in Event Types

### 1. `chat.message.received`
```json
{
  "event_id": "chat.message.received:xxxx",
  "event_type": "chat.message.received",
  "occurred_at": 1700000000000,
  "payload": {
    "chat_id": "chat123",
    "user_id": "user123",
    "item_id": "item123",
    "order_status": null,
    "message": "在吗？",
    "sender_name": "买家A",
    "created_at": 1700000000000,
    "raw": {}
  },
  "meta": {}
}
```

### 2. `order.status.changed`
```json
{
  "event_id": "order.status.changed:xxxx",
  "event_type": "order.status.changed",
  "occurred_at": 1700000000000,
  "payload": {
    "chat_id": "chat123",
    "user_id": "buyer123",
    "item_id": null,
    "order_status": "等待卖家发货",
    "raw": {}
  },
  "meta": {}
}
```

`payload` 里约定保留以下通用字段：`chat_id`、`user_id`、`item_id`、`order_status`、`raw`。  
说明：订单事件初始 `item_id` 可能为 `null`，路由阶段会优先尝试用 `chat_id` 回填最近商品映射。
