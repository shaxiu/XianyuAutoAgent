// content/main.js — Content script entry point: bootstraps the extension in the Goofish IM page context.
// Runs in the isolated world on *://www.goofish.com/im* at document_start.

// =============================================================================
// Section 1: MessagePack Decoder (ported from Python utils/xianyu_utils.py)
// =============================================================================
// Content scripts in MV3 cannot use ES module imports, so the msgpack decoder
// and decrypt logic are inlined here.

class MessagePackDecoder {
  constructor(data) {
    // data: Uint8Array
    this.data = data;
    this.pos = 0;
    this.length = data.length;
  }

  readByte() {
    if (this.pos >= this.length) throw new Error('Unexpected end of data');
    return this.data[this.pos++];
  }

  readBytes(count) {
    if (this.pos + count > this.length) throw new Error('Unexpected end of data');
    const result = this.data.slice(this.pos, this.pos + count);
    this.pos += count;
    return result;
  }

  // Big-endian unsigned integer readers
  readUint8() {
    return this.readByte();
  }
  readUint16() {
    const b = this.readBytes(2);
    return (b[0] << 8) | b[1];
  }
  readUint32() {
    const b = this.readBytes(4);
    return ((b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]) >>> 0;
  }
  readUint64() {
    const hi = this.readUint32();
    const lo = this.readUint32();
    // Return as Number (safe for values up to 2^53-1)
    return hi * 0x100000000 + lo;
  }

  // Big-endian signed integer readers
  readInt8() {
    const v = this.readByte();
    return v > 0x7f ? v - 256 : v;
  }
  readInt16() {
    const v = this.readUint16();
    return v > 0x7fff ? v - 0x10000 : v;
  }
  readInt32() {
    const v = this.readUint32();
    return v > 0x7fffffff ? v - 0x100000000 : v;
  }
  readInt64() {
    // Simplified: read as two 32-bit and combine
    const hi = this.readUint32();
    const lo = this.readUint32();
    if (hi > 0x7fffffff) {
      return -(0x100000000 * (0xffffffff - hi) + (0x100000000 - lo));
    }
    return hi * 0x100000000 + lo;
  }

  readFloat32() {
    const b = this.readBytes(4);
    const view = new DataView(b.buffer, b.byteOffset, 4);
    return view.getFloat32(0, false); // big-endian
  }
  readFloat64() {
    const b = this.readBytes(8);
    const view = new DataView(b.buffer, b.byteOffset, 8);
    return view.getFloat64(0, false); // big-endian
  }

  readString(length) {
    const bytes = this.readBytes(length);
    return new TextDecoder('utf-8').decode(bytes);
  }

  decodeValue() {
    if (this.pos >= this.length) throw new Error('Unexpected end of data');

    const fmt = this.readByte();

    // Positive fixint (0x00 - 0x7f)
    if (fmt <= 0x7f) return fmt;

    // Fixmap (0x80 - 0x8f)
    if (fmt >= 0x80 && fmt <= 0x8f) return this.decodeMap(fmt & 0x0f);

    // Fixarray (0x90 - 0x9f)
    if (fmt >= 0x90 && fmt <= 0x9f) return this.decodeArray(fmt & 0x0f);

    // Fixstr (0xa0 - 0xbf)
    if (fmt >= 0xa0 && fmt <= 0xbf) return this.readString(fmt & 0x1f);

    // nil
    if (fmt === 0xc0) return null;

    // false
    if (fmt === 0xc2) return false;

    // true
    if (fmt === 0xc3) return true;

    // bin 8
    if (fmt === 0xc4) return this.readBytes(this.readUint8());

    // bin 16
    if (fmt === 0xc5) return this.readBytes(this.readUint16());

    // bin 32
    if (fmt === 0xc6) return this.readBytes(this.readUint32());

    // float 32
    if (fmt === 0xca) return this.readFloat32();

    // float 64
    if (fmt === 0xcb) return this.readFloat64();

    // uint 8
    if (fmt === 0xcc) return this.readUint8();

    // uint 16
    if (fmt === 0xcd) return this.readUint16();

    // uint 32
    if (fmt === 0xce) return this.readUint32();

    // uint 64
    if (fmt === 0xcf) return this.readUint64();

    // int 8
    if (fmt === 0xd0) return this.readInt8();

    // int 16
    if (fmt === 0xd1) return this.readInt16();

    // int 32
    if (fmt === 0xd2) return this.readInt32();

    // int 64
    if (fmt === 0xd3) return this.readInt64();

    // str 8
    if (fmt === 0xd9) return this.readString(this.readUint8());

    // str 16
    if (fmt === 0xda) return this.readString(this.readUint16());

    // str 32
    if (fmt === 0xdb) return this.readString(this.readUint32());

    // array 16
    if (fmt === 0xdc) return this.decodeArray(this.readUint16());

    // array 32
    if (fmt === 0xdd) return this.decodeArray(this.readUint32());

    // map 16
    if (fmt === 0xde) return this.decodeMap(this.readUint16());

    // map 32
    if (fmt === 0xdf) return this.decodeMap(this.readUint32());

    // Negative fixint (0xe0 - 0xff)
    if (fmt >= 0xe0) return fmt - 256;

    throw new Error(`Unknown msgpack format byte: 0x${fmt.toString(16)}`);
  }

