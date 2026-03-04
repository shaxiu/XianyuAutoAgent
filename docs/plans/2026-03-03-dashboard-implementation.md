# XianyuAutoAgent Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Next.js dashboard on Vercel + Supabase backend to monitor and manage XianyuAutoAgent bot instances.

**Architecture:** Bot (Linux) writes conversations/logs to Supabase and reads config from it. Next.js dashboard (Vercel) displays data and allows config editing. Supabase Edge Function sends email on errors.

**Tech Stack:** Next.js 14 (App Router), Tailwind CSS, shadcn/ui, Supabase (PostgreSQL + Realtime + Edge Functions), supabase-py (bot side), Resend (email)

---

## Phase 1: Supabase Setup & Bot Integration

### Task 1: Supabase Database Schema

**Files:**
- Create: `supabase/schema.sql`

**Step 1: Write the SQL schema file**

```sql
-- supabase/schema.sql
-- Run this in Supabase SQL Editor to set up the database

-- Accounts table
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    cookies_str TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    model_base_url TEXT NOT NULL DEFAULT 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model_name TEXT NOT NULL DEFAULT 'qwen-max',
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'error')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Prompts table
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('classify', 'price', 'tech', 'default')),
    content TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(account_id, type)
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    chat_id TEXT NOT NULL,
    item_id TEXT,
    item_title TEXT,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    intent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_conversations_account ON conversations(account_id);
CREATE INDEX idx_conversations_chat ON conversations(chat_id);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- Logs table
CREATE TABLE logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    level TEXT NOT NULL CHECK (level IN ('INFO', 'WARNING', 'ERROR')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_logs_account ON logs(account_id);
CREATE INDEX idx_logs_level ON logs(level);
CREATE INDEX idx_logs_created ON logs(created_at DESC);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER prompts_updated_at
    BEFORE UPDATE ON prompts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Enable Row Level Security (optional, for API key protection)
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (bot and dashboard both use service key)
CREATE POLICY "service_role_all" ON accounts FOR ALL USING (true);
CREATE POLICY "service_role_all" ON prompts FOR ALL USING (true);
CREATE POLICY "service_role_all" ON conversations FOR ALL USING (true);
CREATE POLICY "service_role_all" ON logs FOR ALL USING (true);
```

**Step 2: Commit**

```bash
git add supabase/schema.sql
git commit -m "feat: add Supabase database schema"
```

---

### Task 2: Bot Supabase Sync Module

**Files:**
- Create: `supabase_sync.py`
- Modify: `requirements.txt` (add `supabase` dependency)

**Step 1: Add supabase dependency to requirements.txt**

Add this line to `requirements.txt`:
```
supabase==2.13.0
```

**Step 2: Write supabase_sync.py**

