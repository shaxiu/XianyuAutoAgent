// state-manager.js — Centralized extension state management: tracks toggle state, active conversations, and runtime config.

/**
 * Default state shape. Every key here is guaranteed to exist after init().
 * Persisted to chrome.storage.local under the key 'xianyuBotState'.
 */
const DEFAULT_STATE = {
  enabled: true,             // Auto-reply master switch
  myId: '',                  // Seller's Xianyu user ID (extracted from cookie)
  toggleKeywords: '\u3002',  // '。' — seller sends this in chat to toggle manual mode
  manualChats: {},           // { [chatId]: timestamp } — chats currently in manual mode
  manualModeTimeout: 3600,   // seconds before a manual-mode chat auto-resumes
  messageExpireTime: 300000, // ms — skip inbound messages older than this
  simulateTyping: true,      // whether to simulate human typing delay before replying
  typingDelayBase: [0, 1000],       // ms range for a fixed base delay
  typingDelayPerChar: [100, 300],   // ms range added per character of reply
  stats: {
    today: { replied: 0, skipped: 0, errors: 0, date: '' },
    total: { replied: 0 },
  },
};

const STORAGE_KEY = 'xianyuBotState';

/**
 * StateManager wraps chrome.storage.local and provides typed helpers for
 * reading/writing extension state.  It keeps an in-memory copy for fast
 * synchronous access between async storage round-trips.
 */
export class StateManager {
  constructor() {
    /** @type {typeof DEFAULT_STATE | null} */
    this._state = null;
    this._initPromise = null;
  }

  // ---------------------------------------------------------------------------
  // Initialisation
  // ---------------------------------------------------------------------------

