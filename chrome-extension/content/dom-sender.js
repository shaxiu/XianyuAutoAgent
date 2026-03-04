// dom-sender.js — Programmatically types and sends reply messages into the Goofish IM chat input box via DOM manipulation.
//
// Instead of sending messages via WebSocket (which could trigger risk control),
// this module simulates human interaction with the Goofish IM page:
//   1. Navigate to the correct chat conversation
//   2. Find the input box
//   3. Simulate typing the reply text
//   4. Click the send button

// ---------------------------------------------------------------------------
// DOM Selector Fallbacks
// ---------------------------------------------------------------------------

// Input box selectors (tried in order):
const INPUT_SELECTORS = [
  '.chat-input .ql-editor',           // Quill editor (primary)
  '.chat-sendbox .ql-editor',         // Alternative Quill location
  '[contenteditable="true"]',         // Generic contenteditable
  'div[data-placeholder]',            // Placeholder-based detection
  '.message-input textarea',          // Textarea fallback
];

// Send button selectors:
const SEND_BUTTON_SELECTORS = [
  '.chat-input .send-btn',
  '.chat-sendbox .send-btn',
  'button.send-btn',
  '.btn-send',
  '.message-input button[type="submit"]',
];

// Chat list item selectors:
const CHAT_LIST_SELECTORS = [
  '.conv-list .conv-item',
  '.session-list .session-item',
  '.chat-list-item',
];

// ---------------------------------------------------------------------------
// Reply Queue
// ---------------------------------------------------------------------------

const replyQueue = [];
let isProcessing = false;

/**
 * Queue a reply to be sent via DOM simulation.
 * @param {string} chatId  - The conversation / chat identifier.
 * @param {string} text    - The message text to send.
 */
function queueReply(chatId, text) {
  replyQueue.push({ chatId, text, timestamp: Date.now() });
  processQueue();
}

/**
 * Drain the reply queue sequentially.  Each message is sent one-at-a-time
 * with a randomised inter-message delay so the cadence looks human.
 */
async function processQueue() {
  if (isProcessing || replyQueue.length === 0) return;
  isProcessing = true;

  while (replyQueue.length > 0) {
    const { chatId, text } = replyQueue.shift();
    try {
      await sendMessage(chatId, text);
    } catch (err) {
      console.error('[XianyuBot] Failed to send message:', err);
    }
    // Random pause between messages to look more human
    await sleep(500 + Math.random() * 1000);
  }

  isProcessing = false;
}

// ---------------------------------------------------------------------------
// Core Send Flow
// ---------------------------------------------------------------------------

/**
 * Send a single message to the given chat.
 *
 * Steps:
 *  1. (Optional) navigate to the target chat in the sidebar.
 *  2. Locate the input element.
 *  3. Focus and clear the input.
 *  4. Simulate typing (or instant-insert, depending on settings).
 *  5. Click the send button (or fall back to dispatching Enter).
 *
 * @param {string} chatId
 * @param {string} text
 */
async function sendMessage(chatId, text) {
  console.log(`[XianyuBot] Sending message to chat ${chatId}: ${text}`);

  // 1. Attempt to navigate to the target chat if it is not already active.
  //    navigateToChat is best-effort; if it fails we still try to type into
  //    whatever chat is currently open.
  await navigateToChat(chatId);

  // 2. Find the input element
  const input = findElement(INPUT_SELECTORS);
  if (!input) {
    throw new Error('Could not find chat input element on the page');
  }

  // 3. Load user typing-simulation settings
  const settings = await getTypingSettings();

  // 4. Focus the input
  input.focus();
  await sleep(100);

  // 5. Clear any existing content
  clearInput(input);
  await sleep(100);

  // 6. Type the message
  if (settings.simulateTyping) {
    await simulateTyping(input, text, settings);
  } else {
    insertText(input, text);
  }

  await sleep(200);

  // 7. Click the send button (or press Enter as a fallback)
  const sendBtn = findElement(SEND_BUTTON_SELECTORS);
  if (sendBtn) {
    sendBtn.click();
    console.log('[XianyuBot] Send button clicked');
  } else {
    // Dispatch Enter key as fallback for sending
    const enterEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true,
    });
    input.dispatchEvent(enterEvent);
    console.log('[XianyuBot] Enter key dispatched (send button not found)');
  }
}

// ---------------------------------------------------------------------------
// Typing Simulation
// ---------------------------------------------------------------------------

/**
 * Simulate human-like typing by inserting characters one-at-a-time with
 * randomised inter-character delays.
 *
 * @param {HTMLElement} input
 * @param {string}      text
 * @param {object}      settings
 */
async function simulateTyping(input, text, settings) {
  const { typingDelayBase, typingDelayPerChar } = settings;

  // Initial "thinking" pause before starting to type
  const baseDelay = randomInRange(typingDelayBase[0], typingDelayBase[1]);
  await sleep(baseDelay);

  // Type character by character
  for (const char of text) {
    insertChar(input, char);
    const charDelay = randomInRange(typingDelayPerChar[0], typingDelayPerChar[1]);
    await sleep(charDelay);
  }
}

