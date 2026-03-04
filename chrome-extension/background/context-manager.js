// context-manager.js — Builds and maintains conversation context (product info, chat history) for LLM prompt construction.
//
// Storage schema in chrome.storage.local:
//   'ctx:{chatId}'     -> { messages: [{role, content, timestamp}], itemId }
//   'bargain:{chatId}' -> { count: number, lastUpdated: timestamp }
//   'item:{itemId}'    -> { data: object, lastUpdated: timestamp }

const MAX_MESSAGES_PER_CHAT = 20;

/**
 * ContextManager replaces the Python SQLite-based ChatContextManager with a
 * chrome.storage.local implementation.  It stores per-chat message history,
 * bargain counts, and cached item info — all keyed so they coexist safely with
 * other extension data in local storage.
 */
export class ContextManager {

  // ---------------------------------------------------------------------------
  // Message history
  // ---------------------------------------------------------------------------

  /**
   * Add a message to the chat history for the given chatId.
   *
   * @param {string} chatId   - Unique conversation identifier
   * @param {string} role     - 'user' | 'assistant'
   * @param {string} content  - Message text
   * @param {string|null} itemId - Optional item ID to associate with this chat
   */
  async addMessage(chatId, role, content, itemId = null) {
    const key = `ctx:${chatId}`;
    const stored = await chrome.storage.local.get(key);
    const ctx = stored[key] || { messages: [], itemId: null };

    ctx.messages.push({
      role,
      content,
      timestamp: Date.now(),
    });

    // Keep only the most recent N messages to stay within storage limits.
    if (ctx.messages.length > MAX_MESSAGES_PER_CHAT) {
      ctx.messages = ctx.messages.slice(-MAX_MESSAGES_PER_CHAT);
    }

    if (itemId) ctx.itemId = itemId;

    await chrome.storage.local.set({ [key]: ctx });
  }

  /**
   * Get conversation context for a chat.
   * Returns an array of { role, content } objects, with a trailing system
   * message indicating the bargain count when it is greater than zero.
   *
   * @param {string} chatId
   * @returns {Promise<Array<{role: string, content: string}>>}
   */
  async getContext(chatId) {
    const key = `ctx:${chatId}`;
    const stored = await chrome.storage.local.get(key);
    const ctx = stored[key] || { messages: [] };

    const messages = ctx.messages.map(m => ({ role: m.role, content: m.content }));

    // Append bargain count as a system hint when relevant.
    const bargainCount = await this.getBargainCount(chatId);
    if (bargainCount > 0) {
      messages.push({ role: 'system', content: `\u8BAE\u4EF7\u6B21\u6570: ${bargainCount}` });
    }

    return messages;
  }

  /**
   * Format context as a plain-text string suitable for inclusion in an LLM
   * prompt.  Only user and assistant turns are included.
   *
   * @param {string} chatId
   * @returns {Promise<string>}
   */
  async getFormattedContext(chatId) {
    const context = await this.getContext(chatId);
    return context
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => `${m.role}: ${m.content}`)
      .join('\n');
  }

  // ---------------------------------------------------------------------------
  // Bargain count tracking
  // ---------------------------------------------------------------------------

  /**
   * Increment the bargain (price negotiation) count for a chat and return the
   * new value.
   *
   * @param {string} chatId
   * @returns {Promise<number>}
   */
  async incrementBargainCount(chatId) {
    const key = `bargain:${chatId}`;
    const stored = await chrome.storage.local.get(key);
    const data = stored[key] || { count: 0 };
    data.count += 1;
    data.lastUpdated = Date.now();
    await chrome.storage.local.set({ [key]: data });
    return data.count;
  }

  /**
   * Get the current bargain count for a chat.
   *
   * @param {string} chatId
   * @returns {Promise<number>}
   */
  async getBargainCount(chatId) {
    const key = `bargain:${chatId}`;
    const stored = await chrome.storage.local.get(key);
    return (stored[key] || { count: 0 }).count;
  }

  // ---------------------------------------------------------------------------
  // Item info cache
  // ---------------------------------------------------------------------------

  /**
   * Save item (product) info to the local cache.
   *
   * @param {string} itemId
   * @param {object} itemData - Raw item data object from Xianyu
   */
  async saveItemInfo(itemId, itemData) {
    const key = `item:${itemId}`;
    await chrome.storage.local.set({
      [key]: {
        data: itemData,
        lastUpdated: Date.now(),
      },
    });
  }

  /**
   * Retrieve cached item info.  Returns null if the item is not cached or if
   * the cache entry is older than 24 hours.
   *
   * @param {string} itemId
   * @returns {Promise<object|null>}
   */
  async getItemInfo(itemId) {
    const key = `item:${itemId}`;
    const stored = await chrome.storage.local.get(key);
    const item = stored[key];
    if (!item) return null;

    // Expire after 24 hours.
    const TWENTY_FOUR_HOURS = 24 * 60 * 60 * 1000;
    if (Date.now() - item.lastUpdated > TWENTY_FOUR_HOURS) {
      await chrome.storage.local.remove(key);
      return null;
    }

    return item.data;
  }

  // ---------------------------------------------------------------------------
  // Item description builder  (port from Python context_manager.py)
  // ---------------------------------------------------------------------------

  /**
   * Build a human-readable item description string for inclusion in an LLM
   * prompt.  Mirrors the Python build_item_description logic.
   *
   * @param {object|null} itemInfo - Raw item data as returned by getItemInfo()
   * @returns {string}
   */
  buildItemDescription(itemInfo) {
    if (!itemInfo) return '\u5546\u54C1\u4FE1\u606F\u6682\u65E0';

    const cleanSkus = [];
    const rawSkuList = itemInfo.skuList || [];

    for (const sku of rawSkuList) {
      const specs = (sku.propertyList || [])
        .filter(p => p.valueText)
        .map(p => p.valueText);
      const specText = specs.length > 0 ? specs.join(' ') : '\u9ED8\u8BA4\u89C4\u683C';

      cleanSkus.push({
        spec: specText,
        price: formatPrice(sku.price),
        stock: sku.quantity || 0,
      });
    }

    // Determine a price display string from SKU prices or the main soldPrice.
    const validPrices = cleanSkus.map(s => s.price).filter(p => p > 0);
    let priceDisplay;

    if (validPrices.length > 0) {
      const minPrice = Math.min(...validPrices);
      const maxPrice = Math.max(...validPrices);
      priceDisplay = minPrice === maxPrice
        ? `\u00A5${minPrice}`
        : `\u00A5${minPrice} - \u00A5${maxPrice}`;
    } else {
      const mainPrice = Math.round(parseFloat(itemInfo.soldPrice || 0) * 100) / 100;
      priceDisplay = `\u00A5${mainPrice}`;
    }

    const summary = {
      title: itemInfo.title || '',
      desc: itemInfo.desc || '',
      price_range: priceDisplay,
      total_stock: itemInfo.quantity || 0,
      sku_details: cleanSkus,
    };

    return `\u5F53\u524D\u5546\u54C1\u7684\u4FE1\u606F\u5982\u4E0B\uFF1A${JSON.stringify(summary)}`;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Convert a raw price value (typically in fen / hundredths) to a two-decimal
 * yuan amount.  Returns 0 on any parse failure.
 *
 * @param {*} price
 * @returns {number}
 */
function formatPrice(price) {
  try {
    return Math.round(parseFloat(price) / 100 * 100) / 100;
  } catch {
    return 0;
  }
}
