# XianyuAutoAgent Dashboard Design

## Overview

A Next.js web dashboard deployed on Vercel for monitoring and managing XianyuAutoAgent instances. Uses Supabase as the cloud database bridge between the Linux bot server and the Vercel frontend.

## Architecture

```
Linux Server                Supabase              Vercel
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Bot #1 ──────┼────>│ accounts         │<────┤ Next.js Dashboard│
│ Bot #2 ──────┼────>│ conversations    │<────┤                 │
│              │     │ logs             │     │ Pages:          │
│ Reads config │<────│ prompts          │<────┤ /login          │
│ on startup   │     │                  │     │ /dashboard      │
└──────────────┘     │ Webhook ──> Email│     │ /conversations  │
                     └──────────────────┘     │ /logs           │
                                              │ /settings       │
                                              └─────────────────┘
```

## Data Flow

1. Bot writes conversation records and logs to Supabase in real-time
2. Bot reads config (API Key, Cookie, Prompts) from Supabase on startup and periodically
3. Dashboard reads all data from Supabase for display
4. Dashboard writes config changes to Supabase
5. Supabase Database Webhook triggers email on ERROR logs (cookie expiry, connection failures)

## Database Schema (Supabase / PostgreSQL)

### accounts
| Column         | Type      | Description                    |
|----------------|-----------|--------------------------------|
| id             | uuid PK   | Account ID (auto-generated)    |
| name           | text      | Display name (e.g. "Shop #1") |
| cookies_str    | text      | Xianyu cookies                 |
| api_key        | text      | LLM API key                    |
| model_base_url | text      | LLM endpoint URL               |
| model_name     | text      | LLM model name                 |
| status         | text      | online / offline / error       |
| created_at     | timestamptz | Auto-set                     |
| updated_at     | timestamptz | Auto-updated                 |

### prompts
| Column     | Type        | Description                          |
|------------|-------------|--------------------------------------|
| id         | uuid PK     | Auto-generated                       |
| account_id | uuid FK     | References accounts.id               |
| type       | text        | classify / price / tech / default    |
| content    | text        | Prompt content                       |
| updated_at | timestamptz | Auto-updated                         |

### conversations
| Column     | Type        | Description                    |
|------------|-------------|--------------------------------|
| id         | uuid PK     | Auto-generated                 |
| account_id | uuid FK     | References accounts.id         |
| chat_id    | text        | Xianyu chat session ID         |
| item_id    | text        | Product ID                     |
| item_title | text        | Product title                  |
| role       | text        | user / assistant               |
| content    | text        | Message content                |
| intent     | text        | price / tech / default / null  |
| created_at | timestamptz | Auto-set                       |

### logs
| Column     | Type        | Description                    |
|------------|-------------|--------------------------------|
| id         | uuid PK     | Auto-generated                 |
| account_id | uuid FK     | References accounts.id         |
| level      | text        | INFO / WARNING / ERROR         |
| message    | text        | Log message                    |
| created_at | timestamptz | Auto-set                       |

## Next.js Pages

### /login
- Simple password authentication
- Password stored as env var DASHBOARD_PASSWORD on Vercel
- JWT session token in httpOnly cookie

### /dashboard
- Account status cards (online/offline/error indicator)
- Today's message count per account
- Error count (last 24h)
- Quick links to conversations and logs

### /conversations
- Account selector dropdown (top)
- Chat list grouped by chat_id / item
- Click into a chat to see full conversation thread
- Real-time updates via Supabase realtime subscription
- Search by content

### /logs
- Account selector dropdown
- Level filter (INFO / WARNING / ERROR)
- ERROR rows highlighted in red
- Cookie expiry errors prominently displayed
- Auto-refresh

### /settings
- Per-account configuration:
  - API Key (masked input)
  - Model Base URL
  - Model Name
  - Cookies (textarea)
- Prompt editor per account:
  - classify / price / tech / default tabs
  - Textarea with current prompt content
  - Save button

## Bot-Side Changes

### Config loading (new: supabase_sync.py)
- On startup: fetch account config from Supabase by account_id
- Periodic config poll (every 60s) to pick up dashboard changes
- Override .env values with Supabase values

### Conversation sync
- After each message exchange, insert into Supabase conversations table
- Async write to avoid blocking message processing

### Log sync (custom loguru sink)
- Custom loguru sink that writes WARNING+ logs to Supabase logs table
- Batch writes every 5 seconds to reduce API calls
- Update account status to "error" on critical failures

### Cookie expiry handling
- On cookie failure: write ERROR log to Supabase
- Update account status to "error"
- Supabase Database Webhook triggers email notification

## Email Notification

- Supabase Edge Function triggered by Database Webhook
- Fires when logs table gets INSERT with level = 'ERROR'
- Sends email via Resend / SendGrid (free tier)
- Email contains: account name, error message, timestamp

## Bot Environment Variables (new)

| Variable           | Description                        |
|--------------------|------------------------------------|
| SUPABASE_URL       | Supabase project URL               |
| SUPABASE_KEY       | Supabase service role key          |
| ACCOUNT_ID         | This bot instance's account UUID   |

## Multi-Account Deployment

Each bot instance runs with a different ACCOUNT_ID env var:
```bash
# Bot 1
ACCOUNT_ID=uuid-1 python main.py

# Bot 2
ACCOUNT_ID=uuid-2 python main.py
```

## Tech Stack

- **Frontend**: Next.js 14 (App Router), Tailwind CSS, shadcn/ui
- **Database**: Supabase (PostgreSQL)
- **Auth**: Simple password + JWT
- **Deployment**: Vercel (frontend), Linux server (bots)
- **Email**: Supabase Edge Function + Resend
