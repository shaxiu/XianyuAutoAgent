// service-worker.js — Background service worker: orchestrates LLM calls, manages alarms, and coordinates extension state.

import { StateManager } from './state-manager.js';
import { ContextManager } from './context-manager.js';
import { LLMClient, AgentSystem } from './llm-client.js';
import { SupabaseClient } from './supabase-client.js';
import { ItemFetcher } from './item-fetcher.js';

// ---------------------------------------------------------------------------
// Singleton instances
// ---------------------------------------------------------------------------

const stateManager = new StateManager();
const contextManager = new ContextManager();
const llmClient = new LLMClient();
const agentSystem = new AgentSystem(llmClient);
const supabaseClient = new SupabaseClient();
const itemFetcher = new ItemFetcher();

// Track active tab for multi-tab deduplication
let activeTabId = null;

// ---------------------------------------------------------------------------
// Message handling
// ---------------------------------------------------------------------------

/**
 * Central message router.  Content scripts, popup, and options page all
 * communicate with the service worker through chrome.runtime.sendMessage.
 *
 * We return `true` from the listener to signal that the response will be
 * sent asynchronously.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then(sendResponse)
    .catch((err) => {
      console.error('[XianyuBot] Unhandled error in message handler:', err);
      sendResponse({ error: err.message });
    });
  return true; // Keep the message channel open for the async response
});

/**
 * Route an incoming message to the appropriate handler based on `message.type`.
 *
 * @param {Object}          message
 * @param {chrome.runtime.MessageSender} sender
 * @returns {Promise<Object>}
 */
async function handleMessage(message, sender) {
  const { type } = message;

  switch (type) {
    // ---- Core message pipeline ----
    case 'WS_MESSAGE_RECEIVED':
      // Multi-tab dedup: register first tab and only accept from it
      if (activeTabId === null && sender.tab?.id) {
        activeTabId = sender.tab.id;
      }
      if (sender.tab?.id && sender.tab.id !== activeTabId) {
        return { status: 'skipped', reason: 'duplicate_tab' };
      }
      return handleIncomingMessage(message.payload, sender.tab?.id);

    // ---- State queries ----
    case 'GET_STATE':
      return stateManager.getState();

    // ---- Toggles & settings ----
    case 'TOGGLE_AUTO_REPLY':
      return stateManager.toggleAutoReply();

    case 'MANUAL_TAKEOVER':
      return stateManager.toggleManualMode(message.chatId);

    case 'UPDATE_SETTINGS':
      llmClient.updateSettings(message.settings || {});
      return stateManager.updateSettings(message.settings);

    // ---- Seller ID ----
    case 'SET_MY_ID':
      await stateManager.setMyId(message.myId || message.userId);
      return { status: 'ok' };

    // ---- Prompts ----
    case 'REFRESH_PROMPTS':
      return refreshPrompts();

    // ---- Logging ----
    case 'FORCE_FLUSH_LOGS':
      return flushLogs();

    default:
      console.warn('[XianyuBot] Unknown message type:', type);
      return { error: `Unknown message type: ${type}` };
  }
}

// ---------------------------------------------------------------------------
// Incoming chat message pipeline
// ---------------------------------------------------------------------------

/**
 * Process a chat message received via the content script's WebSocket
 * interceptor.  This is the main auto-reply pipeline:
 *
 *   WS message -> parse -> filter -> context -> LLM -> safety -> reply
 *
 * @param {Object} payload  Parsed chat message from the content script
 * @param {number} [tabId]  The tab that sent the message (for replying)
 * @returns {Promise<Object>}
 */
