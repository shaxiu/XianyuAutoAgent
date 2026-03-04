-- ===========================================
-- XianyuAutoAgent Dashboard - Full Setup SQL
-- Run this in Supabase SQL Editor (one shot)
-- ===========================================

-- ============ 1. CREATE TABLES ============

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

-- ============ 2. TRIGGERS ============

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

-- ============ 3. ROW LEVEL SECURITY ============

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON accounts FOR ALL USING (true);
CREATE POLICY "service_role_all" ON prompts FOR ALL USING (true);
CREATE POLICY "service_role_all" ON conversations FOR ALL USING (true);
CREATE POLICY "service_role_all" ON logs FOR ALL USING (true);

-- ============ 4. SEED DATA: 2 ACCOUNTS ============

INSERT INTO accounts (name) VALUES ('1');
INSERT INTO accounts (name) VALUES ('2');

-- ============ 5. VERIFY ============
-- After running, check the accounts table to get the UUIDs:
-- SELECT id, name, status FROM accounts;
-- Copy these UUIDs for your bot .env ACCOUNT_ID config
