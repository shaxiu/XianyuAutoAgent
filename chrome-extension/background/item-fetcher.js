// item-fetcher.js — Fetch item/product info from the Goofish API using
// the browser's cookies.  Because the extension has host_permissions for
// *.goofish.com the service worker can make cross-origin requests with
// cookies attached, which avoids risk-control issues (same session as
// the user's browser tab).
//
// Mirrors: XianyuApis.py  get_item_info  (lines 254-316)

import { generateSign } from '../lib/md5.js';

// ---------------------------------------------------------------------------
// ItemFetcher
// ---------------------------------------------------------------------------

export class ItemFetcher {

  // -----------------------------------------------------------------------
  // Cookie helpers
  // -----------------------------------------------------------------------

  /**
   * Read the `_m_h5_tk` token from goofish.com cookies.
   *
   * The cookie value has the form `<token>_<timestamp>`.  We only need the
   * token portion (everything before the first underscore).
   *
   * @returns {Promise<string>} The token string, or '' on failure.
   */
  async getToken() {
    try {
      const cookie = await chrome.cookies.get({
        url: 'https://www.goofish.com',
        name: '_m_h5_tk'
      });
      if (cookie && cookie.value) {
        return cookie.value.split('_')[0];
      }
    } catch (err) {
      console.error('[XianyuBot] Failed to get _m_h5_tk cookie:', err);
    }
    return '';
  }

  /**
   * Collect all goofish.com cookies into a single `Cookie` header string.
   *
   * Not currently used (we rely on `credentials: 'include'` in fetch), but
   * kept as a utility in case manual cookie injection is ever needed.
   *
   * @returns {Promise<string>}
   */
  async getCookieString() {
    try {
      const cookies = await chrome.cookies.getAll({ domain: '.goofish.com' });
      return cookies.map(c => `${c.name}=${c.value}`).join('; ');
    } catch (err) {
      console.error('[XianyuBot] Failed to get cookies:', err);
      return '';
    }
  }

  // -----------------------------------------------------------------------
  // Main API call
  // -----------------------------------------------------------------------

  /**
   * Fetch item (product) information from the Goofish H5 API.
   *
   * Mirrors `XianyuApis.get_item_info` — builds the same query parameters,
   * signs the request identically, and retries up to 3 times on failure.
   *
   * @param {string} itemId       The Goofish item / product ID.
   * @param {number} [retryCount] Internal retry counter (callers should omit).
   * @returns {Promise<object|null>} The item data object, or null on failure.
   */
  async getItemInfo(itemId, retryCount = 0) {
    if (retryCount >= 3) {
      console.error('[XianyuBot] Failed to get item info after 3 retries:', itemId);
      return null;
    }

    // -- Timestamp ---------------------------------------------------------
    // Python:  str(int(time.time()) * 1000)
    // This truncates to whole seconds first, so the value always ends in 000.
    const t = String(Math.floor(Date.now() / 1000) * 1000);

    // -- Token & signature -------------------------------------------------
    const token = await this.getToken();
    // Build the data payload exactly as the Python source does:
    //   data_val = '{"itemId":"' + item_id + '"}'
    const dataVal = '{"itemId":"' + itemId + '"}';
    const sign = generateSign(t, token, dataVal);

    // -- Query parameters --------------------------------------------------
    const params = new URLSearchParams({
      jsv: '2.7.2',
      appKey: '34839810',
      t,
      sign,
      v: '1.0',
      type: 'originaljson',
      accountSite: 'xianyu',
      dataType: 'json',
      timeout: '20000',
      api: 'mtop.taobao.idle.pc.detail',
      sessionOption: 'AutoLoginOnly',
      spm_cnt: 'a21ybx.im.0.0'
    });

    const url = `https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/?${params}`;

    try {
      // The extension's host_permissions for *.goofish.com allow the service
      // worker to make this cross-origin POST with cookies attached.
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Origin': 'https://www.goofish.com',
          'Referer': 'https://www.goofish.com/'
        },
        body: `data=${encodeURIComponent(dataVal)}`,
        credentials: 'include'
      });

      const resJson = await response.json();

      // -- Check result ----------------------------------------------------
      if (resJson && Array.isArray(resJson.ret)) {
        // Python checks: any('SUCCESS::调用成功' in ret for ret in ret_value)
        // We use the broader 'SUCCESS' substring match for robustness.
        if (resJson.ret.some(r => r.includes('SUCCESS'))) {
          // Return the most useful sub-object if available, otherwise the
          // full response data.
          return resJson.data?.itemDO || resJson.data || resJson;
        }
      }

      // -- Retry on failure ------------------------------------------------
      console.warn(
        '[XianyuBot] Item API call failed, retrying (' + (retryCount + 1) + '/3):',
        resJson?.ret
      );
      await new Promise(resolve => setTimeout(resolve, 500));
      return this.getItemInfo(itemId, retryCount + 1);

    } catch (err) {
      console.error('[XianyuBot] Item API request error:', err);
      await new Promise(resolve => setTimeout(resolve, 500));
      return this.getItemInfo(itemId, retryCount + 1);
    }
  }
}