  decodeArray(size) {
    const result = [];
    for (let i = 0; i < size; i++) {
      result.push(this.decodeValue());
    }
    return result;
  }

  decodeMap(size) {
    const result = {};
    for (let i = 0; i < size; i++) {
      const key = this.decodeValue();
      const value = this.decodeValue();
      result[key] = value;
    }
    return result;
  }

  decode() {
    try {
      return this.decodeValue();
    } catch (e) {
      // Fallback: return raw bytes as base64
      return btoa(String.fromCharCode(...this.data));
    }
  }
}

// =============================================================================
// Section 2: Decrypt function (ported from Python utils/xianyu_utils.py)
// =============================================================================

/**
 * Decrypts an encrypted data string from the WS sync package.
 * Steps: base64 decode -> msgpack decode -> JSON string.
 * @param {string} data - base64-encoded encrypted data
 * @returns {string} JSON string of decoded message
 */
function decrypt(data) {
  try {
    // 1. Clean the base64 input (strip non-base64 characters)
    let cleaned = data.replace(/[^A-Za-z0-9+/=]/g, '');

    // Pad if necessary
    while (cleaned.length % 4 !== 0) {
      cleaned += '=';
    }

    // 2. Base64 decode to bytes
    const binaryStr = atob(cleaned);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    // 3. MessagePack decode
    const decoder = new MessagePackDecoder(bytes);
    const result = decoder.decode();

    // 4. Custom serializer for any Uint8Array values nested in the result
    function jsonSerializer(key, value) {
      if (value instanceof Uint8Array || value instanceof ArrayBuffer) {
        try {
          return new TextDecoder('utf-8').decode(value);
        } catch {
          return btoa(String.fromCharCode(...new Uint8Array(value)));
        }
      }
      return value;
    }

    return JSON.stringify(result, jsonSerializer);
  } catch (e) {
    // If everything fails, return an error JSON
    return JSON.stringify({ error: `Decrypt failed: ${e.message}`, raw_data: data });
  }
}


// =============================================================================
// Section 3: Message type classification helpers
//   (ported from Python main.py: is_sync_package, is_chat_message, etc.)
// =============================================================================

/**
 * Check if the raw WS message is a sync push package containing message data.
 */
function isSyncPackage(data) {
  try {
    return (
      data != null &&
      typeof data === 'object' &&
      data.body != null &&
      data.body.syncPushPackage != null &&
      Array.isArray(data.body.syncPushPackage.data) &&
      data.body.syncPushPackage.data.length > 0
    );
  } catch {
    return false;
  }
}

/**
 * Check if the decoded message is a user chat message (has reminderContent).
 */
function isChatMessage(msg) {
  try {
    return (
      msg != null &&
      typeof msg === 'object' &&
      msg['1'] != null &&
      typeof msg['1'] === 'object' &&
      !Array.isArray(msg['1']) &&
      msg['1']['10'] != null &&
      typeof msg['1']['10'] === 'object' &&
      'reminderContent' in msg['1']['10']
    );
  } catch {
    return false;
  }
}

/**
 * Check if the message is a "user is typing" status indicator.
 */