  /**
   * Load persisted state from chrome.storage.local, merging in defaults for
   * any missing keys.  Safe to call multiple times — subsequent calls return
   * the same promise.
   *
   * @returns {Promise<typeof DEFAULT_STATE>}
   */
  async init() {
    if (this._initPromise) return this._initPromise;

    this._initPromise = (async () => {
      const result = await chrome.storage.local.get(STORAGE_KEY);
      const stored = result[STORAGE_KEY] || {};

      // Deep-merge defaults with stored values so new keys are added on upgrade.
      this._state = this._deepMerge(DEFAULT_STATE, stored);

      // Ensure today's stats bucket matches the current date.
      this._rollStatsIfNeeded();

      // Persist the merged state so any new defaults are saved immediately.
      await this._persist();

      console.log('[XianyuBot] StateManager initialised', this._state);
      return this._state;
    })();

    return this._initPromise;
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Return a *copy* of the current state.  Ensures init has completed first.
   * @returns {Promise<typeof DEFAULT_STATE>}
   */
  async getState() {
    await this.init();
    return { ...this._state };
  }

  /**
   * Toggle the master auto-reply switch and update the badge accordingly.
   * @returns {Promise<{enabled: boolean}>}
   */
  async toggleAutoReply() {
    await this.init();
    this._state.enabled = !this._state.enabled;
    await this._persist();
    await this.updateBadge(this._state.enabled ? 'active' : 'disabled');
    console.log('[XianyuBot] Auto-reply toggled:', this._state.enabled);
    return { enabled: this._state.enabled };
  }

  /**
   * Toggle manual mode for a specific chat.  If the chat is already in manual
   * mode it is removed (auto-reply resumes); otherwise a timestamp is stored.
   *
   * @param {string} chatId
   * @returns {Promise<'manual' | 'auto'>}
   */
  async toggleManualMode(chatId) {
    await this.init();

    if (this._state.manualChats[chatId]) {
      delete this._state.manualChats[chatId];
      await this._persist();
      console.log(`[XianyuBot] Chat ${chatId} switched to AUTO mode`);
      return 'auto';
    }

    this._state.manualChats[chatId] = Date.now();
    await this._persist();
    console.log(`[XianyuBot] Chat ${chatId} switched to MANUAL mode`);
    return 'manual';
  }

  /**
   * Check whether a chat is in manual mode.  If the timeout has expired the
   * chat is automatically switched back to auto mode.
   *
   * @param {string} chatId
   * @returns {Promise<boolean>}
   */
  async isManualMode(chatId) {
    await this.init();

    const timestamp = this._state.manualChats[chatId];
    if (!timestamp) return false;

    const elapsed = (Date.now() - timestamp) / 1000; // seconds
    if (elapsed >= this._state.manualModeTimeout) {
      // Timeout expired — auto-resume
      delete this._state.manualChats[chatId];
      await this._persist();
      console.log(`[XianyuBot] Chat ${chatId} manual mode expired, resuming auto`);
      return false;
    }

    return true;
  }

  /**
   * Merge partial settings into state.  Only keys that already exist in the
   * default state are accepted to prevent stale / unknown keys from creeping in.
   *
   * @param {Partial<typeof DEFAULT_STATE>} settings
   * @returns {Promise<typeof DEFAULT_STATE>}
   */
  async updateSettings(settings) {
    await this.init();

    for (const key of Object.keys(settings)) {
      if (key in DEFAULT_STATE) {
        this._state[key] = settings[key];
      } else {
        console.warn(`[XianyuBot] Ignoring unknown setting key: ${key}`);
      }
    }

    await this._persist();
    console.log('[XianyuBot] Settings updated', settings);
    return { ...this._state };
  }

  /**
   * Increment today's reply counter and the all-time total.
   * Automatically rolls over to a new day bucket if the date has changed.
   *
   * @returns {Promise<void>}
   */
  async incrementStats() {
    await this.init();
    this._rollStatsIfNeeded();

    this._state.stats.today.replied += 1;
    this._state.stats.total.replied += 1;

    await this._persist();
  }

  /**
   * Increment today's skipped counter.
   * @returns {Promise<void>}
   */
  async incrementSkipped() {
    await this.init();
    this._rollStatsIfNeeded();

    this._state.stats.today.skipped += 1;
    await this._persist();
  }

  /**
   * Increment today's error counter.
   * @returns {Promise<void>}
   */
  async incrementErrors() {
    await this.init();
    this._rollStatsIfNeeded();

    this._state.stats.today.errors += 1;
    await this._persist();
  }

  /**
   * Store the seller's user ID.
   * @param {string} id
   * @returns {Promise<void>}
   */
  async setMyId(id) {
    await this.init();
    this._state.myId = id;
    await this._persist();
    console.log('[XianyuBot] Seller ID set:', id);
  }

  /**
   * Update the extension icon badge to reflect current status.
   *
   * @param {'active' | 'disabled' | 'error'} status
   * @returns {Promise<void>}
   */
  async updateBadge(status) {
    const badges = {
      active:   { text: 'ON',  color: '#4CAF50' },
      disabled: { text: 'OFF', color: '#9E9E9E' },
      error:    { text: 'ERR', color: '#F44336' },
    };

    const badge = badges[status] || badges.disabled;

    try {
      await chrome.action.setBadgeText({ text: badge.text });
      await chrome.action.setBadgeBackgroundColor({ color: badge.color });
    } catch (err) {
      // action API may not be available in all contexts (e.g. tests)
      console.warn('[XianyuBot] Could not update badge:', err.message);
    }
  }

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  /**
   * Persist the in-memory state to chrome.storage.local.
   * @returns {Promise<void>}
   */
  async _persist() {
    await chrome.storage.local.set({ [STORAGE_KEY]: this._state });
  }

  /**
   * If today's date has changed since the last recorded stats bucket, reset
   * the daily counters.
   */
  _rollStatsIfNeeded() {
    const today = new Date().toISOString().slice(0, 10); // 'YYYY-MM-DD'

    if (this._state.stats.today.date !== today) {
      this._state.stats.today = {
        replied: 0,
        skipped: 0,
        errors: 0,
        date: today,
      };
    }
  }

  /**
   * Deep-merge `source` into a copy of `defaults`.  Arrays and primitives in
   * `source` overwrite `defaults`; objects are recursively merged.
   *
   * @param {Record<string, any>} defaults
   * @param {Record<string, any>} source
   * @returns {Record<string, any>}
   */
  _deepMerge(defaults, source) {
    const result = { ...defaults };

    for (const key of Object.keys(source)) {
      if (
        source[key] !== null &&
        typeof source[key] === 'object' &&
        !Array.isArray(source[key]) &&
        typeof defaults[key] === 'object' &&
        !Array.isArray(defaults[key]) &&
        defaults[key] !== null
      ) {
        result[key] = this._deepMerge(defaults[key], source[key]);
      } else {
        result[key] = source[key];
      }
    }

    return result;
  }
}
