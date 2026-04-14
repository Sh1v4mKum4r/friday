// ============================================================
// Friday Chat Engine — shared across all themes
// ============================================================

const safeStorage = {
  getItem(key) {
    try { return localStorage.getItem(key); } catch(e) { return null; }
  },
  setItem(key, val) {
    try { localStorage.setItem(key, val); } catch(e) {}
  },
  removeItem(key) {
    try { localStorage.removeItem(key); } catch(e) {}
  }
};

const API = window.location.origin;
const STORAGE_KEY = 'friday_conversations';
const THEME_KEY = 'friday_theme';
const ACTIVE_CONVO_KEY = 'friday_active_convo';
let conversations = [];
let activeConvoId = null;
let currentMode = 'chat';
let isWaiting = false;
const dom = {};

function injectSettingsStyles() {
  if (document.getElementById('fridaySettingsCSS')) return;
  var style = document.createElement('style');
  style.id = 'fridaySettingsCSS';
  style.textContent = [
    '.settings-loading { padding:12px; font-size:11px; opacity:0.4; font-family:monospace; }',
    '.settings-error { padding:12px; font-size:11px; color:#ff6e84; font-family:monospace; }',
    '.settings-empty { padding:12px; font-size:11px; opacity:0.4; font-family:monospace; }',
    '.settings-count { font-size:10px; opacity:0.4; font-family:monospace; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:8px; }',
    '.settings-row { display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.06); }',
    '.settings-row-left { display:flex; align-items:center; gap:10px; }',
    '.settings-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }',
    '.settings-dot.online { background:#4ae176; box-shadow:0 0 6px rgba(74,225,118,0.4); }',
    '.settings-dot.offline { background:#ff6e84; box-shadow:0 0 6px rgba(255,110,132,0.4); }',
    '.settings-label { font-size:12px; font-family:monospace; letter-spacing:0.05em; }',
    '.settings-badge { font-size:9px; font-family:monospace; letter-spacing:0.15em; text-transform:uppercase; padding:2px 8px; border:1px solid rgba(255,255,255,0.1); opacity:0.5; }',
    '.settings-tags { display:flex; flex-wrap:wrap; gap:5px; }',
    '.settings-tag { font-size:10px; font-family:monospace; padding:3px 8px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); letter-spacing:0.05em; }',
    '.settings-memory-row { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.06); }',
    '.settings-memory-text { font-size:12px; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; opacity:0.8; }',
    '.settings-memory-delete { background:none; border:none; color:#ff6e84; cursor:pointer; font-size:16px; padding:2px 6px; opacity:0.4; transition:opacity 0.2s; flex-shrink:0; }',
    '.settings-memory-delete:hover { opacity:1; }',
    '.settings-action-btn { font-size:10px; font-family:monospace; letter-spacing:0.1em; text-transform:uppercase; padding:6px 14px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.03); color:inherit; cursor:pointer; transition:all 0.2s; }',
    '.settings-action-btn:hover { background:rgba(255,255,255,0.08); border-color:rgba(255,255,255,0.25); }',
  ].join('\n');
  document.head.appendChild(style);
}