/**
 * Insert a single character into the input element.
 * For contenteditable elements (Quill etc.) we use document.execCommand which
 * is the most natural way to simulate keyboard entry.
 *
 * @param {HTMLElement} input
 * @param {string}      char
 */
function insertChar(input, char) {
  if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
    input.value += char;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  } else {
    // Contenteditable — execCommand('insertText') closely mimics real typing
    document.execCommand('insertText', false, char);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

/**
 * Insert the full text at once (no per-character animation).
 *
 * @param {HTMLElement} input
 * @param {string}      text
 */
function insertText(input, text) {
  if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  } else {
    // Contenteditable — select-all then insert to replace any stale content
    input.focus();
    document.execCommand('selectAll', false, null);
    document.execCommand('insertText', false, text);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

/**
 * Clear whatever content is in the input element.
 *
 * @param {HTMLElement} input
 */
function clearInput(input) {
  if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  } else {
    // Contenteditable
    input.innerHTML = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

// ---------------------------------------------------------------------------
// Chat Navigation
// ---------------------------------------------------------------------------

/**
 * Attempt to click on the conversation that matches `chatId` in the sidebar
 * chat list.  This is best-effort and heuristic-based because the chatId
 * may appear in a data attribute, a link href, or an inner element's text.
 *
 * @param {string} chatId
 * @returns {Promise<boolean>} true if we found and clicked the chat item
 */
async function navigateToChat(chatId) {
  if (!chatId) return false;

  // Strategy 1: look via our known chat-list selectors
  for (const selector of CHAT_LIST_SELECTORS) {
    const items = document.querySelectorAll(selector);
    for (const item of items) {
      if (chatItemMatchesId(item, chatId)) {
        item.click();
        await sleep(500); // Wait for the chat pane to load
        return true;
      }
    }
  }

  // Strategy 2: broader search for any element whose data-* or href contains the id
  const candidates = document.querySelectorAll(
    '[class*="conv"], [class*="session"], [class*="chat-list"]'
  );
  for (const item of candidates) {
    if (chatItemMatchesId(item, chatId)) {
      item.click();
      await sleep(500);
      return true;
    }
  }

  console.warn('[XianyuBot] Could not find chat in sidebar:', chatId);
  return false;
}

/**
 * Check whether a sidebar chat item corresponds to the given chatId.
 * We look at data-* attributes, nested links, and dataset properties.
 *
 * @param {HTMLElement} item
 * @param {string}      chatId
 * @returns {boolean}
 */
function chatItemMatchesId(item, chatId) {
  // Check common data attributes
  if (item.dataset && item.dataset.id === chatId) return true;
  if (item.dataset && item.dataset.cid === chatId) return true;
  if (item.dataset && item.dataset.conversationId === chatId) return true;

  // Check nested anchor hrefs
  const link = item.querySelector('a');
  if (link && link.href && link.href.includes(chatId)) return true;

  // Check the item's own attributes
  const id = item.getAttribute('id') || '';
  if (id.includes(chatId)) return true;

  return false;
}

// ---------------------------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------------------------

/**
 * Try each selector in order and return the first matching element, or null.
 *
 * @param {string[]} selectors
 * @returns {HTMLElement|null}
 */
function findElement(selectors) {
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) return el;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

/**
 * Load typing-simulation preferences from chrome.storage.local.
 * Falls back to sensible defaults if storage is unavailable or empty.
 *
 * @returns {Promise<{simulateTyping: boolean, typingDelayBase: number[], typingDelayPerChar: number[]}>}
 */
async function getTypingSettings() {
  try {
    const result = await chrome.storage.local.get([
      'simulateTyping',
      'typingDelayBase',
      'typingDelayPerChar',
    ]);
    return {
      simulateTyping: result.simulateTyping !== false, // default: true
      typingDelayBase: result.typingDelayBase || [0, 1000],
      typingDelayPerChar: result.typingDelayPerChar || [50, 150],
    };
  } catch {
    // Storage unavailable — use defaults
    return {
      simulateTyping: true,
      typingDelayBase: [0, 1000],
      typingDelayPerChar: [50, 150],
    };
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * Return a random integer between min and max (inclusive).
 */
function randomInRange(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * Promise-based sleep.
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Message Listener — receive SEND_REPLY commands from the background worker
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'SEND_REPLY') {
    queueReply(message.chatId, message.text);
    sendResponse({ status: 'queued' });
  }
  // Return false (synchronous) — we already called sendResponse above.
  // If we needed async sendResponse we would return true here.
});

// ---------------------------------------------------------------------------
// Exports (for use by other content-script modules loaded in the same context)
// ---------------------------------------------------------------------------
// Note: content scripts declared in manifest.json share a single execution
// context, so we attach public API to the window for cross-file access when
// ES module imports are not available.

if (typeof window !== 'undefined') {
  window.__xianyuDomSender = {
    queueReply,
  };
}
