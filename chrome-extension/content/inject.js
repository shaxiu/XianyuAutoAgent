// inject.js — Injected into the page context to intercept WebSocket connections and access page-level APIs.
// This file runs in the MAIN world (not isolated). It hooks window.WebSocket
// to intercept all WS connections to wss://wss-goofish.dingtalk.com/ and
// forwards incoming messages to the content script via window.postMessage.

(function () {
  'use strict';

  // Guard against double-injection
  if (window.__XIANYU_WS_HOOKED__) return;
  window.__XIANYU_WS_HOOKED__ = true;

  const TARGET_HOST = 'wss-goofish.dingtalk.com';
  const LOG_PREFIX = '[XianyuAutoReply:inject]';

  // Keep a reference to the original WebSocket constructor
  const OriginalWebSocket = window.WebSocket;

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /**
   * Convert an ArrayBuffer (or typed-array buffer) to a base64 string.
   * Used for forwarding binary WS frames to the content script.
   * @param {ArrayBuffer} buffer
   * @returns {string}
   */
  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  /**
   * Check whether a WebSocket URL targets the Goofish IM server.
   * @param {string} url
   * @returns {boolean}
   */
  function isGoofishWsUrl(url) {
    try {
      const parsed = new URL(url);
      return parsed.host === TARGET_HOST || parsed.host.endsWith('.' + TARGET_HOST);
    } catch {
      return url.indexOf(TARGET_HOST) !== -1;
    }
  }

  /**
   * Post a message to the content script (isolated world) via window.postMessage.
   * The content script's ws-interceptor.js listens for these.
   * @param {string} type     - 'XIANYU_WS_MESSAGE' | 'XIANYU_WS_OPEN' | 'XIANYU_WS_CLOSE'
   * @param {*}      payload  - Data to include
   */
  function postToContentScript(type, payload) {
    try {
      window.postMessage({ type, data: payload }, '*');
    } catch (e) {
      console.warn(LOG_PREFIX, 'postMessage failed:', e);
    }
  }

  // ---------------------------------------------------------------------------
  // WebSocket hook
  // ---------------------------------------------------------------------------

  /**
   * Custom WebSocket constructor that wraps the original.
   * When the target URL matches the Goofish IM server, we attach listeners
   * to intercept incoming messages and forward them.
   */
  function HookedWebSocket(url, protocols) {
    // Create the real WebSocket instance
    let ws;
    if (protocols !== undefined) {
      ws = new OriginalWebSocket(url, protocols);
    } else {
      ws = new OriginalWebSocket(url);
    }

    // Only intercept connections to the target host
    if (!isGoofishWsUrl(url)) {
      return ws;
    }

    console.info(LOG_PREFIX, 'Intercepting WebSocket connection to', url);

    // Notify content script that a new WS connection was opened
    ws.addEventListener('open', function () {
      console.info(LOG_PREFIX, 'WebSocket connected');
      postToContentScript('XIANYU_WS_OPEN', { url });
    });

    // Intercept incoming messages
    ws.addEventListener('message', function (event) {
      try {
        let messageData;
        let messageType;

        if (event.data instanceof ArrayBuffer) {
          // Binary frame: convert to base64
          messageType = 'binary';
          messageData = arrayBufferToBase64(event.data);
        } else if (event.data instanceof Blob) {
          // Blob frame: read asynchronously, then post
          messageType = 'blob';
          const reader = new FileReader();
          reader.onload = function () {
            const base64 = arrayBufferToBase64(reader.result);
            postToContentScript('XIANYU_WS_MESSAGE', {
              messageType: 'binary',
              payload: base64
            });
          };
          reader.readAsArrayBuffer(event.data);
          return; // Posted asynchronously above
        } else {
          // Text frame (JSON string)
          messageType = 'text';
          messageData = event.data;
        }

        postToContentScript('XIANYU_WS_MESSAGE', {
          messageType,
          payload: messageData
        });
      } catch (e) {
        console.warn(LOG_PREFIX, 'Error intercepting WS message:', e);
      }
    });

    // Notify on close
    ws.addEventListener('close', function (event) {
      console.info(LOG_PREFIX, 'WebSocket closed, code:', event.code);
      postToContentScript('XIANYU_WS_CLOSE', {
        url,
        code: event.code,
        reason: event.reason
      });
    });

    // Notify on error
    ws.addEventListener('error', function () {
      console.warn(LOG_PREFIX, 'WebSocket error');
      postToContentScript('XIANYU_WS_ERROR', { url });
    });

    // Optionally intercept outgoing send() for debugging.
    // We wrap send() on this specific instance.
    const originalSend = ws.send.bind(ws);
    ws.send = function (data) {
      try {
        // For debugging: uncomment the line below to log outgoing messages
        // console.debug(LOG_PREFIX, 'WS send:', typeof data === 'string' ? data.substring(0, 200) : data);
        postToContentScript('XIANYU_WS_SEND', {
          messageType: typeof data === 'string' ? 'text' : 'binary',
          payload: typeof data === 'string' ? data : arrayBufferToBase64(data)
        });
      } catch (e) {
        // Silently ignore interception errors; never break the actual send
      }
      return originalSend(data);
    };

    return ws;
  }

  // Copy static properties and prototype from the original WebSocket
  HookedWebSocket.prototype = OriginalWebSocket.prototype;
  HookedWebSocket.CONNECTING = OriginalWebSocket.CONNECTING;
  HookedWebSocket.OPEN = OriginalWebSocket.OPEN;
  HookedWebSocket.CLOSING = OriginalWebSocket.CLOSING;
  HookedWebSocket.CLOSED = OriginalWebSocket.CLOSED;

  // Replace the global WebSocket
  window.WebSocket = HookedWebSocket;

  console.info(LOG_PREFIX, 'WebSocket hook installed. Monitoring connections to', TARGET_HOST);
})();