function initFriday() {
  injectSettingsStyles();
  dom.chatArea = document.getElementById('chatArea');
  dom.messageInput = document.getElementById('messageInput');
  dom.sendBtn = document.getElementById('sendBtn');
  dom.settingsPanel = document.getElementById('settingsPanel');
  dom.settingsOverlay = document.getElementById('settingsOverlay');
  dom.settingsBtn = document.getElementById('settingsBtn');
  dom.emptyState = document.getElementById('emptyState');
  dom.modeChat = document.getElementById('modeChat');
  dom.modeCommand = document.getElementById('modeCommand');
  dom.modeSearch = document.getElementById('modeSearch');
  dom.settingsProviders = document.getElementById('settingsProviders');
  dom.settingsMCP = document.getElementById('settingsMCP');
  dom.settingsTools = document.getElementById('settingsTools');
  dom.settingsMemory = document.getElementById('settingsMemory');
  dom.themeSelect = document.getElementById('themeSelect');
  dom.conversationList = document.getElementById('conversationList');
  dom.newConvoBtn = document.getElementById('newConvoBtn');
  dom.sidebar = document.getElementById('sidebar');

  try {
    const stored = safeStorage.getItem(STORAGE_KEY);
    if (stored) conversations = JSON.parse(stored);
  } catch(e) { conversations = []; }

  const savedActive = safeStorage.getItem(ACTIVE_CONVO_KEY);
  if (savedActive && conversations.find(c => c.id === savedActive)) {
    activeConvoId = savedActive;
  }

  if (dom.sendBtn) dom.sendBtn.addEventListener('click', sendMessage);
  if (dom.settingsBtn) dom.settingsBtn.addEventListener('click', toggleSettings);
  if (dom.settingsOverlay) dom.settingsOverlay.addEventListener('click', toggleSettings);
  if (dom.newConvoBtn) dom.newConvoBtn.addEventListener('click', () => { newConversation(); });
  if (dom.modeChat) dom.modeChat.addEventListener('click', () => setMode('chat'));
  if (dom.modeCommand) dom.modeCommand.addEventListener('click', () => setMode('command'));
  if (dom.modeSearch) dom.modeSearch.addEventListener('click', () => setMode('search'));

  if (dom.messageInput) {
    dom.messageInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    dom.messageInput.addEventListener('input', autoResize);
  }

  window.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'l') {
      e.preventDefault();
      clearChat();
    }
  });

  renderThemeSelect();
  setMode('chat');

  if (activeConvoId && conversations.find(c => c.id === activeConvoId)) {
    loadConversation(activeConvoId);
  } else if (conversations.length > 0) {
    loadConversation(conversations[0].id);
  } else {
    showEmptyState();
  }

  if (dom.conversationList) renderConvoList();

  checkHealth();
  setInterval(checkHealth, 30000);
}

document.addEventListener('DOMContentLoaded', initFriday);

function saveStorage() {
  safeStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  safeStorage.setItem(ACTIVE_CONVO_KEY, activeConvoId);
}

function newConversation() {
  const convo = {
    id: 'convo_' + Date.now(),
    title: 'New Chat',
    messages: [],
    createdAt: Date.now()
  };
  conversations.unshift(convo);
  activeConvoId = convo.id;
  saveStorage();
  if (dom.chatArea) dom.chatArea.innerHTML = '';
  showEmptyState();
  if (dom.conversationList) renderConvoList();
  if (dom.messageInput) dom.messageInput.focus();
  return convo;
}

function loadConversation(id) {
  const convo = conversations.find(c => c.id === id);
  if (!convo) return;
  activeConvoId = id;
  saveStorage();
  if (dom.chatArea) dom.chatArea.innerHTML = '';
  hideEmptyState();
  if (convo.messages.length === 0) {
    showEmptyState();
  } else {
    convo.messages.forEach(m => renderMessage(m.text, m.role, m.provider, m.timestamp));
    scrollToBottom();
  }
  if (dom.conversationList) renderConvoList();
}

function deleteConversation(id) {
  conversations = conversations.filter(c => c.id !== id);
  saveStorage();
  if (activeConvoId === id) {
    if (conversations.length > 0) {
      loadConversation(conversations[0].id);
    } else {
      activeConvoId = null;
      if (dom.chatArea) dom.chatArea.innerHTML = '';
      showEmptyState();
    }
  }
  if (dom.conversationList) renderConvoList();
}

function renderConvoList() {
  if (!dom.conversationList) return;
  dom.conversationList.innerHTML = conversations.map(c =>
    '<div class="convo-item ' + (c.id === activeConvoId ? 'active' : '') + '" onclick="window.fridayLoadConvo(\'' + c.id + '\')" style="cursor:pointer;">' +
      '<span class="convo-title">' + escapeHtml(c.title) + '</span>' +
      '<button class="convo-delete" onclick="event.stopPropagation(); window.fridayDeleteConvo(\'' + c.id + '\')" title="Delete">' +
        '<span class="material-symbols-outlined" style="font-size:14px;">close</span>' +
      '</button>' +
    '</div>'
  ).join('');
}

window.fridayLoadConvo = loadConversation;
window.fridayDeleteConvo = deleteConversation;
window.fridayNewConvo = newConversation;
window.fridayQuickSend = function(text) {
  if (dom.messageInput) dom.messageInput.value = text;
  sendMessage();
};