```python
"""
Supabase sync module for XianyuAutoAgent.
Handles:
- Reading config (API key, cookies, prompts) from Supabase
- Writing conversation records to Supabase
- Writing logs to Supabase
- Updating account status
"""

import os
import time
import threading
from datetime import datetime
from loguru import logger

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class SupabaseSync:
    """Syncs bot data with Supabase cloud database."""

    def __init__(self):
        self.enabled = False
        self.client: Client = None
        self.account_id = os.getenv("ACCOUNT_ID", "")
        self._log_buffer = []
        self._log_lock = threading.Lock()
        self._flush_interval = 5  # seconds
        self._last_flush = time.time()

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")

        if not SUPABASE_AVAILABLE:
            logger.warning("supabase package not installed, cloud sync disabled")
            return

        if not url or not key or not self.account_id:
            logger.info("Supabase env vars not set, cloud sync disabled")
            return

        try:
            self.client = create_client(url, key)
            self.enabled = True
            logger.info(f"Supabase sync enabled for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to init Supabase client: {e}")

    def get_account_config(self) -> dict:
        """Fetch account config from Supabase. Returns dict with keys:
        cookies_str, api_key, model_base_url, model_name
        Returns empty dict if disabled or error.
        """
        if not self.enabled:
            return {}
        try:
            result = (
                self.client.table("accounts")
                .select("*")
                .eq("id", self.account_id)
                .single()
                .execute()
            )
            return result.data or {}
        except Exception as e:
            logger.error(f"Failed to fetch account config: {e}")
            return {}

    def get_prompts(self) -> dict:
        """Fetch prompts from Supabase. Returns dict like:
        {"classify": "...", "price": "...", "tech": "...", "default": "..."}
        """
        if not self.enabled:
            return {}
        try:
            result = (
                self.client.table("prompts")
                .select("type, content")
                .eq("account_id", self.account_id)
                .execute()
            )
            return {row["type"]: row["content"] for row in (result.data or [])}
        except Exception as e:
            logger.error(f"Failed to fetch prompts: {e}")
            return {}

    def update_status(self, status: str):
        """Update account status: online, offline, error"""
        if not self.enabled:
            return
        try:
            self.client.table("accounts").update(
                {"status": status}
            ).eq("id", self.account_id).execute()
        except Exception as e:
            logger.error(f"Failed to update status: {e}")

    def log_conversation(self, chat_id: str, item_id: str, item_title: str,
                         role: str, content: str, intent: str = None):
        """Write a conversation message to Supabase."""
        if not self.enabled:
            return
        try:
            self.client.table("conversations").insert({
                "account_id": self.account_id,
                "chat_id": chat_id,
                "item_id": item_id,
                "item_title": item_title or "",
                "role": role,
                "content": content,
                "intent": intent,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

    def buffer_log(self, level: str, message: str):
        """Buffer a log entry. Flushed every _flush_interval seconds."""
        if not self.enabled:
            return
        with self._log_lock:
            self._log_buffer.append({
                "account_id": self.account_id,
                "level": level,
                "message": message[:2000],  # truncate long messages
            })

    def flush_logs(self):
        """Flush buffered logs to Supabase."""
        if not self.enabled:
            return
        with self._log_lock:
            if not self._log_buffer:
                return
            batch = self._log_buffer.copy()
            self._log_buffer.clear()

        try:
            self.client.table("logs").insert(batch).execute()
        except Exception as e:
            logger.error(f"Failed to flush logs: {e}")

    def maybe_flush_logs(self):
        """Flush logs if enough time has passed."""
        now = time.time()
        if now - self._last_flush >= self._flush_interval:
            self.flush_logs()
            self._last_flush = now


# Global singleton
_sync_instance = None


def get_sync() -> SupabaseSync:
    """Get or create the global SupabaseSync instance."""
    global _sync_instance
    if _sync_instance is None:
        _sync_instance = SupabaseSync()
    return _sync_instance
```

**Step 3: Commit**

```bash
git add supabase_sync.py requirements.txt
git commit -m "feat: add Supabase sync module for bot"
```

---

### Task 3: Integrate Supabase Sync into Bot

**Files:**
- Modify: `main.py` (add sync calls at key points)

**Step 1: Add Supabase config loading at startup**

In `main.py`, after the `load_dotenv()` calls (around line 754), add Supabase config override logic:

```python
# After existing load_dotenv calls, before check_and_complete_env():

from supabase_sync import get_sync

# Try to load config from Supabase (overrides .env)
sync = get_sync()
cloud_config = sync.get_account_config()
if cloud_config:
    if cloud_config.get("cookies_str"):
        os.environ["COOKIES_STR"] = cloud_config["cookies_str"]
    if cloud_config.get("api_key"):
        os.environ["API_KEY"] = cloud_config["api_key"]
    if cloud_config.get("model_base_url"):
        os.environ["MODEL_BASE_URL"] = cloud_config["model_base_url"]
    if cloud_config.get("model_name"):
        os.environ["MODEL_NAME"] = cloud_config["model_name"]
    logger.info("Loaded config from Supabase")
```

**Step 2: Add conversation logging in handle_message**

In `main.py` `handle_message()`, after `self.context_manager.add_message_by_chat(...)` calls for both user and assistant messages, add:

After user message save (around line 523):
```python
# Sync user message to Supabase
item_title = item_info.get('title', '') if item_info else ''
get_sync().log_conversation(chat_id, item_id, item_title, "user", send_message)
```

After bot reply save (around line 532):
```python
# Sync bot reply to Supabase
get_sync().log_conversation(chat_id, item_id, item_title, "assistant", bot_reply, intent=bot.last_intent)
get_sync().maybe_flush_logs()
```

**Step 3: Add status updates**

In `main.py`, after successful WebSocket init (after line 189 `logger.info('连接注册完成')`):
```python
get_sync().update_status("online")
```

In the `except` blocks of `main()` (around lines 678-682):
```python
get_sync().update_status("offline")
```

**Step 4: Add custom loguru sink for Supabase**

In `main.py`, after the existing `logger.add(sys.stderr, ...)` call (around line 764), add:

```python
# Add Supabase log sink for WARNING+ levels
def supabase_log_sink(message):
    record = message.record
    if record["level"].no >= 30:  # WARNING = 30, ERROR = 40
        level = "ERROR" if record["level"].no >= 40 else "WARNING"
        get_sync().buffer_log(level, str(message).strip())

logger.add(supabase_log_sink, level="WARNING")
```

