// supabase-client.js — Supabase REST API client for cloud sync.
// Uses direct PostgREST API calls (no SDK) to keep the extension lightweight.
//
// Ported from Python: supabase_sync.py

export class SupabaseClient {
  constructor() {
    this.url = '';
    this.apiKey = '';
    this.accountId = '';
    this.enabled = false;
    this._logBuffer = [];
    this._lastFlush = Date.now();
    this._flushInterval = 5000;
  }

  async init() {
    const settings = await chrome.storage.local.get([
      'supabaseUrl', 'supabaseKey', 'accountId',
    ]);
    this.url = settings.supabaseUrl || '';
    this.apiKey = settings.supabaseKey || '';
    this.accountId = settings.accountId || '';
    this.enabled = !!(this.url && this.apiKey && this.accountId);

    if (this.enabled) {
      console.log('[XianyuBot] Supabase sync enabled for account:', this.accountId);
    } else {
      console.log('[XianyuBot] Supabase sync disabled (missing config)');
    }
  }

  /**
   * Make a request to the Supabase PostgREST API.
   */
  async _request(method, table, options = {}) {
    if (!this.enabled) return null;

    const { body, filter, select } = options;

    let url = `${this.url}/rest/v1/${table}`;

    const searchParams = new URLSearchParams();
    if (select) searchParams.set('select', select);
    if (filter) {
      for (const [key, value] of Object.entries(filter)) {
        searchParams.set(key, value);
      }
    }

    const queryString = searchParams.toString();
    if (queryString) url += `?${queryString}`;

    const headers = {
      'apikey': this.apiKey,
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
    };
    if (method === 'POST') {
      headers['Prefer'] = 'return=minimal';
    }

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const errText = await response.text();
        console.error(`[XianyuBot] Supabase ${method} ${table} failed:`, response.status, errText);
        return null;
      }

      if (method === 'GET') {
        return await response.json();
      }
      return true;
    } catch (err) {
      console.error('[XianyuBot] Supabase request error:', err);
      return null;
    }
  }

  /** Fetch account config from Supabase. */
  async getAccountConfig() {
    const data = await this._request('GET', 'accounts', {
      select: '*',
      filter: { id: `eq.${this.accountId}` },
    });
    return data?.[0] || {};
  }

  /** Fetch prompts. Returns { classify, price, tech, default }. */
  async getPrompts() {
    const data = await this._request('GET', 'prompts', {
      select: 'type,content',
      filter: { account_id: `eq.${this.accountId}` },
    });
    if (!data) return {};
    const prompts = {};
    for (const row of data) {
      prompts[row.type] = row.content;
    }
    return prompts;
  }

  /** Update account status: online, offline, error. */
  async updateStatus(status) {
    return this._request('PATCH', 'accounts', {
      body: { status },
      filter: { id: `eq.${this.accountId}` },
    });
  }

  /** Log a conversation message. */
  async logConversation(chatId, itemId, itemTitle, role, content, intent = null) {
    return this._request('POST', 'conversations', {
      body: {
        account_id: this.accountId,
        chat_id: chatId,
        item_id: itemId,
        item_title: itemTitle || '',
        role,
        content,
        intent,
      },
    });
  }

  /** Buffer a log entry for batch insert. */
  bufferLog(level, message) {
    if (!this.enabled) return;
    this._logBuffer.push({
      account_id: this.accountId,
      level,
      message: message.substring(0, 2000),
    });
  }

  /** Flush buffered logs to Supabase. */
  async flushLogs() {
    if (!this.enabled || this._logBuffer.length === 0) return;

    const batch = [...this._logBuffer];
    this._logBuffer = [];

    const result = await this._request('POST', 'logs', { body: batch });
    if (!result) {
      this._logBuffer.unshift(...batch);
    }
  }

  /** Flush logs if enough time has passed. */
  async maybeFlushLogs() {
    const now = Date.now();
    if (now - this._lastFlush >= this._flushInterval) {
      await this.flushLogs();
      this._lastFlush = now;
    }
  }
}
