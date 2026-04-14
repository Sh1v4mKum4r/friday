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

function initFriday() {
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
  dom.settingsProviders.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    var res = await fetch(API + '/health');
    var data = await res.json();
    dom.settingsProviders.innerHTML = data.providers.map(function(p) {
      return '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px;">' + escapeHtml(p) + '</div>';
    }).join('');
  } catch(e) {
    dom.settingsProviders.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading providers</div>';
  }
}

async function loadMCP() {
  if (!dom.settingsMCP) return;
  dom.settingsMCP.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    var res = await fetch(API + '/mcp/status');
    var data = await res.json();
    if (!data.servers || data.servers.length === 0) {
      dom.settingsMCP.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">No MCP servers</div>';
    } else {
      dom.settingsMCP.innerHTML = data.servers.map(function(s) {
        return '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px;">' + escapeHtml(s) + '</div>';
      }).join('');
    }
  } catch(e) {
    dom.settingsMCP.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading MCP</div>';
  }
}

async function loadTools() {
  if (!dom.settingsTools) return;
  dom.settingsTools.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    var res = await fetch(API + '/reload', { method: 'POST' });
    var data = await res.json();
    dom.settingsTools.innerHTML = '<div style="display:flex; flex-wrap:wrap; gap:6px;">' +
      data.tools.map(function(t) {
        return '<span style="background:rgba(255,255,255,0.08); padding:4px 8px; border-radius:4px; font-size:11px;">' + escapeHtml(t) + '</span>';
      }).join('') + '</div>';
  } catch(e) {
    dom.settingsTools.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading tools</div>';
  }
}

async function loadMemory() {
  if (!dom.settingsMemory) return;
  dom.settingsMemory.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    var res = await fetch(API + '/memory/list', { method: 'POST' });
    var data = await res.json();
    if (!data.entries || data.entries.length === 0) {
      dom.settingsMemory.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Memory is empty</div>';
    } else {
      dom.settingsMemory.innerHTML = data.entries.map(function(m) {
        return '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); display:flex; justify-content:space-between; align-items:center; font-size:13px;">' +
          '<span>' + escapeHtml(m) + '</span>' +
          '<button onclick="window.fridayForgetMemory(\'' + escapeHtml(m).replace(/'/g, "\\'") + '\')" style="color:#ff6e84; cursor:pointer; background:none; border:none; font-size:12px;">X</button>' +
        '</div>';
      }).join('');
    }
  } catch(e) {
    dom.settingsMemory.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading memory</div>';
  }
}

window.fridayForgetMemory = async function(keyword) {
  try {
    await fetch(API + '/memory/forget?query=' + encodeURIComponent(keyword), { method: 'POST' });
    loadMemory();
  } catch(e) {}
};

window.fridayClearMemory = async function() {
  if (!confirm('Clear all memory context?')) return;
  try {
    await fetch(API + '/memory/clear', { method: 'POST' });
    loadMemory();
  } catch(e) {}
};

var THEMES = [
  { id: 'obsidian', name: 'Obsidian', color: '#ba9eff', desc: 'Editorial glass' },
  { id: 'techno', name: 'Techno', color: '#4ae176', desc: 'Terminal brutalist' },
  { id: 'neural', name: 'Neural', color: '#69daff', desc: 'Synthetic HUD' },
  { id: 'prism', name: 'Prism', color: '#ff1a1a', desc: 'Kinetic stealth' }
];

function renderThemeSelect() {
  if (!dom.themeSelect) return;
  var current = safeStorage.getItem(THEME_KEY) || 'obsidian';
  dom.themeSelect.innerHTML = THEMES.map(function(t) {
    return '<div onclick="window.fridayApplyTheme(\'' + t.id + '\')" ' +
    'style="display:flex; align-items:center; gap:12px; padding:10px; cursor:pointer; border:1px solid ' +
    (t.id === current ? t.color : 'rgba(255,255,255,0.08)') + '; margin-bottom:6px; transition:all 0.2s;">' +
      '<div style="width:12px; height:12px; border-radius:50%; background:' + t.color + ';"></div>' +
      '<div>' +
        '<div style="font-size:13px; font-weight:500;">' + t.name + '</div>' +
        '<div style="font-size:11px; opacity:0.5;">' + t.desc + '</div>' +
      '</div>' +
      (t.id === current ? '<span style="margin-left:auto; font-size:11px; opacity:0.5;">Active</span>' : '') +
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

async function checkHealth() {
  try {
    var res = await fetch(API + '/health');
    var data = await res.json();
    var dot = document.getElementById('healthDot');
    if (dot) dot.className = data.providers && data.providers.length > 0 ? 'online' : 'offline';
  } catch(e) {
    var dot = document.getElementById('healthDot');
    if (dot) dot.className = 'offline';
  }
}