**Step 5: Commit**

```bash
git add main.py
git commit -m "feat: integrate Supabase sync into bot main loop"
```

---

### Task 4: Support Supabase Prompts in XianyuAgent

**Files:**
- Modify: `XianyuAgent.py` (allow prompts from Supabase)

**Step 1: Modify _init_system_prompts to accept cloud prompts**

In `XianyuAgent.py`, modify the `_init_system_prompts` method to check Supabase first:

```python
def _init_system_prompts(self):
    """Load prompts: Supabase > local files > example files"""
    from supabase_sync import get_sync
    cloud_prompts = get_sync().get_prompts()

    prompt_dir = "prompts"

    def load_prompt_content(name: str, prompt_type: str) -> str:
        # Check cloud first
        if cloud_prompts.get(prompt_type):
            logger.debug(f"Loaded {prompt_type} prompt from Supabase, length: {len(cloud_prompts[prompt_type])}")
            return cloud_prompts[prompt_type]

        # Fall back to local files
        target_path = os.path.join(prompt_dir, f"{name}.txt")
        if os.path.exists(target_path):
            file_path = target_path
        else:
            file_path = os.path.join(prompt_dir, f"{name}_example.txt")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            logger.debug(f"Loaded {name} prompt from file: {file_path}, length: {len(content)}")
            return content

    try:
        self.classify_prompt = load_prompt_content("classify_prompt", "classify")
        self.price_prompt = load_prompt_content("price_prompt", "price")
        self.tech_prompt = load_prompt_content("tech_prompt", "tech")
        self.default_prompt = load_prompt_content("default_prompt", "default")
        logger.info("All prompts loaded successfully")
    except Exception as e:
        logger.error(f"Error loading prompts: {e}")
        raise
```

**Step 2: Commit**

```bash
git add XianyuAgent.py
git commit -m "feat: support loading prompts from Supabase"
```

---

## Phase 2: Next.js Dashboard

### Task 5: Initialize Next.js Project

**Files:**
- Create: `dashboard/` directory with Next.js project

**Step 1: Create Next.js app with create-next-app**

```bash
cd "/Users/remusdu/Github/Xianyu AutoAgent"
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
```

**Step 2: Install dependencies**

```bash
cd dashboard
npm install @supabase/supabase-js @supabase/ssr jose
npm install -D @types/node
```

Note: `jose` is for JWT-based password auth. shadcn/ui will be added next.

**Step 3: Initialize shadcn/ui**

```bash
cd dashboard
npx shadcn@latest init -d
```

**Step 4: Add required shadcn components**

```bash
npx shadcn@latest add button card input label select tabs textarea badge table dialog separator dropdown-menu
```

**Step 5: Commit**

```bash
cd "/Users/remusdu/Github/Xianyu AutoAgent"
git add dashboard/
git commit -m "feat: initialize Next.js dashboard project"
```

---

### Task 6: Supabase Client & Auth Setup

**Files:**
- Create: `dashboard/src/lib/supabase.ts`
- Create: `dashboard/src/lib/auth.ts`
- Create: `dashboard/src/middleware.ts`
- Modify: `dashboard/.env.local` (add env vars)

**Step 1: Create .env.local**

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
DASHBOARD_PASSWORD=your_dashboard_password
JWT_SECRET=your_random_32char_secret
```

**Step 2: Create Supabase server client**

```typescript
// dashboard/src/lib/supabase.ts
import { createClient } from "@supabase/supabase-js";

export function createSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}
```

**Step 3: Create auth utilities**

```typescript
// dashboard/src/lib/auth.ts
import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

const secret = new TextEncoder().encode(process.env.JWT_SECRET!);

