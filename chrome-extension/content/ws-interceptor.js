// ws-interceptor.js — Listens for WebSocket messages posted by inject.js
// and forwards them to the background service worker.
//
// This runs in the content script's isolated world. inject.js (MAIN world)
// posts messages via window.postMessage; this module picks them up and
// relays them through chrome.runtime.sendMessage.

/**
 * Set up the window.postMessage listener that bridges inject.js → background.
 * @param {function} onMessage - Callback receiving (type, data) for each WS event.
 */
export function setupWsInterceptor(onMessage) {
  window.addEventListener('message', (event) => {
    // Only accept messages from our own window (same origin)
    if (event.source !== window) return;
    if (!event.data || typeof event.data.type !== 'string') return;

    const { type, data } = event.data;

    switch (type) {
      case 'XIANYU_WS_MESSAGE':
        onMessage('message', data);
        break;
      case 'XIANYU_WS_OPEN':
        onMessage('open', data);
        break;
      case 'XIANYU_WS_CLOSE':
        onMessage('close', data);
        break;
      case 'XIANYU_WS_ERROR':
        onMessage('error', data);
        break;
      case 'XIANYU_WS_SEND':
        // Outgoing messages — useful for debugging
        onMessage('send', data);
        break;
      default:
        // Ignore unrelated postMessage events
        break;
    }
  });
}
