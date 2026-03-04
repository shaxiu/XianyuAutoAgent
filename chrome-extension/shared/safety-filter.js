// safety-filter.js — Filters and sanitizes outgoing replies to prevent sending
// inappropriate, sensitive, or policy-violating content.
//
// Ported from Python: XianyuAgent.py _safe_filter (lines 65-68).
// Extended with English variants of blocked phrases for broader coverage.

/**
 * Phrases that must never appear in outgoing replies.
 * If any phrase is found (case-insensitive) the entire reply is replaced with
 * a safety reminder asking the buyer to communicate through the platform.
 */
const BLOCKED_PHRASES = [
  '微信',
  'QQ',
  '支付宝',
  '银行卡',
  '线下',
  'wechat',
  'weixin',
  'alipay',
];

/** Replacement text shown when a blocked phrase is detected. */
const SAFETY_REPLACEMENT = '[安全提醒]请通过平台沟通';

/**
 * Run the safety filter on outgoing text.
 *
 * If `text` contains any of the blocked phrases the entire message is replaced
 * with a generic safety reminder.  Otherwise the original text is returned
 * unchanged.
 *
 * @param {string} text - The LLM-generated reply to check.
 * @returns {string} Either the original text or the safety replacement.
 */
export function safetyFilter(text) {
  if (!text || typeof text !== 'string') return text;

  const lower = text.toLowerCase();

  if (BLOCKED_PHRASES.some(phrase => lower.includes(phrase.toLowerCase()))) {
    return SAFETY_REPLACEMENT;
  }

  return text;
}

/**
 * Expose constants for testing / external use.
 */
export { BLOCKED_PHRASES, SAFETY_REPLACEMENT };