export async function createSession() {
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("7d")
    .sign(secret);
  (await cookies()).set("session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });
}

export async function verifySession(): Promise<boolean> {
  const token = (await cookies()).get("session")?.value;
  if (!token) return false;
  try {
    await jwtVerify(token, secret);
    return true;
  } catch {
    return false;
  }
}

export async function deleteSession() {
  (await cookies()).delete("session");
}
```

**Step 4: Create middleware for auth protection**

```typescript
// dashboard/src/middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

export async function middleware(request: NextRequest) {
  // Allow login page and login API
  if (
    request.nextUrl.pathname === "/login" ||
    request.nextUrl.pathname === "/api/auth/login"
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get("session")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const secret = new TextEncoder().encode(process.env.JWT_SECRET!);
    await jwtVerify(token, secret);
    return NextResponse.next();
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

**Step 5: Commit**

```bash
git add dashboard/src/lib/ dashboard/src/middleware.ts dashboard/.env.local
git commit -m "feat: add Supabase client and auth setup"
```

---

### Task 7: Login Page & Auth API

**Files:**
- Create: `dashboard/src/app/login/page.tsx`
- Create: `dashboard/src/app/api/auth/login/route.ts`
- Create: `dashboard/src/app/api/auth/logout/route.ts`

**Step 1: Create login API route**

```typescript
// dashboard/src/app/api/auth/login/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSession } from "@/lib/auth";

export async function POST(request: NextRequest) {
  const { password } = await request.json();

  if (password !== process.env.DASHBOARD_PASSWORD) {
    return NextResponse.json({ error: "Wrong password" }, { status: 401 });
  }

  await createSession();
  return NextResponse.json({ ok: true });
}
```

**Step 2: Create logout API route**

```typescript
// dashboard/src/app/api/auth/logout/route.ts
import { NextResponse } from "next/server";
import { deleteSession } from "@/lib/auth";

export async function POST() {
  await deleteSession();
  return NextResponse.json({ ok: true });
}
```

**Step 3: Create login page**

```tsx
// dashboard/src/app/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (res.ok) {
      router.push("/");
    } else {
      setError("Password incorrect");
    }
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">Xianyu Dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "..." : "Login"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add dashboard/src/app/login/ dashboard/src/app/api/auth/
git commit -m "feat: add login page and auth API routes"
```

---

### Task 8: Dashboard Layout & Navigation

**Files:**
- Modify: `dashboard/src/app/layout.tsx`
- Create: `dashboard/src/components/nav.tsx`
- Create: `dashboard/src/components/account-selector.tsx`

**Step 1: Create account selector component**

```tsx
// dashboard/src/components/account-selector.tsx
"use client";

import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Account = { id: string; name: string; status: string };

export function AccountSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const [accounts, setAccounts] = useState<Account[]>([]);

  useEffect(() => {
    fetch("/api/accounts")
      .then((r) => r.json())
      .then(setAccounts);
  }, []);

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-48">
        <SelectValue placeholder="Select account" />
      </SelectTrigger>
      <SelectContent>
        {accounts.map((a) => (
          <SelectItem key={a.id} value={a.id}>
            {a.name}
            <span className="ml-2 text-xs">
              {a.status === "online" ? "🟢" : a.status === "error" ? "🔴" : "⚪"}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

**Step 2: Create navigation component**

```tsx
// dashboard/src/components/nav.tsx
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/conversations", label: "Conversations" },
  { href: "/logs", label: "Logs" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
  }

  return (
    <nav className="border-b bg-white px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="font-bold text-lg">Xianyu Monitor</span>
        <div className="flex gap-2">
          {links.map((link) => (
            <Link key={link.href} href={link.href}>
              <Button
                variant={pathname === link.href ? "default" : "ghost"}
                size="sm"
              >
                {link.label}
              </Button>
            </Link>
          ))}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={handleLogout}>
        Logout
      </Button>
    </nav>
  );
}
```

**Step 3: Update root layout**

Replace `dashboard/src/app/layout.tsx`:

```tsx
// dashboard/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Xianyu Dashboard",
  description: "Monitor and manage Xianyu AutoAgent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

**Step 4: Commit**

```bash
git add dashboard/src/components/ dashboard/src/app/layout.tsx
git commit -m "feat: add dashboard layout with nav and account selector"
```

---

### Task 9: API Routes for Data

**Files:**
- Create: `dashboard/src/app/api/accounts/route.ts`
- Create: `dashboard/src/app/api/conversations/route.ts`
- Create: `dashboard/src/app/api/logs/route.ts`
- Create: `dashboard/src/app/api/settings/route.ts`
- Create: `dashboard/src/app/api/settings/prompts/route.ts`

**Step 1: Accounts API**

```typescript
// dashboard/src/app/api/accounts/route.ts
import { NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET() {
  const supabase = createSupabaseClient();
  const { data, error } = await supabase
    .from("accounts")
    .select("id, name, status, created_at")
    .order("created_at", { ascending: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
```

**Step 2: Conversations API**

```typescript
// dashboard/src/app/api/conversations/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const accountId = searchParams.get("account_id");
  const chatId = searchParams.get("chat_id");
  const limit = parseInt(searchParams.get("limit") || "50");
  const offset = parseInt(searchParams.get("offset") || "0");

  const supabase = createSupabaseClient();
  let query = supabase
    .from("conversations")
    .select("*")
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (accountId) query = query.eq("account_id", accountId);
  if (chatId) query = query.eq("chat_id", chatId);

  const { data, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
```

**Step 3: Logs API**

```typescript
// dashboard/src/app/api/logs/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const accountId = searchParams.get("account_id");
  const level = searchParams.get("level");
  const limit = parseInt(searchParams.get("limit") || "100");

  const supabase = createSupabaseClient();
  let query = supabase
    .from("logs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (accountId) query = query.eq("account_id", accountId);
  if (level) query = query.eq("level", level);

  const { data, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
```

**Step 4: Settings API (account config)**

```typescript
// dashboard/src/app/api/settings/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const accountId = new URL(request.url).searchParams.get("account_id");
  if (!accountId) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { data, error } = await supabase
    .from("accounts")
    .select("*")
    .eq("id", accountId)
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  const { account_id, ...updates } = body;
  if (!account_id) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { error } = await supabase
    .from("accounts")
    .update(updates)
    .eq("id", account_id);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
```

**Step 5: Prompts API**

```typescript
// dashboard/src/app/api/settings/prompts/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseClient } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  const accountId = new URL(request.url).searchParams.get("account_id");
  if (!accountId) return NextResponse.json({ error: "account_id required" }, { status: 400 });

  const supabase = createSupabaseClient();
  const { data, error } = await supabase
    .from("prompts")
    .select("*")
    .eq("account_id", accountId);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PUT(request: NextRequest) {
  const { account_id, type, content } = await request.json();
  if (!account_id || !type) {
    return NextResponse.json({ error: "account_id and type required" }, { status: 400 });
  }

  const supabase = createSupabaseClient();
  const { error } = await supabase
    .from("prompts")
    .upsert(
      { account_id, type, content },
      { onConflict: "account_id,type" }
    );

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
```

**Step 6: Commit**

```bash
git add dashboard/src/app/api/
git commit -m "feat: add API routes for accounts, conversations, logs, settings"
```

---

### Task 10: Dashboard Home Page

**Files:**
- Create: `dashboard/src/app/(dashboard)/layout.tsx`
- Create: `dashboard/src/app/(dashboard)/page.tsx`

**Step 1: Create dashboard layout with nav**

```tsx
// dashboard/src/app/(dashboard)/layout.tsx
import { Nav } from "@/components/nav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Nav />
      <main className="p-6">{children}</main>
    </div>
  );
}
```

**Step 2: Create dashboard home page**

```tsx
// dashboard/src/app/(dashboard)/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Account = {
  id: string;
  name: string;
  status: string;
};

type Stats = {
  totalMessages: number;
  todayMessages: number;
  errorCount: number;
};

export default function DashboardPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [stats, setStats] = useState<Record<string, Stats>>({});

  useEffect(() => {
    fetch("/api/accounts")
      .then((r) => r.json())
      .then((data: Account[]) => {
        setAccounts(data);
        // Fetch stats for each account
        data.forEach((account) => {
          Promise.all([
            fetch(`/api/conversations?account_id=${account.id}&limit=1000`).then((r) => r.json()),
            fetch(`/api/logs?account_id=${account.id}&level=ERROR&limit=100`).then((r) => r.json()),
          ]).then(([conversations, errors]) => {
            const today = new Date().toISOString().split("T")[0];
            const todayMsgs = conversations.filter(
              (c: any) => c.created_at?.startsWith(today)
            );
            setStats((prev) => ({
              ...prev,
              [account.id]: {
                totalMessages: conversations.length,
                todayMessages: todayMsgs.length,
                errorCount: errors.length,
              },
            }));
          });
        });
      });
  }, []);

  function statusBadge(status: string) {
    switch (status) {
      case "online":
        return <Badge className="bg-green-500">Online</Badge>;
      case "error":
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="secondary">Offline</Badge>;
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accounts.map((account) => (
          <Card key={account.id}>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{account.name}</CardTitle>
              {statusBadge(account.status)}
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold">
                    {stats[account.id]?.totalMessages ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Total Messages</p>
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats[account.id]?.todayMessages ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Today</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-500">
                    {stats[account.id]?.errorCount ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Errors</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add dashboard/src/app/\(dashboard\)/
git commit -m "feat: add dashboard home page with account status cards"
```

---

### Task 11: Conversations Page

**Files:**
- Create: `dashboard/src/app/(dashboard)/conversations/page.tsx`

**Step 1: Create conversations page**

```tsx
// dashboard/src/app/(dashboard)/conversations/page.tsx
"use client";

import { useEffect, useState } from "react";
import { AccountSelector } from "@/components/account-selector";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Message = {
  id: string;
  chat_id: string;
  item_id: string;
  item_title: string;
  role: string;
  content: string;
  intent: string | null;
  created_at: string;
};

type ChatGroup = {
  chat_id: string;
  item_title: string;
  messages: Message[];
  lastTime: string;
};

export default function ConversationsPage() {
  const [accountId, setAccountId] = useState("");
  const [chatGroups, setChatGroups] = useState<ChatGroup[]>([]);
  const [selectedChat, setSelectedChat] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    fetch(`/api/conversations?account_id=${accountId}&limit=500`)
      .then((r) => r.json())
      .then((data: Message[]) => {
        // Group by chat_id
        const groups: Record<string, ChatGroup> = {};
        // Data comes newest first, reverse for display
        const sorted = [...data].reverse();
        sorted.forEach((msg) => {
          if (!groups[msg.chat_id]) {
            groups[msg.chat_id] = {
              chat_id: msg.chat_id,
              item_title: msg.item_title || msg.item_id,
              messages: [],
              lastTime: msg.created_at,
            };
          }
          groups[msg.chat_id].messages.push(msg);
          groups[msg.chat_id].lastTime = msg.created_at;
        });
        // Sort groups by last message time, newest first
        const sortedGroups = Object.values(groups).sort(
          (a, b) => new Date(b.lastTime).getTime() - new Date(a.lastTime).getTime()
        );
        setChatGroups(sortedGroups);
      });
  }, [accountId]);

  const activeChat = chatGroups.find((g) => g.chat_id === selectedChat);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Conversations</h1>
        <AccountSelector value={accountId} onChange={setAccountId} />
      </div>

      <div className="grid grid-cols-3 gap-4" style={{ minHeight: "70vh" }}>
        {/* Chat list */}
        <div className="col-span-1 space-y-2 overflow-y-auto max-h-[70vh]">
          {chatGroups.map((group) => (
            <Card
              key={group.chat_id}
              className={`cursor-pointer hover:bg-gray-50 ${
                selectedChat === group.chat_id ? "ring-2 ring-blue-500" : ""
              }`}
              onClick={() => setSelectedChat(group.chat_id)}
            >
              <CardContent className="p-3">
                <p className="font-medium text-sm truncate">{group.item_title}</p>
                <p className="text-xs text-gray-500">
                  {group.messages.length} messages
                </p>
                <p className="text-xs text-gray-400">
                  {new Date(group.lastTime).toLocaleString("zh-CN")}
                </p>
              </CardContent>
            </Card>
          ))}
          {chatGroups.length === 0 && accountId && (
            <p className="text-gray-400 text-sm">No conversations</p>
          )}
        </div>

        {/* Chat detail */}
        <div className="col-span-2 overflow-y-auto max-h-[70vh]">
          {activeChat ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{activeChat.item_title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {activeChat.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.role === "assistant" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[70%] rounded-lg px-3 py-2 ${
                        msg.role === "assistant"
                          ? "bg-blue-500 text-white"
                          : "bg-gray-100"
                      }`}
                    >
                      <p className="text-sm">{msg.content}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs opacity-60">
                          {new Date(msg.created_at).toLocaleTimeString("zh-CN")}
                        </span>
                        {msg.intent && (
                          <Badge variant="outline" className="text-xs">
                            {msg.intent}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add dashboard/src/app/\(dashboard\)/conversations/
git commit -m "feat: add conversations page with chat list and detail view"
```

---

### Task 12: Logs Page

**Files:**
- Create: `dashboard/src/app/(dashboard)/logs/page.tsx`

**Step 1: Create logs page**

```tsx
// dashboard/src/app/(dashboard)/logs/page.tsx
"use client";

import { useEffect, useState } from "react";
import { AccountSelector } from "@/components/account-selector";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Log = {
  id: string;
  account_id: string;
  level: string;
  message: string;
  created_at: string;
};

export default function LogsPage() {
  const [accountId, setAccountId] = useState("");
  const [logs, setLogs] = useState<Log[]>([]);
  const [levelFilter, setLevelFilter] = useState<string | null>(null);

  function loadLogs() {
    if (!accountId) return;
    const params = new URLSearchParams({ account_id: accountId, limit: "200" });
    if (levelFilter) params.set("level", levelFilter);
    fetch(`/api/logs?${params}`)
      .then((r) => r.json())
      .then(setLogs);
  }

  useEffect(() => {
    loadLogs();
    // Auto-refresh every 10 seconds
    const interval = setInterval(loadLogs, 10000);
    return () => clearInterval(interval);
  }, [accountId, levelFilter]);

  function levelBadge(level: string) {
    switch (level) {
      case "ERROR":
        return <Badge variant="destructive">ERROR</Badge>;
      case "WARNING":
        return <Badge className="bg-yellow-500">WARNING</Badge>;
      default:
        return <Badge variant="secondary">{level}</Badge>;
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Logs</h1>
        <div className="flex items-center gap-4">
          <div className="flex gap-1">
            {[null, "ERROR", "WARNING", "INFO"].map((level) => (
              <Button
                key={level || "all"}
                variant={levelFilter === level ? "default" : "outline"}
                size="sm"
                onClick={() => setLevelFilter(level)}
              >
                {level || "All"}
              </Button>
            ))}
          </div>
          <AccountSelector value={accountId} onChange={setAccountId} />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">Time</TableHead>
            <TableHead className="w-24">Level</TableHead>
            <TableHead>Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => (
            <TableRow
              key={log.id}
              className={log.level === "ERROR" ? "bg-red-50" : ""}
            >
              <TableCell className="text-xs text-gray-500">
                {new Date(log.created_at).toLocaleString("zh-CN")}
              </TableCell>
              <TableCell>{levelBadge(log.level)}</TableCell>
              <TableCell className="text-sm font-mono">{log.message}</TableCell>
            </TableRow>
          ))}
          {logs.length === 0 && (
            <TableRow>
              <TableCell colSpan={3} className="text-center text-gray-400">
                {accountId ? "No logs" : "Select an account"}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add dashboard/src/app/\(dashboard\)/logs/
git commit -m "feat: add logs page with level filtering and auto-refresh"
```

---

### Task 13: Settings Page

**Files:**
- Create: `dashboard/src/app/(dashboard)/settings/page.tsx`

**Step 1: Create settings page**

```tsx
// dashboard/src/app/(dashboard)/settings/page.tsx
"use client";

import { useEffect, useState } from "react";
import { AccountSelector } from "@/components/account-selector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type AccountConfig = {
  id: string;
  name: string;
  cookies_str: string;
  api_key: string;
  model_base_url: string;
  model_name: string;
};

type Prompt = {
  type: string;
  content: string;
};

const PROMPT_TYPES = ["classify", "price", "tech", "default"] as const;

export default function SettingsPage() {
  const [accountId, setAccountId] = useState("");
  const [config, setConfig] = useState<AccountConfig | null>(null);
  const [prompts, setPrompts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!accountId) return;
    // Load account config
    fetch(`/api/settings?account_id=${accountId}`)
      .then((r) => r.json())
      .then(setConfig);
    // Load prompts
    fetch(`/api/settings/prompts?account_id=${accountId}`)
      .then((r) => r.json())
      .then((data: Prompt[]) => {
        const map: Record<string, string> = {};
        data.forEach((p) => (map[p.type] = p.content));
        setPrompts(map);
      });
  }, [accountId]);

  async function saveConfig() {
    if (!config) return;
    setSaving(true);
    setMessage("");
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        cookies_str: config.cookies_str,
        api_key: config.api_key,
        model_base_url: config.model_base_url,
        model_name: config.model_name,
      }),
    });
    setSaving(false);
    setMessage(res.ok ? "Config saved" : "Save failed");
  }

  async function savePrompt(type: string) {
    setSaving(true);
    setMessage("");
    const res = await fetch("/api/settings/prompts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        type,
        content: prompts[type] || "",
      }),
    });
    setSaving(false);
    setMessage(res.ok ? `${type} prompt saved` : "Save failed");
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <AccountSelector value={accountId} onChange={setAccountId} />
      </div>

      {message && (
        <p className="text-sm text-green-600">{message}</p>
      )}

      {config && (
        <div className="space-y-6">
          {/* Account Config */}
          <Card>
            <CardHeader>
              <CardTitle>Account Config</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>API Key</Label>
                <Input
                  type="password"
                  value={config.api_key}
                  onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                />
              </div>
              <div>
                <Label>Model Base URL</Label>
                <Input
                  value={config.model_base_url}
                  onChange={(e) => setConfig({ ...config, model_base_url: e.target.value })}
                />
              </div>
              <div>
                <Label>Model Name</Label>
                <Input
                  value={config.model_name}
                  onChange={(e) => setConfig({ ...config, model_name: e.target.value })}
                />
              </div>
              <div>
                <Label>Cookies</Label>
                <Textarea
                  rows={3}
                  value={config.cookies_str}
                  onChange={(e) => setConfig({ ...config, cookies_str: e.target.value })}
                />
              </div>
              <Button onClick={saveConfig} disabled={saving}>
                {saving ? "Saving..." : "Save Config"}
              </Button>
            </CardContent>
          </Card>

          {/* Prompts */}
          <Card>
            <CardHeader>
              <CardTitle>Prompts</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="classify">
                <TabsList>
                  {PROMPT_TYPES.map((type) => (
                    <TabsTrigger key={type} value={type}>
                      {type}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {PROMPT_TYPES.map((type) => (
                  <TabsContent key={type} value={type} className="space-y-3">
                    <Textarea
                      rows={15}
                      value={prompts[type] || ""}
                      onChange={(e) =>
                        setPrompts({ ...prompts, [type]: e.target.value })
                      }
                      placeholder={`Enter ${type} prompt...`}
                    />
                    <Button onClick={() => savePrompt(type)} disabled={saving}>
                      {saving ? "Saving..." : `Save ${type} Prompt`}
                    </Button>
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </div>
      )}

      {!config && accountId && (
        <p className="text-gray-400">Loading config...</p>
      )}
      {!accountId && (
        <p className="text-gray-400">Select an account to configure</p>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add dashboard/src/app/\(dashboard\)/settings/
git commit -m "feat: add settings page for config and prompt editing"
```

---

## Phase 3: Email Notification & Deployment

### Task 14: Supabase Edge Function for Email Alerts

**Files:**
- Create: `supabase/functions/notify-error/index.ts`

**Step 1: Write the edge function**

This file is deployed via Supabase CLI (`supabase functions deploy notify-error`). The Database Webhook is configured in Supabase Dashboard to trigger on INSERT to `logs` table where `level = 'ERROR'`.

```typescript
// supabase/functions/notify-error/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const NOTIFY_EMAIL = Deno.env.get("NOTIFY_EMAIL") || "";

serve(async (req) => {
  const payload = await req.json();
  const record = payload.record;

  // Only notify on ERROR
  if (record.level !== "ERROR") {
    return new Response("not error level", { status: 200 });
  }

  // Send email via Resend
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${RESEND_API_KEY}`,
    },
    body: JSON.stringify({
      from: "Xianyu Monitor <onboarding@resend.dev>",
      to: [NOTIFY_EMAIL],
      subject: `[Xianyu Alert] ${record.message.substring(0, 50)}`,
      html: `
        <h2>Xianyu Bot Error Alert</h2>
        <p><strong>Account:</strong> ${record.account_id}</p>
        <p><strong>Level:</strong> ${record.level}</p>
        <p><strong>Message:</strong> ${record.message}</p>
        <p><strong>Time:</strong> ${record.created_at}</p>
      `,
    }),
  });

  return new Response(JSON.stringify({ sent: res.ok }), { status: 200 });
});
```

**Step 2: Commit**

```bash
git add supabase/functions/
git commit -m "feat: add Supabase edge function for error email alerts"
```

---

### Task 15: Vercel Deployment Config

**Files:**
- Modify: `dashboard/.gitignore` (ensure .env.local is ignored)
- Create: `dashboard/vercel.json` (optional, usually not needed)

**Step 1: Verify .gitignore includes .env.local**

Check `dashboard/.gitignore` includes `.env.local`. Next.js template should already include it.

**Step 2: Deploy to Vercel**

```bash
cd "/Users/remusdu/Github/Xianyu AutoAgent/dashboard"
npx vercel
```

Follow prompts. Then set environment variables in Vercel dashboard:
- `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DASHBOARD_PASSWORD`
- `JWT_SECRET`

**Step 3: Commit any deployment config**

```bash
git add -A
git commit -m "chore: finalize deployment configuration"
```

---

### Task 16: Update Bot .env.example

**Files:**
- Modify: `.env.example`

**Step 1: Add Supabase env vars to .env.example**

Add these lines to the existing `.env.example`:

```env
# Supabase cloud sync (optional - dashboard features)
SUPABASE_URL=
SUPABASE_KEY=
ACCOUNT_ID=
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add Supabase env vars to .env.example"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | Task 1-4 | Supabase schema + bot sync module + integration |
| 2 | Task 5-13 | Next.js dashboard (all pages) |
| 3 | Task 14-16 | Email alerts + deployment |

**Prerequisites before starting:**
1. Create a Supabase project at https://supabase.com
2. Create a Resend account at https://resend.com (for email alerts)
3. Have a Vercel account ready