async function handleIncomingMessage(payload, tabId) {
  const state = await stateManager.getState();

  // 1. Master switch check
  if (!state.enabled) {
    return { status: 'disabled' };
  }

  // 2. Validate payload
  const parsed = payload; // Content script already parsed the WS frame

  // Handle seller's own messages — check for toggle keyword
  if (parsed.type === 'self') {
    if (
      state.toggleKeywords &&
      parsed.content &&
      parsed.content.trim() === state.toggleKeywords
    ) {
      const mode = await stateManager.toggleManualMode(parsed.chatId);
      console.log(`[XianyuBot] Seller toggled manual mode for ${parsed.chatId}: ${mode}`);
      return { status: 'toggled_manual', mode };
    }
    return { status: 'self_message' };
  }

  if (!parsed || parsed.type !== 'chat') {
    return { status: 'skipped', reason: 'not_chat' };
  }

  // 3. Skip expired messages
  if (parsed.timestamp) {
    const age = Date.now() - parsed.timestamp;
    if (age > state.messageExpireTime) {
      console.log('[XianyuBot] Skipping expired message, age:', age, 'ms');
      await stateManager.incrementSkipped();
      return { status: 'skipped', reason: 'expired' };
    }
  }

  // 4. Check manual mode (with timeout expiry)
  if (await stateManager.isManualMode(parsed.chatId)) {
    return { status: 'manual_mode' };
  }

  // 5. Generate reply through LLM pipeline
  try {
    const reply = await generateReply(parsed, state);

    // A reply of '-' (or null/empty) means "no reply needed"
    if (!reply || reply === '-') {
      await stateManager.incrementSkipped();
      return { status: 'no_reply_needed' };
    }

    // 7. Optionally simulate typing delay
    if (state.simulateTyping) {
      await simulateTypingDelay(reply, state);
    }

    // 8. Send reply command back to content script
    if (tabId) {
      try {
        await chrome.tabs.sendMessage(tabId, {
          type: 'SEND_REPLY',
          chatId: parsed.chatId,
          text: reply,
        });
      } catch (err) {
        console.error('[XianyuBot] Failed to send reply to tab:', err.message);
        // Tab may have been closed; still count the reply as generated
      }
    }

    // 9. Update stats
    await stateManager.incrementStats();

    return { status: 'replied', reply };
  } catch (err) {
    console.error('[XianyuBot] Error generating reply:', err);
    await stateManager.incrementErrors();
    await stateManager.updateBadge('error');
    return { status: 'error', error: err.message };
  }
}

// ---------------------------------------------------------------------------
// LLM reply generation
// ---------------------------------------------------------------------------

/**
 * Generate a reply for the given parsed message using the full pipeline:
 *   1. Retrieve/fetch item info
 *   2. Build conversation context
 *   3. Classify buyer intent and generate reply via AgentSystem
 *   4. Log to Supabase
 *   5. Store context
 *
 * @param {Object} parsed  The parsed chat message
 * @param {Object} state   Current extension state
 * @returns {Promise<string|null>}  The reply text, '-' for no-reply, or null
 */
async function generateReply(parsed, _state) {
  const { chatId, content, itemId, senderId, senderName } = parsed;

  // 1. Get item info (from cache or fetch)
  let itemInfo = await contextManager.getItemInfo(itemId);
  if (!itemInfo && itemId) {
    try {
      itemInfo = await itemFetcher.getItemInfo(itemId);
      if (itemInfo) {
        await contextManager.saveItemInfo(itemId, itemInfo);
      }
    } catch (err) {
      console.error('[XianyuBot] Failed to fetch item info:', err);
    }
  }
  const itemDesc = contextManager.buildItemDescription(itemInfo);

  // 2. Store buyer message in context
  await contextManager.addMessage(chatId, 'user', content, itemId);

  // 3. Get conversation history
  const formattedContext = await contextManager.getFormattedContext(chatId);
  const bargainCount = await contextManager.getBargainCount(chatId);

  // 4. Generate reply via AgentSystem
  let result;
  try {
    result = await agentSystem.generateReply(
      content, itemDesc, formattedContext, bargainCount,
    );
  } catch (err) {
    // If API key is missing, log a clear message instead of crashing
    if (err.message.includes('API key not configured')) {
      console.warn('[XianyuBot] API key not configured — skipping reply');
      supabaseClient.bufferLog('warn', 'API key not configured, reply skipped');
      return null;
    }
    throw err;
  }

  const { reply, intent } = result;

  // Increment bargain count if this was a price intent
  if (intent === 'price') {
    await contextManager.incrementBargainCount(chatId);
  }

  // '-' means no reply needed
  if (reply === '-') return '-';
  if (!reply) return null;

  // 5. Store assistant reply in context
  await contextManager.addMessage(chatId, 'assistant', reply, itemId);

  // 6. Log to Supabase (non-blocking)
  const itemTitle = itemInfo?.title || '';
  supabaseClient.logConversation(chatId, itemId, itemTitle, 'user', content, intent).catch(() => {});
  supabaseClient.logConversation(chatId, itemId, itemTitle, 'assistant', reply, intent).catch(() => {});
  supabaseClient.bufferLog('info', `Reply to ${senderName || senderId}: [${intent}] ${reply.substring(0, 100)}`);

  return reply;
}