function isTypingStatus(msg) {
  try {
    return (
      msg != null &&
      typeof msg === 'object' &&
      Array.isArray(msg['1']) &&
      msg['1'].length > 0 &&
      typeof msg['1'][0] === 'object' &&
      typeof msg['1'][0]['1'] === 'string' &&
      msg['1'][0]['1'].includes('@goofish')
    );
  } catch {
    return false;
  }
}

/**
 * Check if the message is a system message (needPush === "false").
 */
function isSystemMessage(msg) {
  try {
    return (
      msg != null &&
      typeof msg === 'object' &&
      msg['3'] != null &&
      typeof msg['3'] === 'object' &&
      msg['3'].needPush === 'false'
    );
  } catch {
    return false;
  }
}

/**
 * Check if the text is a bracket-wrapped system message like "[系统消息]".
 */
function isBracketSystemMessage(text) {
  if (!text || typeof text !== 'string') return false;
  const clean = text.trim();
  return clean.startsWith('[') && clean.endsWith(']');
}


// =============================================================================
// Section 4: Top-level message parser
//   Processes a raw WS message object through all classification and extraction.
// =============================================================================

/** Default message expiry window: 5 minutes in milliseconds */
const MESSAGE_EXPIRE_MS = 300000;

/**
 * Parse a raw WebSocket message into a structured object suitable for
 * forwarding to the background service worker.
 *
 * @param {object} messageData - The parsed JSON object from the WebSocket frame
 * @param {string} myId - The seller's user ID (from the 'unb' cookie)
 * @returns {object|null} Parsed message descriptor, or null if irrelevant
 */
function parseMessage(messageData, myId) {
  // Must be a sync package
  if (!isSyncPackage(messageData)) return null;

  // Extract the first data entry from the sync push package
  const syncData = messageData.body.syncPushPackage.data[0];
  if (!syncData || !syncData.data) return null;

  let message;

  // Attempt plain base64 -> JSON decode first (unencrypted messages)
  try {
    const decoded = atob(syncData.data);
    message = JSON.parse(decoded);
    // Successfully decoded as plain base64/JSON -- these are typically not
    // user chat messages (e.g. ack confirmations). Skip them.
    return null;
  } catch {
    // Not plain base64/JSON -- try encrypted msgpack path
  }

  try {
    const decrypted = decrypt(syncData.data);
    message = JSON.parse(decrypted);
  } catch (e) {
    console.debug('[XianyuBot] Message decrypt failed:', e);
    return null;
  }

  // -----------------------------------------------------------
  // Check for order status messages (payment, close, shipping)
  // -----------------------------------------------------------
  try {
    const reminder = message['3'] && message['3'].redReminder;
    if (reminder === '等待买家付款' || reminder === '交易关闭' || reminder === '等待卖家发货') {
      const userId = typeof message['1'] === 'string'
        ? message['1'].split('@')[0]
        : null;
      console.log(`[XianyuBot] Order status: ${reminder}, user: ${userId}`);
      return { type: 'order', status: reminder, userId };
    }
  } catch {
    // Not an order message, continue
  }

  // -----------------------------------------------------------
  // Check for typing-status indicator
  // -----------------------------------------------------------
  if (isTypingStatus(message)) {
    return null; // Silently ignore typing indicators
  }

  // -----------------------------------------------------------
  // Must be a chat message with reminderContent
  // -----------------------------------------------------------
  if (!isChatMessage(message)) {
    return null;
  }

  // -----------------------------------------------------------
  // Skip system messages (needPush === "false")
  // -----------------------------------------------------------
  if (isSystemMessage(message)) {
    return null;
  }

  // -----------------------------------------------------------
  // Extract chat message fields
  // -----------------------------------------------------------
  let createTime, senderName, senderId, content, urlInfo, itemId, chatId;

  try {
    createTime = parseInt(message['1']['5'], 10);
    senderName = message['1']['10'].reminderTitle;
    senderId   = message['1']['10'].senderUserId;
    content    = message['1']['10'].reminderContent;
    urlInfo    = message['1']['10'].reminderUrl || '';
    chatId     = message['1']['2'].split('@')[0];
  } catch (e) {
    console.debug('[XianyuBot] Failed to extract message fields:', e);
    return null;
  }

  // Extract itemId from the URL query parameter
  itemId = urlInfo.includes('itemId=')
    ? urlInfo.split('itemId=')[1].split('&')[0]
    : null;

  // Skip bracket-wrapped system messages like "[交易提醒]"
  if (isBracketSystemMessage(content)) {
    return null;
  }

  // Skip expired messages (older than MESSAGE_EXPIRE_MS)
  if (Date.now() - createTime > MESSAGE_EXPIRE_MS) {
    console.debug('[XianyuBot] Expired message discarded');
    return null;
  }

  // Skip messages without an item ID (cannot look up product)
  if (!itemId) {
    console.debug('[XianyuBot] No itemId in message, skipping');
    return null;
  }

  // -----------------------------------------------------------
  // Seller's own messages — pass through for toggle keyword detection
  // -----------------------------------------------------------
  if (senderId === myId) {
    return {
      type: 'self',
      chatId,
      content,
      senderId,
      senderName,
      itemId,
    };
  }

  return {
    type: 'chat',
    createTime,
    senderName,
    senderId,
    content,
    itemId,
    chatId
  };
}


