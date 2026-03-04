// popup.js — Popup panel logic

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const state = await chrome.runtime.sendMessage({ type: 'GET_STATE' });
    updateUI(state);
  } catch (err) {
    console.error('Failed to get state:', err);
  }

  document.getElementById('autoReplyToggle').addEventListener('change', async () => {
    try {
      await chrome.runtime.sendMessage({ type: 'TOGGLE_AUTO_REPLY' });
      const state = await chrome.runtime.sendMessage({ type: 'GET_STATE' });
      updateUI(state);
    } catch (err) {
      console.error('Failed to toggle:', err);
    }
  });

  document.getElementById('openDashboard').addEventListener('click', async () => {
    const data = await chrome.storage.local.get('dashboardUrl');
    const url = data.dashboardUrl || 'https://your-dashboard.vercel.app';
    chrome.tabs.create({ url });
  });

  document.getElementById('openOptions').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });
});

function updateUI(state) {
  if (!state) return;

  const toggle = document.getElementById('autoReplyToggle');
  const label = document.getElementById('toggleLabel');
  toggle.checked = state.enabled;
  label.textContent = state.enabled ? '自动回复已开启' : '自动回复已关闭';

  const dot = document.getElementById('statusDot');
  dot.className = 'status-dot ' + (state.enabled ? 'active' : 'inactive');

  const stats = state.stats?.today || {};
  document.getElementById('repliedCount').textContent = stats.replied || 0;
  document.getElementById('skippedCount').textContent = stats.skipped || 0;
  document.getElementById('errorCount').textContent = stats.errors || 0;

  document.getElementById('accountId').textContent = state.myId || '未设置';
  document.getElementById('wsStatus').textContent = state.wsConnected ? '已连接' : '未连接';
}