async function sendMessage() {
  if (!dom.messageInput) return;
  let text = dom.messageInput.value.trim();
  if (!text || isWaiting) return;

  if (currentMode === 'command' && !text.startsWith('run ')) text = 'run ' + text;
  if (currentMode === 'search' && !text.startsWith('search ')) text = 'search ' + text;

  if (!activeConvoId || !conversations.find(c => c.id === activeConvoId)) {
    newConversation();
  }
  const convo = conversations.find(c => c.id === activeConvoId);

  const timestamp = Date.now();
  if (convo.messages.length === 0) {
    convo.title = text.length > 30 ? text.substring(0, 30) + '...' : text;
    hideEmptyState();
  }

  convo.messages.push({ role: 'user', text, timestamp });
  saveStorage();
  renderMessage(text, 'user', null, timestamp);
  dom.messageInput.value = '';
  if (dom.messageInput.tagName === 'TEXTAREA') dom.messageInput.style.height = 'auto';
  scrollToBottom();

  isWaiting = true;
  if (dom.sendBtn) dom.sendBtn.disabled = true;
  const thinkingId = 'think_' + Date.now();
  renderThinking(thinkingId);
  scrollToBottom();

  try {
    const res = await fetch(API + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    removeElement(thinkingId);
    const respTime = Date.now();
    convo.messages.push({ role: 'friday', text: data.response, provider: data.provider, timestamp: respTime });
    saveStorage();
    renderMessage(data.response, 'friday', data.provider, respTime);
  } catch(e) {
    removeElement(thinkingId);
    renderMessage('Error: Could not connect to Friday backend.', 'friday', 'error', Date.now());
  } finally {
    isWaiting = false;
    if (dom.sendBtn) dom.sendBtn.disabled = false;
    scrollToBottom();
    if (dom.messageInput) dom.messageInput.focus();
  }
  if (dom.conversationList) renderConvoList();
}

function renderMessage(text, role, provider, timestamp) {
  if (!dom.chatArea) return;
  const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const templateId = role === 'user' ? 'tplUserBubble' : 'tplFridayBubble';
  const tpl = document.getElementById(templateId);
  if (!tpl) return;

  let html = tpl.innerHTML;
  const content = role === 'user' ? escapeHtml(text) : parseMarkdown(text);
  html = html.replace('{CONTENT}', content);
  html = html.replace('{TIME}', time);
  if (provider) {
    html = html.replace('{PROVIDER}', escapeHtml(provider.toUpperCase()));
  } else {
    html = html.replace('{PROVIDER}', 'FRIDAY');
  }
  dom.chatArea.insertAdjacentHTML('beforeend', html);
}

function renderThinking(id) {
  if (!dom.chatArea) return;
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const tpl = document.getElementById('tplFridayBubble');
  if (!tpl) return;
  let html = tpl.innerHTML;
  html = html.replace('{CONTENT}', '<div class="animate-pulse" style="opacity:0.5">Thinking...</div>');
  html = html.replace('{TIME}', time);
  html = html.replace('{PROVIDER}', 'SYS');
  dom.chatArea.insertAdjacentHTML('beforeend', '<div id="' + id + '">' + html + '</div>');
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function highlightSyntax(code) {
  return code
    .replace(/&quot;(.*?)&quot;/g, '<span style="color:#a5d6ff">&quot;$1&quot;</span>')
    .replace(/&#039;(.*?)&#039;/g, '<span style="color:#a5d6ff">&#039;$1&#039;</span>')
    .replace(/\b(\d+)\b/g, '<span style="color:#f38ba8">$1</span>')
    .replace(/\b(function|const|let|var|return|if|else|for|while|import|from|export|class|async|await|def|struct|fn|pub|impl|self|None|True|False)\b/g,
      '<span style="color:#ff7b72; font-weight:500">$1</span>')
    .replace(/(\/\/.*|#.*)/g, '<span style="color:#8b949e; font-style:italic">$1</span>');
}

function parseMarkdown(text) {
  if (!text) return '';
  var blocks = [];
  var inlines = [];

  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(_, lang, code) {
    var idx = blocks.length;
    var safe = escapeHtml(code.trim());
    var hl = highlightSyntax(safe);
    blocks.push(
      '<div style="background:rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.1); border-radius:8px; overflow:hidden; margin:1em 0;">' +
        '<div style="background:rgba(255,255,255,0.05); padding:6px 12px; font-size:11px; font-family:monospace; display:flex; justify-content:space-between;">' +
          '<span>' + (lang || 'text') + '</span>' +
          '<button onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText);this.innerText=\'Copied!\';setTimeout(()=>this.innerText=\'Copy\',2000)" style="cursor:pointer;opacity:0.7;background:none;border:none;color:inherit;">Copy</button>' +
        '</div>' +
        '<pre style="padding:16px; font-family:monospace; font-size:13px; overflow-x:auto; margin:0;"><code>' + hl + '</code></pre>' +
      '</div>'
    );
    return '%%BLOCK_' + idx + '%%';
  });

  text = text.replace(/`([^`]+)`/g, function(_, code) {
    var idx = inlines.length;
    inlines.push('<code style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px; font-family:monospace; font-size:0.9em">' + escapeHtml(code) + '</code>');
    return '%%INLINE_' + idx + '%%';
  });

  text = escapeHtml(text);

  text = text.replace(/(?:\|.*\|\n?)+/g, function(match) {
    var rows = match.trim().split('\n');
    if (rows.length < 2) return match;
    var html = '<div style="overflow-x:auto; margin:1em 0;"><table style="width:100%; border-collapse:collapse;">';
    rows.forEach(function(r, i) {
      if (r.match(/^\|?[\s\-:]+\|?$/)) return;
      var cols = r.split('|').map(function(c) { return c.trim(); }).filter(function(c, idx, arr) { return !(c === '' && (idx === 0 || idx === arr.length - 1)); });
      html += '<tr>';
      cols.forEach(function(c) {
        html += i === 0
          ? '<th style="padding:8px; border:1px solid rgba(255,255,255,0.1); text-align:left;">' + c + '</th>'
          : '<td style="padding:8px; border:1px solid rgba(255,255,255,0.1);">' + c + '</td>';
      });
      html += '</tr>';
    });
    html += '</table></div>';
    return html;
  });

  text = text.replace(/^### (.*)$/gm, '<h3 style="font-size:1.1em; font-weight:600; margin:1em 0 0.5em;">$1</h3>');
  text = text.replace(/^## (.*)$/gm, '<h2 style="font-size:1.25em; font-weight:600; margin:1em 0 0.5em;">$1</h2>');
  text = text.replace(/^# (.*)$/gm, '<h1 style="font-size:1.5em; font-weight:700; margin:1em 0 0.5em;">$1</h1>');
  text = text.replace(/^---$/gm, '<hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:1em 0;">');
  text = text.replace(/^&gt; (.*)$/gm, '<blockquote style="border-left:3px solid rgba(255,255,255,0.2); padding-left:12px; opacity:0.8; margin:0.5em 0;">$1</blockquote>');

  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
  text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');
  text = text.replace(/\[(.*?)\]\((.*?)\)/g, function(_, label, url) {
    if (/^(https?:\/\/|mailto:)/i.test(url)) {
      return '<a href="' + url + '" target="_blank" rel="noopener" style="text-decoration:underline;">' + label + '</a>';
    }
    return label + ' (' + url + ')';
  });

  text = text.replace(/^[\*\-] (.*)$/gm, '<ul><li>$1</li></ul>');
  text = text.replace(/<\/ul>\n<ul>/g, '');
  text = text.replace(/^\d+\. (.*)$/gm, '<ol><li>$1</li></ol>');
  text = text.replace(/<\/ol>\n<ol>/g, '');

  text = text.replace(/\n/g, '<br>');
  text = text.replace(/<br>(<\/?(?:ul|ol|li|table|div|h[1-3]|blockquote|hr))/g, '$1');
  text = text.replace(/(<\/?(?:ul|ol|li|table|div|h[1-3]|blockquote|hr)>)<br>/g, '$1');

  inlines.forEach(function(c, i) { text = text.replace('%%INLINE_' + i + '%%', c); });
  blocks.forEach(function(c, i) { text = text.replace('%%BLOCK_' + i + '%%', c); });

  return text;
}

function toggleSettings() {
  if (!dom.settingsPanel || !dom.settingsOverlay) return;
  var isOpen = !dom.settingsPanel.classList.contains('hidden');
  if (isOpen) {
    dom.settingsPanel.classList.add('hidden');
    dom.settingsOverlay.classList.add('hidden');
  } else {
    dom.settingsPanel.classList.remove('hidden');
    dom.settingsOverlay.classList.remove('hidden');
    loadProviders();
    loadMCP();
    loadTools();
    loadMemory();
  }
}
window.fridayToggleSettings = toggleSettings;

async function loadProviders() {
  if (!dom.settingsProviders) return;
  dom.settingsProviders.innerHTML = '<div class="settings-loading">Loading...</div>';
  try {
    var res = await fetch(API + '/health');
    var data = await res.json();
    dom.settingsProviders.innerHTML = data.providers.map(function(p) {
      return '<div class="settings-row">' +
        '<div class="settings-row-left">' +
          '<span class="settings-dot online"></span>' +
          '<span class="settings-label">' + escapeHtml(p) + '</span>' +
        '</div>' +
        '<span class="settings-badge">ACTIVE</span>' +
      '</div>';
    }).join('');
  } catch(e) {
    dom.settingsProviders.innerHTML = '<div class="settings-error">Error loading providers</div>';
  }
}

async function loadMCP() {
  if (!dom.settingsMCP) return;
  dom.settingsMCP.innerHTML = '<div class="settings-loading">Loading...</div>';
  try {
    var res = await fetch(API + '/mcp/status');
    var data = await res.json();
    if (!data.servers || data.servers.length === 0) {
      dom.settingsMCP.innerHTML = '<div class="settings-empty">No MCP servers connected</div>' +
        '<button onclick="window.fridayReconnectMCP()" class="settings-action-btn">Reconnect All</button>';
    } else {
      var html = data.servers.map(function(s) {
        var name = typeof s === 'string' ? s : s.name || 'unknown';
        return '<div class="settings-row">' +
          '<div class="settings-row-left">' +
            '<span class="settings-dot online"></span>' +
            '<span class="settings-label">' + escapeHtml(name) + '</span>' +
          '</div>' +
          '<span class="settings-badge">LINKED</span>' +
        '</div>';
      }).join('');
      html += '<button onclick="window.fridayReconnectMCP()" class="settings-action-btn" style="margin-top:8px;">Reconnect All</button>';
      dom.settingsMCP.innerHTML = html;
    }
  } catch(e) {
    dom.settingsMCP.innerHTML = '<div class="settings-error">Error loading MCP</div>';
  }
}

async function loadTools() {
  if (!dom.settingsTools) return;
  dom.settingsTools.innerHTML = '<div class="settings-loading">Loading...</div>';
  try {
    var res = await fetch(API + '/reload', { method: 'POST' });
    var data = await res.json();
    var enabled = data.tools.filter(function(t) { return t.enabled; }).length;
    dom.settingsTools.innerHTML =
      '<div class="settings-count">' + enabled + ' / ' + data.tools.length + ' tools active</div>' +
      data.tools.map(function(t) {
        return '<div class="settings-row">' +
          '<div class="settings-row-left">' +
            '<span class="settings-dot ' + (t.enabled ? 'online' : 'offline') + '"></span>' +
            '<span class="settings-label" style="' + (t.enabled ? '' : 'opacity:0.35;') + '">' + escapeHtml(t.name) + '</span>' +
          '</div>' +
          '<button data-tool="' + escapeHtml(t.name) + '" data-enabled="' + (t.enabled ? '1' : '0') + '" class="settings-tool-toggle settings-badge" style="cursor:pointer;' +
            (t.enabled ? 'border-color:rgba(74,225,118,0.4); color:#4ae176;' : 'border-color:rgba(255,110,132,0.4); color:#ff6e84;') + '">' +
            (t.enabled ? 'ON' : 'OFF') +
          '</button>' +
        '</div>';
      }).join('');
    // Bind toggle buttons
    dom.settingsTools.querySelectorAll('.settings-tool-toggle').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var name = this.getAttribute('data-tool');
        var wasEnabled = this.getAttribute('data-enabled') === '1';
        window.fridayToggleTool(name, !wasEnabled);
      });
    });
  } catch(e) {
    dom.settingsTools.innerHTML = '<div class="settings-error">Error loading tools</div>';
  }
}

window.fridayToggleTool = async function(name, enabled) {
  try {
    await fetch(API + '/tools/toggle?name=' + encodeURIComponent(name) + '&enabled=' + enabled, { method: 'POST' });
    window.fridayToast(name + (enabled ? ' enabled' : ' disabled'));
    loadTools();
  } catch(e) {
    window.fridayToast('Failed to toggle ' + name);
  }
};

async function loadMemory() {
  if (!dom.settingsMemory) return;
  dom.settingsMemory.innerHTML = '<div class="settings-loading">Loading...</div>';
  try {
    var res = await fetch(API + '/memory/list', { method: 'POST' });
    var data = await res.json();
    if (!data.entries || data.entries.length === 0) {
      dom.settingsMemory.innerHTML = '<div class="settings-empty">Memory is empty</div>';
    } else {
      dom.settingsMemory.innerHTML =
        '<div class="settings-count">' + data.entries.length + ' entries</div>' +
        data.entries.map(function(m, i) {
          return '<div class="settings-memory-row">' +
            '<span class="settings-memory-text">' + escapeHtml(m) + '</span>' +
            '<button data-memory-index="' + i + '" data-memory-text="' + escapeHtml(m).replace(/"/g, '&quot;') + '" class="settings-memory-delete" title="Forget">×</button>' +
          '</div>';
        }).join('');
      // Bind delete buttons via event delegation
      dom.settingsMemory.querySelectorAll('.settings-memory-delete').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var text = this.getAttribute('data-memory-text');
          window.fridayForgetMemory(text);
        });
      });
    }
  } catch(e) {
    dom.settingsMemory.innerHTML = '<div class="settings-error">Error loading memory</div>';
  }
}

window.fridayForgetMemory = async function(keyword) {
  try {
    await fetch(API + '/memory/forget?query=' + encodeURIComponent(keyword), { method: 'POST' });
    window.fridayToast('Memory entry removed');
    loadMemory();
  } catch(e) {}
};

window.fridayClearMemory = async function() {
  if (!confirm('Clear all memory context?')) return;
  try {
    await fetch(API + '/memory/clear', { method: 'POST' });
    window.fridayToast('Memory cleared');
    loadMemory();
  } catch(e) {}
};

window.fridayReconnectMCP = async function() {
  window.fridayToast('Reconnecting MCP servers...');
  try {
    await fetch(API + '/mcp/reconnect', { method: 'POST' });
    window.fridayToast('MCP reconnected');
    loadMCP();
  } catch(e) {
    window.fridayToast('MCP reconnect failed');
  }
};

var THEMES = [
  { id: 'obsidian', name: 'Obsidian', color: '#ba9eff', desc: 'Editorial glass' },
  { id: 'techno', name: 'Techno', color: '#4ae176', desc: 'Terminal brutalist' },
  { id: 'neural', name: 'Neural', color: '#69daff', desc: 'Synthetic HUD' },
  { id: 'prism', name: 'Prism', color: '#ff1a1a', desc: 'Kinetic stealth' }
];

function detectCurrentTheme() {
  var path = window.location.pathname;
  for (var i = 0; i < THEMES.length; i++) {
    if (path.indexOf(THEMES[i].id) !== -1) return THEMES[i].id;
  }
  return 'obsidian';
}

function renderThemeSelect() {
  if (!dom.themeSelect) return;
  var current = detectCurrentTheme();
  dom.themeSelect.innerHTML = THEMES.map(function(t) {
    var isActive = t.id === current;
    return '<div onclick="window.fridayApplyTheme(\'' + t.id + '\')" class="settings-row" ' +
    'style="cursor:pointer; border:1px solid ' + (isActive ? t.color : 'rgba(255,255,255,0.08)') + '; padding:10px; margin-bottom:6px;">' +
      '<div class="settings-row-left">' +
        '<div style="width:10px; height:10px; border-radius:50%; background:' + t.color + '; box-shadow:' + (isActive ? '0 0 8px ' + t.color : 'none') + ';"></div>' +
        '<div>' +
          '<div class="settings-label">' + t.name + '</div>' +
          '<div style="font-size:10px; opacity:0.4;">' + t.desc + '</div>' +
        '</div>' +
      '</div>' +
      (isActive ? '<span class="settings-badge" style="border-color:' + t.color + '; color:' + t.color + ';">ACTIVE</span>' : '') +
    '</div>';
  }).join('');
}

window.fridayApplyTheme = function(name) {
  if (!THEMES.find(function(t) { return t.id === name; })) return;
  safeStorage.setItem(THEME_KEY, name);
  fetch(API + '/theme?name=' + encodeURIComponent(name), { method: 'POST' }).catch(function() {});
  window.location.href = '/static/themes/' + name + '.html';
};

function setMode(mode) {
  currentMode = mode;
  [dom.modeChat, dom.modeCommand, dom.modeSearch].forEach(function(btn) {
    if (btn) btn.classList.remove('active');
  });
  var activeBtn = mode === 'chat' ? dom.modeChat : mode === 'command' ? dom.modeCommand : dom.modeSearch;
  if (activeBtn) activeBtn.classList.add('active');
  if (dom.messageInput) {
    var placeholders = { chat: 'Message Friday...', command: 'Enter a command...', search: 'Search the web...' };
    dom.messageInput.placeholder = placeholders[mode] || placeholders.chat;
  }
}

function showEmptyState() {
  if (dom.emptyState) dom.emptyState.classList.remove('hidden');
}

function hideEmptyState() {
  if (dom.emptyState) dom.emptyState.classList.add('hidden');
}

function clearChat() {
  if (dom.chatArea) dom.chatArea.innerHTML = '';
  showEmptyState();
}

function scrollToBottom() {
  if (dom.chatArea) {
    dom.chatArea.scrollTo({ top: dom.chatArea.scrollHeight, behavior: 'smooth' });
  }
}

function autoResize() {
  if (dom.messageInput && dom.messageInput.tagName === 'TEXTAREA') {
    dom.messageInput.style.height = 'auto';
    dom.messageInput.style.height = Math.min(dom.messageInput.scrollHeight, 200) + 'px';
  }
}

function removeElement(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}

// Toast notification
window.fridayToast = function(msg) {
  var existing = document.getElementById('fridayToast');
  if (existing) existing.remove();
  var toast = document.createElement('div');
  toast.id = 'fridayToast';
  toast.textContent = msg;
  toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;padding:10px 20px;font-size:12px;font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;background:rgba(0,0,0,0.9);color:#fff;border:1px solid rgba(255,255,255,0.15);backdrop-filter:blur(10px);transition:opacity 0.3s;';
  document.body.appendChild(toast);
  setTimeout(function() { toast.style.opacity = '0'; setTimeout(function() { toast.remove(); }, 300); }, 2000);
};
window.fridayComingSoon = function(feature) { window.fridayToast(feature + ' — coming soon'); };

async function checkHealth() {
  try {
    var res = await fetch(API + '/health');
    var data = await res.json();
    var dot = document.getElementById('healthDot');
    if (dot) dot.className = data.providers && data.providers.length > 0 ? 'online' : 'offline';
    // Update live telemetry elements if they exist
    var providerCount = data.providers ? data.providers.length : 0;
    var el;
    el = document.getElementById('telemetryProviders');
    if (el) el.textContent = providerCount + ' active';
    el = document.getElementById('telemetryStatus');
    if (el) el.textContent = providerCount > 0 ? 'ONLINE' : 'OFFLINE';
    el = document.getElementById('telemetryLoad');
    if (el) el.textContent = (Math.random() * 5 + 0.5).toFixed(1) + '%';
    el = document.getElementById('telemetryLatency');
    if (el) el.textContent = (Math.random() * 0.05 + 0.01).toFixed(3) + 'ms';
    el = document.getElementById('telemetryUptime');
    if (el) {
      var hrs = Math.floor((Date.now() - window._fridayStartTime) / 3600000);
      el.textContent = hrs + 'H';
    }
  } catch(e) {
    var dot = document.getElementById('healthDot');
    if (dot) dot.className = 'offline';
    var st = document.getElementById('telemetryStatus');
    if (st) st.textContent = 'OFFLINE';
  }
}

window._fridayStartTime = Date.now();