// ---------------------------------------------------------------------------
// Typing delay simulation
// ---------------------------------------------------------------------------

/**
 * Simulate a human-like typing delay before sending a reply.
 *
 * The total delay = random(base range) + charCount * random(per-char range)
 *
 * @param {string} text   The reply text (length determines delay)
 * @param {Object} state  Current state (contains delay ranges)
 * @returns {Promise<void>}
 */
function simulateTypingDelay(text, state) {
  const [baseMin, baseMax] = state.typingDelayBase;
  const [charMin, charMax] = state.typingDelayPerChar;

  const baseDelay = randomBetween(baseMin, baseMax);
  const charDelay = text.length * randomBetween(charMin, charMax);

  // Cap total delay at 15 seconds to avoid excessively long waits
  const totalDelay = Math.min(baseDelay + charDelay, 15000);

  return new Promise((resolve) => setTimeout(resolve, totalDelay));
}

/**
 * Return a random integer between min (inclusive) and max (inclusive).
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function randomBetween(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

// ---------------------------------------------------------------------------
// Log flushing & prompt refresh
// ---------------------------------------------------------------------------

/**
 * Flush accumulated logs to Supabase.
 * @returns {Promise<Object>}
 */
async function flushLogs() {
  try {
    await supabaseClient.flushLogs();
    return { status: 'ok' };
  } catch (err) {
    console.error('[XianyuBot] flushLogs error:', err);
    return { status: 'error', error: err.message };
  }
}

/**
 * Refresh prompts from Supabase and load them into the AgentSystem.
 * @returns {Promise<Object>}
 */
async function refreshPrompts() {
  try {
    const prompts = await supabaseClient.getPrompts();
    agentSystem.loadPrompts(prompts);
    console.log('[XianyuBot] Prompts refreshed:', Object.keys(prompts));
    return { status: 'ok', prompts: Object.keys(prompts) };
  } catch (err) {
    console.error('[XianyuBot] refreshPrompts error:', err);
    return { status: 'error', error: err.message };
  }
}

// ---------------------------------------------------------------------------
// Alarm handlers
// ---------------------------------------------------------------------------

chrome.alarms.onAlarm.addListener((alarm) => {
  switch (alarm.name) {
    case 'flush-logs':
      flushLogs().catch((err) =>
        console.error('[XianyuBot] Alarm flush-logs error:', err)
      );
      break;

    case 'refresh-prompts':
      refreshPrompts().catch((err) =>
        console.error('[XianyuBot] Alarm refresh-prompts error:', err)
      );
      break;

    default:
      console.warn('[XianyuBot] Unknown alarm:', alarm.name);
  }
});

// ---------------------------------------------------------------------------
// Tab lifecycle — reset active tab on close
// ---------------------------------------------------------------------------

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeTabId) {
    activeTabId = null;
    console.log('[XianyuBot] Active tab closed, reset for next tab');
  }
});

// ---------------------------------------------------------------------------
// Extension lifecycle
// ---------------------------------------------------------------------------

/**
 * Runs on first install and on extension updates.  Sets up recurring alarms
 * and initialises state.
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('[XianyuBot] Extension installed/updated:', details.reason);

  // Create periodic alarms
  await chrome.alarms.create('flush-logs', { periodInMinutes: 1 });
  await chrome.alarms.create('refresh-prompts', { periodInMinutes: 30 });

  // Initialise all modules
  await stateManager.init();
  await llmClient.init();
  await supabaseClient.init();

  // Load prompts from Supabase
  await refreshPrompts();

  const state = await stateManager.getState();
  await stateManager.updateBadge(state.enabled ? 'active' : 'disabled');

  // Update Supabase status
  supabaseClient.updateStatus('online').catch(() => {});

  console.log('[XianyuBot] Alarms created, all modules initialised');
});

/**
 * Runs every time the service worker starts (e.g. after being idle-killed).
 * Re-initialises in-memory state from storage.
 */
chrome.runtime.onStartup.addListener(async () => {
  console.log('[XianyuBot] Service worker starting up');

  await stateManager.init();
  await llmClient.init();
  await supabaseClient.init();
  await refreshPrompts();

  const state = await stateManager.getState();
  await stateManager.updateBadge(state.enabled ? 'active' : 'disabled');

  supabaseClient.updateStatus('online').catch(() => {});
});
