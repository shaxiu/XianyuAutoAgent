// message-parser.js — Parses raw WebSocket message payloads into structured
// chat message objects.
//
// Ported from Python: main.py (lines 193-268, 358-560)
// This module provides standalone parsing utilities. The main.js content script
// inlines a copy of the MessagePack decoder and uses the same logic, but this
// module is available for import by the service worker if needed.

/**
 * Check if raw WS JSON is a sync package containing message data.
 * @param {object} data
 * @returns {boolean}
 */
export function isSyncPackage(data) {
  try {
    return (
      data &&
      typeof data === 'object' &&
      data.body &&
      data.body.syncPushPackage &&
      Array.isArray(data.body.syncPushPackage.data) &&
      data.body.syncPushPackage.data.length > 0
    );
  } catch {
    return false;
  }
}

/**
 * Check if a decoded message is a user chat message.
 * @param {object} msg
 * @returns {boolean}
 */
export function isChatMessage(msg) {
  try {
    return (
      msg &&
      typeof msg === 'object' &&
      msg['1'] &&
      typeof msg['1'] === 'object' &&
      !Array.isArray(msg['1']) &&
      msg['1']['10'] &&
      typeof msg['1']['10'] === 'object' &&
      'reminderContent' in msg['1']['10']
    );
  } catch {
    return false;
  }
}

/**
 * Check if a decoded message is a "user is typing" status.
 * @param {object} msg
 * @returns {boolean}
 */
export function isTypingStatus(msg) {
  try {
    return (
      msg &&
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
 * Check if a decoded message is a system message (needPush === "false").
 * @param {object} msg
 * @returns {boolean}
 */
export function isSystemMessage(msg) {
  try {
    return (
      msg &&
      typeof msg === 'object' &&
      msg['3'] &&
      typeof msg['3'] === 'object' &&
      msg['3'].needPush === 'false'
    );
  } catch {
    return false;
  }
}

/**
 * Check if a text message is a bracket-wrapped system message like "[交易提醒]".
 * @param {string} text
 * @returns {boolean}
 */
export function isBracketSystemMessage(text) {
  if (!text || typeof text !== 'string') return false;
  const clean = text.trim();
  return clean.startsWith('[') && clean.endsWith(']');
}

/**
 * Extract chat fields from a decoded message object.
 * @param {object} message - The decoded message
 * @returns {object|null} Extracted fields or null if extraction fails
 */
export function extractChatFields(message) {
  try {
    const createTime = parseInt(message['1']['5']);
    const senderName = message['1']['10'].reminderTitle;
    const senderId = message['1']['10'].senderUserId;
    const content = message['1']['10'].reminderContent;
    const urlInfo = message['1']['10'].reminderUrl || '';
    const itemId = urlInfo.includes('itemId=')
      ? urlInfo.split('itemId=')[1].split('&')[0]
      : null;
    const chatId = message['1']['2'].split('@')[0];

    return { createTime, senderName, senderId, content, itemId, chatId };
  } catch {
    return null;
  }
}

/**
 * Check for order-related messages (payment pending, trade closed, etc.)
 * @param {object} message - The decoded message
 * @returns {object|null} Order info or null
 */
export function extractOrderInfo(message) {
  try {
    const reminder = message['3']?.redReminder;
    if (
      reminder === '等待买家付款' ||
      reminder === '交易关闭' ||
      reminder === '等待卖家发货'
    ) {
      const userId = message['1']?.split?.('@')?.[0];
      return { type: 'order', status: reminder, userId };
    }
  } catch {
    // Not an order message
  }
  return null;
}
