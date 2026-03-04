// intent-router.js — Classifies buyer message intent (e.g. price inquiry,
// tech question, default) to select the appropriate reply strategy.
//
// Ported from Python: XianyuAgent.py IntentRouter (lines 149-199).
// Three-level routing: keyword match -> regex match -> LLM fallback.

/**
 * IntentRouter implements a three-level classification strategy for incoming
 * buyer messages:
 *
 *   1. Keyword matching  (fast, deterministic)
 *   2. Regex patterns    (slightly more flexible)
 *   3. LLM fallback      (handles everything else)
 *
 * Tech intent is checked first (keywords + patterns) because technical
 * questions are higher-priority and easier to detect.  Price intent is
 * checked second.  If neither matches, the router delegates to an LLM-based
 * classifier that returns one of: 'tech', 'price', 'default', 'no_reply'.
 */
export class IntentRouter {
  constructor() {
    /**
     * Rule definitions keyed by intent.  Each entry contains:
     *   - keywords {string[]}  — substrings to look for in the cleaned text
     *   - patterns {RegExp[]}  — regular expressions to test against cleaned text
     */
    this.rules = {
      tech: {
        keywords: ['参数', '规格', '型号', '连接', '对比'],
        patterns: [/和.+比/],
      },
      price: {
        keywords: ['便宜', '价', '砍价', '少点'],
        patterns: [/\d+元/, /能少\d+/],
      },
    };
  }

  /**
   * Detect the intent of a buyer message.
   *
   * @param {string}   userMsg      — The raw buyer message.
   * @param {string}   itemDesc     — Product description for context.
   * @param {string}   context      — Formatted conversation history.
   * @param {function} [llmClassify] — Async callback `(msg, desc, ctx) => intent`
   *                                    used as an LLM-based fallback classifier.
   * @returns {Promise<string>} One of 'tech' | 'price' | 'default' | 'no_reply'.
   */
  async detect(userMsg, itemDesc, context, llmClassify) {
    // Strip everything except word characters and CJK unified ideographs,
    // matching the Python version: re.sub(r'[^\w\u4e00-\u9fa5]', '', user_msg)
    const textClean = userMsg.replace(/[^\w\u4e00-\u9fa5]/g, '');

    // ---------------------------------------------------------------
    // 1. Tech keywords (highest priority)
    // ---------------------------------------------------------------
    if (this.rules.tech.keywords.some(kw => textClean.includes(kw))) {
      return 'tech';
    }

    // ---------------------------------------------------------------
    // 2. Tech regex patterns
    // ---------------------------------------------------------------
    for (const pattern of this.rules.tech.patterns) {
      if (pattern.test(textClean)) {
        return 'tech';
      }
    }

    // ---------------------------------------------------------------
    // 3. Price keywords
    // ---------------------------------------------------------------
    if (this.rules.price.keywords.some(kw => textClean.includes(kw))) {
      return 'price';
    }

    // ---------------------------------------------------------------
    // 4. Price regex patterns
    // ---------------------------------------------------------------
    for (const pattern of this.rules.price.patterns) {
      if (pattern.test(textClean)) {
        return 'price';
      }
    }

    // ---------------------------------------------------------------
    // 5. LLM fallback — delegate to the classify agent
    // ---------------------------------------------------------------
    if (llmClassify) {
      return llmClassify(userMsg, itemDesc, context);
    }

    // No classifier available — default intent
    return 'default';
  }
}
