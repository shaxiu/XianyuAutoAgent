// options.js — Options page logic

document.addEventListener('DOMContentLoaded', loadSettings);

async function loadSettings() {
  const keys = [
    'apiKey', 'modelBaseUrl', 'modelName',
    'supabaseUrl', 'supabaseKey', 'accountId', 'dashboardUrl',
    'simulateTyping', 'typingDelayBase', 'typingDelayPerChar',
    'messageExpireTime', 'manualModeTimeout', 'toggleKeywords',
  ];
  const settings = await chrome.storage.local.get(keys);

  document.getElementById('apiKey').value = settings.apiKey || '';
  document.getElementById('modelBaseUrl').value = settings.modelBaseUrl || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
  document.getElementById('modelName').value = settings.modelName || 'qwen-max';
  document.getElementById('supabaseUrl').value = settings.supabaseUrl || '';
  document.getElementById('supabaseKey').value = settings.supabaseKey || '';
  document.getElementById('accountId').value = settings.accountId || '';
  document.getElementById('dashboardUrl').value = settings.dashboardUrl || '';
  document.getElementById('simulateTyping').checked = settings.simulateTyping !== false;
  document.getElementById('typingDelayBaseMin').value = (settings.typingDelayBase || [0, 1000])[0];
  document.getElementById('typingDelayBaseMax').value = (settings.typingDelayBase || [0, 1000])[1];
  document.getElementById('typingDelayPerCharMin').value = (settings.typingDelayPerChar || [50, 150])[0];
  document.getElementById('typingDelayPerCharMax').value = (settings.typingDelayPerChar || [50, 150])[1];
  document.getElementById('messageExpireTime').value = (settings.messageExpireTime || 300000) / 1000;
  document.getElementById('manualModeTimeout').value = settings.manualModeTimeout || 3600;
  document.getElementById('toggleKeywords').value = settings.toggleKeywords || '\u3002';
}

document.getElementById('saveBtn').addEventListener('click', async () => {
  const settings = {
    apiKey: document.getElementById('apiKey').value.trim(),
    modelBaseUrl: document.getElementById('modelBaseUrl').value.trim(),
    modelName: document.getElementById('modelName').value.trim(),
    supabaseUrl: document.getElementById('supabaseUrl').value.trim(),
    supabaseKey: document.getElementById('supabaseKey').value.trim(),
    accountId: document.getElementById('accountId').value.trim(),
    dashboardUrl: document.getElementById('dashboardUrl').value.trim(),
    simulateTyping: document.getElementById('simulateTyping').checked,
    typingDelayBase: [
      parseInt(document.getElementById('typingDelayBaseMin').value) || 0,
      parseInt(document.getElementById('typingDelayBaseMax').value) || 1000,
    ],
    typingDelayPerChar: [
      parseInt(document.getElementById('typingDelayPerCharMin').value) || 50,
      parseInt(document.getElementById('typingDelayPerCharMax').value) || 150,
    ],
    messageExpireTime: (parseInt(document.getElementById('messageExpireTime').value) || 300) * 1000,
    manualModeTimeout: parseInt(document.getElementById('manualModeTimeout').value) || 3600,
    toggleKeywords: document.getElementById('toggleKeywords').value || '\u3002',
  };

  await chrome.storage.local.set(settings);
  chrome.runtime.sendMessage({ type: 'UPDATE_SETTINGS', settings });
  showStatus('设置已保存', 'success');
});

document.getElementById('openDashboard')?.addEventListener('click', () => {
  const url = document.getElementById('dashboardUrl').value || 'https://your-dashboard.vercel.app';
  chrome.tabs.create({ url });
});

document.getElementById('refreshPrompts')?.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'REFRESH_PROMPTS' });
  showStatus('Prompt 缓存已刷新', 'success');
});

function showStatus(message, type) {
  const el = document.getElementById('statusMsg');
  el.textContent = message;
  el.className = 'status-msg ' + type;
  setTimeout(() => { el.textContent = ''; el.className = 'status-msg'; }, 3000);
}

document.querySelectorAll('.toggle-visibility').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = btn.previousElementSibling;
    input.type = input.type === 'password' ? 'text' : 'password';
    btn.textContent = input.type === 'password' ? '显示' : '隐藏';
  });
});
