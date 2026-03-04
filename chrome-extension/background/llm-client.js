// llm-client.js — LLM API client and Agent system for generating auto-replies.
//
// Ported from Python: XianyuAgent.py (BaseAgent, PriceAgent, TechAgent,
// DefaultAgent, ClassifyAgent, XianyuReplyBot).

import { IntentRouter } from '../shared/intent-router.js';
import { safetyFilter } from '../shared/safety-filter.js';

// ---------------------------------------------------------------------------
// LLM Client — calls OpenAI-compatible API
// ---------------------------------------------------------------------------

export class LLMClient {
  constructor() {
    this.apiKey = '';
    this.baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
    this.modelName = 'qwen-max';
  }

  async init() {
    const settings = await chrome.storage.local.get([
      'apiKey', 'modelBaseUrl', 'modelName',
    ]);
    this.apiKey = settings.apiKey || '';
    this.baseUrl = settings.modelBaseUrl || this.baseUrl;
    this.modelName = settings.modelName || this.modelName;
  }

  updateSettings(settings) {
    if (settings.apiKey) this.apiKey = settings.apiKey;
    if (settings.modelBaseUrl) this.baseUrl = settings.modelBaseUrl;
    if (settings.modelName) this.modelName = settings.modelName;
  }

  /**
   * Call the LLM chat completion API with retry logic.
   * @param {Array<{role: string, content: string}>} messages
   * @param {object} options
   * @returns {Promise<string>} The assistant reply text.
   */
  async chat(messages, options = {}) {
    const {
      temperature = 0.4,
      maxTokens = 500,
      topP = 0.8,
      enableSearch = false,
      maxRetries = 3,
    } = options;

    if (!this.apiKey) {
      throw new Error('API key not configured');
    }

    const url = `${this.baseUrl.replace(/\/$/, '')}/chat/completions`;

    const body = {
      model: this.modelName,
      messages,
      temperature,
      max_tokens: maxTokens,
      top_p: topP,
    };

    if (enableSearch) {
      body.enable_search = true;
    }

    let lastError = null;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`,
          },
          body: JSON.stringify(body),
        });

        if (response.status === 429 || response.status >= 500) {
          // Rate limit or server error — retry with exponential backoff
          const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
          console.warn(`[XianyuBot] LLM API ${response.status}, retrying in ${delay}ms (${attempt + 1}/${maxRetries})`);
          await new Promise(r => setTimeout(r, delay));
          continue;
        }

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`LLM API error ${response.status}: ${errText}`);
        }

        const data = await response.json();
        return data.choices?.[0]?.message?.content || '';
      } catch (err) {
        lastError = err;
        if (attempt < maxRetries - 1) {
          const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
          console.warn(`[XianyuBot] LLM request failed, retrying in ${delay}ms:`, err.message);
          await new Promise(r => setTimeout(r, delay));
        }
      }
    }

    throw lastError || new Error('LLM API failed after retries');
  }
}

// ---------------------------------------------------------------------------
// Agent System — orchestrates intent routing + LLM calls
// ---------------------------------------------------------------------------

export class AgentSystem {
  constructor(llmClient) {
    this.llm = llmClient;
    this.prompts = {}; // { classify, price, tech, default }
    this.router = new IntentRouter();
    this.lastIntent = null;
  }

  /**
   * Load prompt templates.
   * @param {object} prompts - { classify, price, tech, default }
   */
  loadPrompts(prompts) {
    this.prompts = prompts || {};
  }

  /**
   * Generate a reply for an incoming buyer message.
   *
   * @param {string} userMsg      - The buyer's message.
   * @param {string} itemDesc     - Item description string.
   * @param {string} context      - Formatted conversation history.
   * @param {number} bargainCount - Number of price negotiations so far.
   * @returns {Promise<{reply: string, intent: string}>}
   */
  async generateReply(userMsg, itemDesc, context, bargainCount = 0) {
    // 1. Classify intent
    const intent = await this.router.detect(
      userMsg,
      itemDesc,
      context,
      (msg, desc, ctx) => this._classifyWithLLM(msg, desc, ctx),
    );

    this.lastIntent = intent;

    if (intent === 'no_reply') {
      return { reply: '-', intent };
    }

    // 2. Select prompt and build messages
    const validIntents = ['price', 'tech', 'default'];
    const effectiveIntent = validIntents.includes(intent) ? intent : 'default';
    const systemPrompt = this.prompts[effectiveIntent] || this.prompts.default || '';
    const messages = this._buildMessages(
      userMsg, itemDesc, context, systemPrompt, effectiveIntent, bargainCount,
    );

    // 3. Call LLM with intent-specific settings
    const options = this._getOptions(effectiveIntent, bargainCount);
    const reply = await this.llm.chat(messages, options);

    // 4. Safety filter
    const filtered = safetyFilter(reply);

    return { reply: filtered, intent: effectiveIntent };
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  _buildMessages(userMsg, itemDesc, context, systemPrompt, intent, bargainCount) {
    let systemContent =
      `【商品信息】${itemDesc}\n【你与客户对话历史】${context}\n${systemPrompt}`;

    if (intent === 'price' && bargainCount > 0) {
      systemContent += `\n▲当前议价轮次：${bargainCount}`;
    }

    return [
      { role: 'system', content: systemContent },
      { role: 'user', content: userMsg },
    ];
  }

  _getOptions(intent, bargainCount) {
    switch (intent) {
      case 'price':
        return { temperature: Math.min(0.3 + bargainCount * 0.15, 0.9) };
      case 'tech':
        return { temperature: 0.4, enableSearch: true };
      case 'default':
        return { temperature: 0.7 };
      default:
        return { temperature: 0.4 };
    }
  }

  async _classifyWithLLM(userMsg, itemDesc, context) {
    const classifyPrompt = this.prompts.classify || '';
    const messages = [
      {
        role: 'system',
        content: `【商品信息】${itemDesc}\n【你与客户对话历史】${context}\n${classifyPrompt}`,
      },
      { role: 'user', content: userMsg },
    ];

    try {
      const result = await this.llm.chat(messages, { temperature: 0.4 });
      const cleaned = result.trim().toLowerCase();
      if (['tech', 'price', 'default', 'no_reply'].includes(cleaned)) {
        return cleaned;
      }
    } catch (err) {
      console.error('[XianyuBot] LLM classify failed:', err);
    }
    return 'default';
  }
}