// =============================================================================
// Section 5: Inject inject.js into the page's MAIN world
// =============================================================================

/**
 * Injects content/inject.js into the page context (MAIN world) so it can
 * monkey-patch the native WebSocket constructor and capture WS frames.
 */
function injectScript() {
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('content/inject.js');
  script.type = 'module';
  (document.head || document.documentElement).appendChild(script);
  script.onload = () => script.remove();
  console.log('[XianyuBot] inject.js injected into page');
}


// =============================================================================
// Section 6: Extract seller ID from browser cookies
// =============================================================================

/**
 * Reads the 'unb' cookie from document.cookie to determine the seller's user ID.
 * @returns {string|null} The seller user ID or null if not found
 */
function getMyId() {
  const cookies = document.cookie.split('; ');
  for (const cookie of cookies) {
    const eqIndex = cookie.indexOf('=');
    if (eqIndex === -1) continue;
    const name = cookie.substring(0, eqIndex);
    const value = cookie.substring(eqIndex + 1);
    if (name === 'unb') return value;
  }
  return null;
}


// =============================================================================
// Section 7: WS message listener (inject.js -> content script via postMessage)
// =============================================================================

/**
 * Sets up a window.addEventListener('message', ...) handler that receives
 * WebSocket frame data from inject.js (which posts XIANYU_WS_MESSAGE events).
 * Valid chat messages are forwarded to the background service worker.
 *
 * @param {string} myId - The seller's user ID
 */
function setupMessageListener(myId) {
  window.addEventListener('message', (event) => {
    // Only accept messages from our own window (same-origin, from inject.js)
    if (event.source !== window) return;
    if (!event.data || event.data.type !== 'XIANYU_WS_MESSAGE') return;

    try {
      const rawData = event.data.data;
      let messageData;

      if (typeof rawData === 'string') {
        messageData = JSON.parse(rawData);
      } else {
        messageData = rawData;
      }

      const parsed = parseMessage(messageData, myId);

      if (!parsed) return; // Not a relevant message

      // Forward the parsed message to the background service worker
      chrome.runtime.sendMessage({
        type: 'WS_MESSAGE_RECEIVED',
        payload: parsed
      });

    } catch (err) {
      console.error('[XianyuBot] Error processing WS message:', err);
    }
  });
}


// =============================================================================
// Section 8: Listen for commands from the background service worker
// =============================================================================

// SEND_REPLY is handled by dom-sender.js (loaded alongside main.js via manifest).
// Other background commands can be handled here.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ status: 'ok', page: 'goofish-im' });
  }
  return true;
});


// =============================================================================
// Section 9: Initialization
// =============================================================================

(function init() {
  const myId = getMyId();
  if (!myId) {
    console.error('[XianyuBot] Could not find seller ID (unb cookie). Extension will not activate.');
    return;
  }

  console.log('[XianyuBot] Seller ID:', myId);

  // Notify the background service worker of the seller's ID
  chrome.runtime.sendMessage({ type: 'SET_MY_ID', myId });

  // Inject the WebSocket hook script into the page's MAIN world
  injectScript();

  // Start listening for WS messages relayed from inject.js
  setupMessageListener(myId);

  console.log('[XianyuBot] Content script initialized');
})();
