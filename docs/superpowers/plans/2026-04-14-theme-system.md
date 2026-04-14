# Friday AI Theme System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gemini's broken single-file theme implementation with 4 separate faithful theme HTML files + shared chat-engine.js, with live theme switching.

**Architecture:** Separate HTML per theme (obsidian, techno, neural, prism) each with their own Tailwind config/CSS/HTML from stitch source files. A shared `chat-engine.js` handles all chat logic, binding to standardized element IDs. A tiny `index.html` loader redirects to the active theme based on localStorage preference.

**Tech Stack:** Tailwind CSS (CDN), vanilla JS, FastAPI static serving, localStorage

**Spec:** `docs/superpowers/specs/2026-04-14-theme-system-design.md`

---

## File Structure

```
friday_ai/static/
├── index.html              # Loader — reads localStorage, redirects (CREATE)
├── chat-engine.js          # Shared JS engine (CREATE)
└── themes/
    ├── obsidian.html       # Obsidian theme (CREATE)
    ├── techno.html         # Techno theme (CREATE)
    ├── neural.html         # Neural theme (CREATE)
    └── prism.html          # Prism theme (CREATE)
```

No backend changes needed — FastAPI's `StaticFiles(directory=static_dir)` mount at `/static` already serves subdirectories.

---

### Task 1: Create index.html loader

**Files:**
- Create: `friday_ai/static/index.html` (replaces Gemini's version)

- [ ] **Step 1: Back up Gemini's index.html**

```bash
cd /home/sh4d0w/Projects/friday
cp friday_ai/static/index.html friday_ai/static/index.html.gemini-bak
```

- [ ] **Step 2: Write the loader**

Write `friday_ai/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Friday</title>
<style>
  body { margin: 0; background: #000; color: #fff; font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; }
</style>
</head>
<body>
<script>
(function() {
  var theme;
  try { theme = localStorage.getItem('friday_theme'); } catch(e) {}
  if (!theme || ['obsidian','techno','neural','prism'].indexOf(theme) === -1) {
    theme = 'obsidian';
  }
  window.location.replace('/static/themes/' + theme + '.html');
})();
</script>
<noscript>
  <a href="/static/themes/obsidian.html">Open Friday</a>
</noscript>
</body>
</html>
```

- [ ] **Step 3: Create themes directory**

```bash
mkdir -p friday_ai/static/themes
```

- [ ] **Step 4: Commit**

```bash
git add friday_ai/static/index.html friday_ai/static/index.html.gemini-bak friday_ai/static/themes/
git commit -m "feat: add theme loader index.html, back up Gemini version"
```

---

### Task 2: Create chat-engine.js

**Files:**
- Create: `friday_ai/static/chat-engine.js`

This is the shared JS engine that all theme pages include. It binds to standardized element IDs and handles all chat functionality.

**Reference:** The working JS logic is in `friday_ai/static/index.html.bak` (the original pre-Gemini UI). Extract and refactor from there.

- [ ] **Step 1: Write the safeStorage wrapper and global state**

Begin `friday_ai/static/chat-engine.js`:

```javascript
// ============================================================
// Friday Chat Engine — shared across all themes
// ============================================================

// Safe localStorage wrapper for pywebview compatibility
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

// Global state
const API = window.location.origin;
const STORAGE_KEY = 'friday_conversations';
const THEME_KEY = 'friday_theme';
const ACTIVE_CONVO_KEY = 'friday_active_convo';
let conversations = [];
let activeConvoId = null;
let currentMode = 'chat';
let isWaiting = false;

// DOM references (populated on init)
const dom = {};
```

- [ ] **Step 2: Write the init function**

Append to `chat-engine.js`:

```javascript
function initFriday() {
  // Discover DOM elements by standardized IDs
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
  // Optional (Obsidian only)
  dom.conversationList = document.getElementById('conversationList');
  dom.newConvoBtn = document.getElementById('newConvoBtn');
  dom.sidebar = document.getElementById('sidebar');

  // Load conversations from storage
  try {
    const stored = safeStorage.getItem(STORAGE_KEY);
    if (stored) conversations = JSON.parse(stored);
  } catch(e) { conversations = []; }

  // Restore active conversation
  const savedActive = safeStorage.getItem(ACTIVE_CONVO_KEY);
  if (savedActive && conversations.find(c => c.id === savedActive)) {
    activeConvoId = savedActive;
  }

  // Bind event listeners
  if (dom.sendBtn) dom.sendBtn.addEventListener('click', sendMessage);
  if (dom.settingsBtn) dom.settingsBtn.addEventListener('click', toggleSettings);
  if (dom.settingsOverlay) dom.settingsOverlay.addEventListener('click', toggleSettings);
  if (dom.newConvoBtn) dom.newConvoBtn.addEventListener('click', () => { newConversation(); });
  if (dom.modeChat) dom.modeChat.addEventListener('click', () => setMode('chat'));
  if (dom.modeCommand) dom.modeCommand.addEventListener('click', () => setMode('command'));
  if (dom.modeSearch) dom.modeSearch.addEventListener('click', () => setMode('search'));

  // Input handlers
  if (dom.messageInput) {
    dom.messageInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    dom.messageInput.addEventListener('input', autoResize);
  }

  // Global keyboard shortcuts
  window.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'l') {
      e.preventDefault();
      clearChat();
    }
  });

  // Render theme selector
  renderThemeSelect();

  // Set initial mode highlight
  setMode('chat');

  // Load conversation or show empty state
  if (activeConvoId && conversations.find(c => c.id === activeConvoId)) {
    loadConversation(activeConvoId);
  } else if (conversations.length > 0) {
    loadConversation(conversations[0].id);
  } else {
    showEmptyState();
  }

  // Render sidebar if available
  if (dom.conversationList) renderConvoList();

  // Health check
  checkHealth();
  setInterval(checkHealth, 30000);
}

document.addEventListener('DOMContentLoaded', initFriday);
```

- [ ] **Step 3: Write conversation management functions**

Append to `chat-engine.js`:

```javascript
// ============================================================
// Conversation Management
// ============================================================

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
  dom.conversationList.innerHTML = conversations.map(c => `
    <div class="convo-item ${c.id === activeConvoId ? 'active' : ''}"
         onclick="window.fridayLoadConvo('${c.id}')"
         style="cursor:pointer;">
      <span class="convo-title">${escapeHtml(c.title)}</span>
      <button class="convo-delete" onclick="event.stopPropagation(); window.fridayDeleteConvo('${c.id}')"
              title="Delete">
        <span class="material-symbols-outlined" style="font-size:14px;">close</span>
      </button>
    </div>
  `).join('');
}

// Expose for onclick handlers in theme HTML
window.fridayLoadConvo = loadConversation;
window.fridayDeleteConvo = deleteConversation;
window.fridayNewConvo = newConversation;
window.fridayQuickSend = function(text) {
  if (dom.messageInput) dom.messageInput.value = text;
  sendMessage();
};
```

- [ ] **Step 4: Write sendMessage and message rendering**

Append to `chat-engine.js`:

```javascript
// ============================================================
// Chat
// ============================================================

async function sendMessage() {
  if (!dom.messageInput) return;
  let text = dom.messageInput.value.trim();
  if (!text || isWaiting) return;

  // Apply mode prefix
  if (currentMode === 'command' && !text.startsWith('run ')) text = 'run ' + text;
  if (currentMode === 'search' && !text.startsWith('search ')) text = 'search ' + text;

  // Ensure conversation exists
  if (!activeConvoId || !conversations.find(c => c.id === activeConvoId)) {
    newConversation();
  }
  const convo = conversations.find(c => c.id === activeConvoId);

  // Set title from first message
  const timestamp = Date.now();
  if (convo.messages.length === 0) {
    convo.title = text.length > 30 ? text.substring(0, 30) + '...' : text;
    hideEmptyState();
  }

  // Store and render user message
  convo.messages.push({ role: 'user', text, timestamp });
  saveStorage();
  renderMessage(text, 'user', null, timestamp);
  dom.messageInput.value = '';
  if (dom.messageInput.tagName === 'TEXTAREA') dom.messageInput.style.height = 'auto';
  scrollToBottom();

  // Show thinking indicator
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

// ============================================================
// Message Rendering via Templates
// ============================================================

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

  dom.chatArea.insertAdjacentHTML('beforeend', `<div id="${id}">${html}</div>`);
}
```

- [ ] **Step 5: Write markdown parser**

Append to `chat-engine.js`:

```javascript
// ============================================================
// Markdown Parser
// ============================================================

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
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
  const blocks = [];
  const inlines = [];

  // Code blocks
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(_, lang, code) {
    const idx = blocks.length;
    const safe = escapeHtml(code.trim());
    const hl = highlightSyntax(safe);
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

  // Inline code
  text = text.replace(/`([^`]+)`/g, function(_, code) {
    const idx = inlines.length;
    inlines.push('<code style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px; font-family:monospace; font-size:0.9em">' + escapeHtml(code) + '</code>');
    return '%%INLINE_' + idx + '%%';
  });

  text = escapeHtml(text);

  // Tables
  text = text.replace(/(?:\|.*\|\n?)+/g, function(match) {
    const rows = match.trim().split('\n');
    if (rows.length < 2) return match;
    let html = '<div style="overflow-x:auto; margin:1em 0;"><table style="width:100%; border-collapse:collapse;">';
    rows.forEach(function(r, i) {
      if (r.match(/^\|?[\s\-:]+\|?$/)) return;
      const cols = r.split('|').map(c => c.trim()).filter((c, idx, arr) => !(c === '' && (idx === 0 || idx === arr.length - 1)));
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

  // Headings
  text = text.replace(/^### (.*)$/gm, '<h3 style="font-size:1.1em; font-weight:600; margin:1em 0 0.5em;">$1</h3>');
  text = text.replace(/^## (.*)$/gm, '<h2 style="font-size:1.25em; font-weight:600; margin:1em 0 0.5em;">$1</h2>');
  text = text.replace(/^# (.*)$/gm, '<h1 style="font-size:1.5em; font-weight:700; margin:1em 0 0.5em;">$1</h1>');
  text = text.replace(/^---$/gm, '<hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:1em 0;">');
  text = text.replace(/^&gt; (.*)$/gm, '<blockquote style="border-left:3px solid rgba(255,255,255,0.2); padding-left:12px; opacity:0.8; margin:0.5em 0;">$1</blockquote>');

  // Inline formatting
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
  text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');
  text = text.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener" style="text-decoration:underline;">$1</a>');

  // Lists
  text = text.replace(/^[\*\-] (.*)$/gm, '<ul><li>$1</li></ul>');
  text = text.replace(/<\/ul>\n<ul>/g, '');
  text = text.replace(/^\d+\. (.*)$/gm, '<ol><li>$1</li></ol>');
  text = text.replace(/<\/ol>\n<ol>/g, '');

  // Newlines
  text = text.replace(/\n/g, '<br>');
  text = text.replace(/<br>(<\/?(?:ul|ol|li|table|div|h[1-3]|blockquote|hr))/g, '$1');
  text = text.replace(/(<\/?(?:ul|ol|li|table|div|h[1-3]|blockquote|hr)>)<br>/g, '$1');

  // Restore placeholders
  inlines.forEach(function(c, i) { text = text.replace('%%INLINE_' + i + '%%', c); });
  blocks.forEach(function(c, i) { text = text.replace('%%BLOCK_' + i + '%%', c); });

  return text;
}
```

- [ ] **Step 6: Write settings, modes, theme switching, and utility functions**

Append to `chat-engine.js`:

```javascript
// ============================================================
// Settings Panel
// ============================================================

function toggleSettings() {
  if (!dom.settingsPanel || !dom.settingsOverlay) return;
  const isOpen = !dom.settingsPanel.classList.contains('hidden');
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
    const res = await fetch(API + '/health');
    const data = await res.json();
    dom.settingsProviders.innerHTML = data.providers.map(p =>
      '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px;">' + escapeHtml(p) + '</div>'
    ).join('');
  } catch(e) {
    dom.settingsProviders.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading providers</div>';
  }
}

async function loadMCP() {
  if (!dom.settingsMCP) return;
  dom.settingsMCP.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    const res = await fetch(API + '/mcp/status');
    const data = await res.json();
    if (!data.servers || data.servers.length === 0) {
      dom.settingsMCP.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">No MCP servers</div>';
    } else {
      dom.settingsMCP.innerHTML = data.servers.map(s =>
        '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); font-size:13px;">' + escapeHtml(s) + '</div>'
      ).join('');
    }
  } catch(e) {
    dom.settingsMCP.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading MCP</div>';
  }
}

async function loadTools() {
  if (!dom.settingsTools) return;
  dom.settingsTools.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    const res = await fetch(API + '/reload', { method: 'POST' });
    const data = await res.json();
    dom.settingsTools.innerHTML = '<div style="display:flex; flex-wrap:wrap; gap:6px;">' +
      data.tools.map(t =>
        '<span style="background:rgba(255,255,255,0.08); padding:4px 8px; border-radius:4px; font-size:11px;">' + escapeHtml(t) + '</span>'
      ).join('') + '</div>';
  } catch(e) {
    dom.settingsTools.innerHTML = '<div style="color:#ff6e84; font-size:12px;">Error loading tools</div>';
  }
}

async function loadMemory() {
  if (!dom.settingsMemory) return;
  dom.settingsMemory.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Loading...</div>';
  try {
    const res = await fetch(API + '/memory/list', { method: 'POST' });
    const data = await res.json();
    if (!data.entries || data.entries.length === 0) {
      dom.settingsMemory.innerHTML = '<div style="padding:10px; font-size:12px; opacity:0.5;">Memory is empty</div>';
    } else {
      dom.settingsMemory.innerHTML = data.entries.map(m =>
        '<div style="padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.08); display:flex; justify-content:space-between; align-items:center; font-size:13px;">' +
          '<span>' + escapeHtml(m) + '</span>' +
          '<button onclick="window.fridayForgetMemory(\'' + escapeHtml(m).replace(/'/g, "\\'") + '\')" style="color:#ff6e84; cursor:pointer; background:none; border:none; font-size:12px;">X</button>' +
        '</div>'
      ).join('');
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

// ============================================================
// Theme Switching
// ============================================================

const THEMES = [
  { id: 'obsidian', name: 'Obsidian', color: '#ba9eff', desc: 'Editorial glass' },
  { id: 'techno', name: 'Techno', color: '#4ae176', desc: 'Terminal brutalist' },
  { id: 'neural', name: 'Neural', color: '#69daff', desc: 'Synthetic HUD' },
  { id: 'prism', name: 'Prism', color: '#ff1a1a', desc: 'Kinetic stealth' }
];

function renderThemeSelect() {
  if (!dom.themeSelect) return;
  const current = safeStorage.getItem(THEME_KEY) || 'obsidian';
  dom.themeSelect.innerHTML = THEMES.map(t =>
    '<div onclick="window.fridayApplyTheme(\'' + t.id + '\')" ' +
    'style="display:flex; align-items:center; gap:12px; padding:10px; cursor:pointer; border:1px solid ' +
    (t.id === current ? t.color : 'rgba(255,255,255,0.08)') + '; margin-bottom:6px; transition:all 0.2s;">' +
      '<div style="width:12px; height:12px; border-radius:50%; background:' + t.color + ';"></div>' +
      '<div>' +
        '<div style="font-size:13px; font-weight:500;">' + t.name + '</div>' +
        '<div style="font-size:11px; opacity:0.5;">' + t.desc + '</div>' +
      '</div>' +
      (t.id === current ? '<span style="margin-left:auto; font-size:11px; opacity:0.5;">Active</span>' : '') +
    '</div>'
  ).join('');
}

window.fridayApplyTheme = function(name) {
  if (!THEMES.find(t => t.id === name)) return;
  safeStorage.setItem(THEME_KEY, name);
  window.location.href = '/static/themes/' + name + '.html';
};

// ============================================================
// Mode Switching
// ============================================================

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

// ============================================================
// Utilities
// ============================================================

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
  const el = document.getElementById(id);
  if (el) el.remove();
}

async function checkHealth() {
  try {
    const res = await fetch(API + '/health');
    const data = await res.json();
    // Themes can add a #healthDot element for status indication
    const dot = document.getElementById('healthDot');
    if (dot) dot.className = data.providers && data.providers.length > 0 ? 'online' : 'offline';
  } catch(e) {
    const dot = document.getElementById('healthDot');
    if (dot) dot.className = 'offline';
  }
}
```

- [ ] **Step 7: Commit chat-engine.js**

```bash
git add friday_ai/static/chat-engine.js
git commit -m "feat: add shared chat-engine.js with all chat logic"
```

---

### Task 3: Create Obsidian theme

**Files:**
- Create: `friday_ai/static/themes/obsidian.html`

**Source files to reference:**
- Chat UI: `/home/sh4d0w/Downloads/stitch/friday_obsidian_chat_refined/code.html`
- Empty state: `/home/sh4d0w/Downloads/stitch/friday_ai_empty_state/code.html`
- Settings: `/home/sh4d0w/Downloads/stitch/friday_ai_settings_theme_switcher/code.html`

- [ ] **Step 1: Create obsidian.html from stitch source**

Copy the refined chat HTML from stitch as the base:
```bash
cp /home/sh4d0w/Downloads/stitch/friday_obsidian_chat_refined/code.html friday_ai/static/themes/obsidian.html
```

- [ ] **Step 2: Add standardized IDs to existing elements**

Open `friday_ai/static/themes/obsidian.html` and add IDs to these existing elements (find them by their classes/structure — do NOT change any classes or styling):

1. The `<aside>` sidebar element → add `id="sidebar"`
2. The scrollable message container `<section class="flex-1 overflow-y-auto ...">` → add `id="chatArea"`
3. The text input `<input class="w-full bg-transparent ...">` → add `id="messageInput"`
4. The send button (the one with the arrow icon inside the input bar) → add `id="sendBtn"`

- [ ] **Step 3: Add conversation list container to sidebar**

In the sidebar `<aside>`, find the section that has the "CURATION HISTORY" heading and the list of conversation items below it. Replace the hardcoded conversation items with:

```html
<div id="conversationList" class="flex-1 overflow-y-auto space-y-2 px-5">
  <!-- Populated by chat-engine.js -->
</div>
```

Add a "New Session" button at the top of the sidebar (near the logo area) with:
```html
<button id="newConvoBtn" class="w-full flex items-center gap-3 px-5 py-3 rounded-2xl bg-primary/10 text-primary text-sm font-medium hover:bg-primary/15 transition-colors">
  <span class="material-symbols-outlined" style="font-size:18px;">add</span>
  New Session
</button>
```

- [ ] **Step 4: Add settings button, panel, and overlay**

Add a settings button to the header area (near the existing icon buttons):
```html
<button id="settingsBtn" class="p-2.5 rounded-xl hover:bg-white/5 transition-colors">
  <span class="material-symbols-outlined">settings</span>
</button>
```

Before the closing `</body>`, add the settings overlay and panel. Use the styling from the Obsidian settings theme switcher stitch file (`friday_ai_settings_theme_switcher/code.html`):

```html
<!-- Settings Overlay -->
<div id="settingsOverlay" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-[90]"></div>

<!-- Settings Panel -->
<div id="settingsPanel" class="hidden fixed top-0 right-0 h-full w-full max-w-[440px] bg-surface-container-low/95 backdrop-blur-xl border-l border-white/5 z-[100] flex flex-col overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-8 py-6 border-b border-white/5">
    <h2 class="text-lg font-semibold text-on-surface">Settings</h2>
    <button onclick="window.fridayToggleSettings()" class="p-2 rounded-xl hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined">close</span>
    </button>
  </div>
  <!-- Scrollable content -->
  <div class="flex-1 overflow-y-auto px-8 py-6 space-y-8">
    <!-- Theme Switcher -->
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-primary" style="font-size:20px;">palette</span>
        <span class="text-sm font-medium text-on-surface">Theme</span>
      </div>
      <div id="themeSelect"></div>
    </div>
    <!-- Providers -->
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-primary" style="font-size:20px;">dns</span>
        <span class="text-sm font-medium text-on-surface">Providers</span>
      </div>
      <div id="settingsProviders"></div>
    </div>
    <!-- MCP Servers -->
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-primary" style="font-size:20px;">hub</span>
        <span class="text-sm font-medium text-on-surface">MCP Servers</span>
      </div>
      <div id="settingsMCP"></div>
    </div>
    <!-- Tools -->
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-primary" style="font-size:20px;">build</span>
        <span class="text-sm font-medium text-on-surface">Tools</span>
      </div>
      <div id="settingsTools"></div>
    </div>
    <!-- Memory -->
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="material-symbols-outlined text-primary" style="font-size:20px;">psychology</span>
        <span class="text-sm font-medium text-on-surface">Memory</span>
      </div>
      <div id="settingsMemory"></div>
      <button onclick="window.fridayClearMemory()" class="mt-3 text-xs text-error hover:text-error/80 transition-colors">Clear All Memory</button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Add empty state**

Add the empty state container inside the main content area, before or at the top of `#chatArea`. It should be hidden by default and shown by chat-engine.js when there are no messages:

```html
<div id="emptyState" class="hidden flex flex-col items-center justify-center min-h-[60vh] px-8 text-center">
  <div class="w-20 h-20 rounded-3xl bg-gradient-to-br from-primary to-primary-dim flex items-center justify-center mb-8 pulse-secondary">
    <span class="text-3xl font-bold text-on-primary">F</span>
  </div>
  <h2 class="text-2xl md:text-4xl font-bold text-on-surface mb-3">What can I help with?</h2>
  <p class="text-on-surface-variant/60 text-sm mb-10 max-w-md">I'm Friday, your AI system assistant.</p>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-w-3xl w-full">
    <button onclick="window.fridayQuickSend('Draft an email')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">mail</span>
      <div class="text-sm font-medium text-on-surface">Draft an email</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Compose professional messages</div>
    </button>
    <button onclick="window.fridayQuickSend('Explain this code')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">code</span>
      <div class="text-sm font-medium text-on-surface">Explain code</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Break down complex logic</div>
    </button>
    <button onclick="window.fridayQuickSend('Analyze this data')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">analytics</span>
      <div class="text-sm font-medium text-on-surface">Analyze data</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Insights and visualization</div>
    </button>
    <button onclick="window.fridayQuickSend('Summarize this text')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">summarize</span>
      <div class="text-sm font-medium text-on-surface">Summarize text</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Condense long content</div>
    </button>
    <button onclick="window.fridayQuickSend('Help me brainstorm')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">lightbulb</span>
      <div class="text-sm font-medium text-on-surface">Brainstorm</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Generate fresh ideas</div>
    </button>
    <button onclick="window.fridayQuickSend('Run a system command')" class="glass border border-white/5 rounded-2xl p-4 text-left hover:bg-white/5 transition-colors">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:20px;">terminal</span>
      <div class="text-sm font-medium text-on-surface">Run command</div>
      <div class="text-xs text-on-surface-variant/50 mt-1">Execute system tasks</div>
    </button>
  </div>
</div>
```

- [ ] **Step 6: Add mode buttons**

Add mode toggle buttons near the input area (below or beside the input bar):

```html
<div class="flex items-center gap-2 justify-center mt-3">
  <button id="modeChat" class="px-3 py-1.5 rounded-xl text-[11px] font-medium bg-primary/10 text-primary border border-primary/20 transition-all">Chat</button>
  <button id="modeCommand" class="px-3 py-1.5 rounded-xl text-[11px] font-medium text-on-surface-variant/50 hover:bg-white/5 transition-all">Command</button>
  <button id="modeSearch" class="px-3 py-1.5 rounded-xl text-[11px] font-medium text-on-surface-variant/50 hover:bg-white/5 transition-all">Search</button>
</div>
```

Add CSS for `.active` mode button state in the `<style>` block:
```css
.active { background: rgba(186, 158, 255, 0.1); color: #ba9eff; border-color: rgba(186, 158, 255, 0.2); }
```

- [ ] **Step 7: Add message templates**

Before the closing `</body>`, add template tags for message bubbles. These use the exact Obsidian bubble styling from the stitch source:

```html
<template id="tplUserBubble">
  <div class="flex flex-col items-end space-y-2 mb-8">
    <div class="max-w-[85%] md:max-w-[65%] p-6 rounded-[28px] rounded-tr-[4px] user-glass border border-primary/20 text-on-surface">
      <div class="text-sm font-light leading-relaxed">{CONTENT}</div>
    </div>
    <div class="text-[10px] text-on-surface-variant/30 font-mono px-2">{TIME}</div>
  </div>
</template>

<template id="tplFridayBubble">
  <div class="flex gap-5 items-start mb-8 max-w-[90%] md:max-w-[85%]">
    <div class="relative flex-shrink-0">
      <div class="w-10 h-10 rounded-2xl bg-surface-container-high flex items-center justify-center border border-white/10">
        <span class="text-primary font-bold text-sm">F</span>
      </div>
      <div class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-primary rounded-full border-2 border-surface"></div>
    </div>
    <div class="flex-1">
      <div class="glass p-7 rounded-[28px] rounded-tl-[4px] border border-white/10">
        <div class="flex items-center gap-2 mb-4">
          <span class="px-2 py-0.5 bg-primary/10 text-primary text-[9px] font-mono rounded-md border border-primary/20">{PROVIDER}</span>
        </div>
        <div class="text-sm font-light leading-relaxed text-on-surface/90">{CONTENT}</div>
      </div>
      <div class="text-[10px] text-on-surface-variant/30 font-mono mt-2 px-2">{TIME}</div>
    </div>
  </div>
</template>
```

- [ ] **Step 8: Strip demo messages and add script tag**

Remove all hardcoded demo message bubbles from the chat area in the HTML (the sample user/AI conversation from stitch). Leave `#chatArea` empty.

Add at the bottom, before `</body>`:
```html
<script src="/static/chat-engine.js"></script>
```

Remove any existing `<script>` blocks that contain demo/sample JS from the stitch source (the stitch files are static demos with no JS logic).

- [ ] **Step 9: Add conversation list styling**

Add to the `<style>` block:
```css
.convo-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: 12px; cursor: pointer; transition: background 0.2s;
}
.convo-item:hover { background: rgba(255,255,255,0.03); }
.convo-item.active { background: rgba(186, 158, 255, 0.08); }
.convo-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.convo-delete { opacity: 0; background: none; border: none; color: #ff6e84; cursor: pointer; padding: 4px; transition: opacity 0.2s; }
.convo-item:hover .convo-delete { opacity: 1; }
```

- [ ] **Step 10: Verify and commit**

Open in browser: `http://localhost:65535` → should redirect to `/static/themes/obsidian.html`.

```bash
git add friday_ai/static/themes/obsidian.html
git commit -m "feat: add Obsidian theme with full stitch fidelity"
```

---

### Task 4: Create Techno theme

**Files:**
- Create: `friday_ai/static/themes/techno.html`

**Source files to reference:**
- Chat UI: `/home/sh4d0w/Downloads/stitch/friday_techno_chat_refined/code.html`
- Empty state: `/home/sh4d0w/Downloads/stitch/friday_techno_empty_state/code.html`
- Settings: `/home/sh4d0w/Downloads/stitch/friday_techno_settings_theme_switcher/code.html`

- [ ] **Step 1: Create techno.html from stitch source**

```bash
cp /home/sh4d0w/Downloads/stitch/friday_techno_chat_refined/code.html friday_ai/static/themes/techno.html
```

- [ ] **Step 2: Add standardized IDs**

Find these existing elements and add IDs (do NOT change classes or styling):

1. The main scrollable area `<main class="flex-1 mt-10 mb-16 overflow-y-auto ...">` → add `id="chatArea"`
2. The input `<input class="flex-1 bg-transparent ... placeholder:text-secondary/20 ...">` → add `id="messageInput"`
3. The send button `<button class="bg-secondary/10 ... text-[9px] ... ">SEND_</button>` → add `id="sendBtn"`

No sidebar for Techno.

- [ ] **Step 3: Add settings button to header**

In the header bar, add a settings button next to existing header icons:

```html
<button id="settingsBtn" class="text-secondary/40 hover:text-secondary terminal-border px-2 py-0.5 text-[9px] tracking-widest uppercase transition-all">
  CONFIG_
</button>
```

- [ ] **Step 4: Add settings panel and overlay**

Before `</body>`, add the Techno-styled settings panel:

```html
<div id="settingsOverlay" class="hidden fixed inset-0 bg-black/80 z-[90]"></div>

<div id="settingsPanel" class="hidden fixed top-0 right-0 h-full w-[420px] bg-[#0a0a0d] border-l-[0.5px] border-secondary/20 z-[100] flex flex-col shadow-[-20px_0_80px_rgba(0,0,0,0.95)]">
  <div class="flex items-center justify-between px-4 py-2 border-b-[0.5px] border-secondary/20">
    <span class="text-[10px] font-label tracking-widest text-secondary uppercase">SYSTEM_CONFIG</span>
    <button onclick="window.fridayToggleSettings()" class="text-on-surface-variant/40 hover:text-secondary text-[9px] tracking-widest uppercase">CLOSE_</button>
  </div>
  <div class="flex-1 overflow-y-auto p-4 space-y-6" style="scrollbar-width:thin; scrollbar-color:#1a1a20 #0a0a0d;">
    <div>
      <div class="text-[9px] text-secondary/60 tracking-widest uppercase mb-3">THEME_SELECT</div>
      <div id="themeSelect"></div>
    </div>
    <div>
      <div class="text-[9px] text-secondary/60 tracking-widest uppercase mb-3">PROVIDER_STATUS</div>
      <div id="settingsProviders"></div>
    </div>
    <div>
      <div class="text-[9px] text-secondary/60 tracking-widest uppercase mb-3">MCP_SERVERS</div>
      <div id="settingsMCP"></div>
    </div>
    <div>
      <div class="text-[9px] text-secondary/60 tracking-widest uppercase mb-3">LOADED_TOOLS</div>
      <div id="settingsTools"></div>
    </div>
    <div>
      <div class="text-[9px] text-secondary/60 tracking-widest uppercase mb-3">MEMORY_BANK</div>
      <div id="settingsMemory"></div>
      <button onclick="window.fridayClearMemory()" class="mt-3 text-[9px] text-error/60 hover:text-error tracking-widest uppercase">PURGE_MEMORY_</button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Add empty state**

Add inside the main content area (within or before `#chatArea`):

```html
<div id="emptyState" class="hidden flex flex-col items-center justify-center min-h-[60vh] px-8 text-center">
  <div class="terminal-border p-6 mb-8">
    <span class="text-4xl font-bold text-secondary font-label">F</span>
  </div>
  <div class="text-xs font-label tracking-[0.3em] text-secondary/80 uppercase mb-2">WHAT CAN I HELP WITH?</div>
  <div class="text-[9px] font-label tracking-widest text-on-surface-variant/30 uppercase mb-10">NEURAL INTERFACE // WAITING FOR INPUT</div>
  <div class="grid grid-cols-2 md:grid-cols-3 gap-2 max-w-2xl w-full">
    <button onclick="window.fridayQuickSend('Run a command')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">terminal</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">EXECUTE_CMD</div>
    </button>
    <button onclick="window.fridayQuickSend('Explain this code')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">code</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">ANALYZE_CODE</div>
    </button>
    <button onclick="window.fridayQuickSend('Search the web')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">search</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">WEB_SEARCH</div>
    </button>
    <button onclick="window.fridayQuickSend('Analyze data')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">analytics</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">DATA_ANALYSIS</div>
    </button>
    <button onclick="window.fridayQuickSend('Refactor this code')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">build</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">REFACTOR_CORE</div>
    </button>
    <button onclick="window.fridayQuickSend('Help with security')" class="terminal-border p-3 text-left hover:bg-secondary/5 transition-colors">
      <span class="material-symbols-outlined text-secondary mb-1" style="font-size:16px;">security</span>
      <div class="text-[9px] tracking-widest text-secondary/60 uppercase">SYS_PROTECT</div>
    </button>
  </div>
</div>
```

- [ ] **Step 6: Add mode buttons**

Add near the input bar:

```html
<div class="flex items-center gap-1 justify-center mt-2">
  <button id="modeChat" class="terminal-border px-3 py-1 text-[9px] tracking-widest text-secondary/60 uppercase transition-all">CHAT</button>
  <button id="modeCommand" class="terminal-border px-3 py-1 text-[9px] tracking-widest text-on-surface-variant/30 uppercase transition-all">COMMAND</button>
  <button id="modeSearch" class="terminal-border px-3 py-1 text-[9px] tracking-widest text-on-surface-variant/30 uppercase transition-all">SEARCH</button>
</div>
```

Add to `<style>`:
```css
button.active { background: rgba(74, 225, 118, 0.1); color: #4ae176; border-color: rgba(74, 225, 118, 0.4); }
```

- [ ] **Step 7: Add message templates**

Before `</body>`:

```html
<template id="tplUserBubble">
  <div class="flex justify-end mb-6">
    <div class="max-w-[90%] md:max-w-[75%] terminal-border bg-surface-container-lowest relative">
      <div class="terminal-header px-3 py-1 flex justify-between items-center">
        <span class="text-[9px] tracking-widest text-on-surface-variant/40 uppercase font-label">USER_INPUT</span>
        <span class="text-[8px] text-on-surface-variant/20 font-label">{TIME}</span>
      </div>
      <div class="p-4 text-xs font-body leading-relaxed text-on-surface/90">{CONTENT}</div>
    </div>
  </div>
</template>

<template id="tplFridayBubble">
  <div class="flex gap-4 items-start mb-6">
    <div class="flex-shrink-0 w-8 h-8 terminal-border bg-secondary/5 flex items-center justify-center">
      <span class="text-secondary text-xs font-bold font-label">F</span>
    </div>
    <div class="flex-1 max-w-[90%] md:max-w-[85%] terminal-border bg-surface-container-high/40 relative">
      <div class="terminal-header px-3 py-1 flex justify-between items-center">
        <div class="flex items-center gap-2">
          <span class="text-[9px] tracking-widest text-secondary uppercase font-label">FRIDAY_CORE</span>
          <span class="text-[8px] bg-secondary/10 text-secondary px-1.5 py-0.5 terminal-border">{PROVIDER}</span>
        </div>
        <span class="text-[8px] text-on-surface-variant/20 font-label">{TIME}</span>
      </div>
      <div class="p-4 text-xs font-body leading-relaxed text-on-surface/80">{CONTENT}</div>
    </div>
  </div>
</template>
```

- [ ] **Step 8: Strip demo messages and add script tag**

Remove all hardcoded demo conversation from the chat area. Leave `#chatArea` empty.

Add before `</body>`:
```html
<script src="/static/chat-engine.js"></script>
```

- [ ] **Step 9: Verify and commit**

Switch theme: set `localStorage.setItem('friday_theme', 'techno')` and reload.

```bash
git add friday_ai/static/themes/techno.html
git commit -m "feat: add Techno theme with terminal aesthetic from stitch"
```

---

### Task 5: Create Neural theme

**Files:**
- Create: `friday_ai/static/themes/neural.html`

**Source files to reference:**
- Chat UI: `/home/sh4d0w/Downloads/stitch/friday_neural_chat_refined/code.html`
- Empty state: `/home/sh4d0w/Downloads/stitch/friday_neural_empty_state/code.html`
- Settings: `/home/sh4d0w/Downloads/stitch/friday_neural_settings_theme_switcher/code.html`

- [ ] **Step 1: Create neural.html from stitch source**

```bash
cp /home/sh4d0w/Downloads/stitch/friday_neural_chat_refined/code.html friday_ai/static/themes/neural.html
```

- [ ] **Step 2: Add standardized IDs**

1. The chat canvas `<div class="flex-1 w-full max-w-4xl px-8 overflow-y-auto scrollbar-hide ...">` → add `id="chatArea"`
2. The input `<input class="flex-1 bg-transparent ... placeholder:text-primary/30 ...">` → add `id="messageInput"`
3. The send button (the `touch-button` with arrow icon) → add `id="sendBtn"`

- [ ] **Step 3: Add settings button to header**

In the header, add:

```html
<button id="settingsBtn" class="touch-button p-2 text-primary/60">
  <span class="material-symbols-outlined" style="font-size:20px;">settings</span>
</button>
```

- [ ] **Step 4: Add settings panel and overlay**

Before `</body>`:

```html
<div id="settingsOverlay" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-[90]"></div>

<div id="settingsPanel" class="hidden fixed top-0 right-0 h-full w-full max-w-[440px] z-[100] flex flex-col overflow-hidden" style="background:rgba(13,17,23,0.95); backdrop-filter:blur(20px); border-left:1px solid rgba(105,218,255,0.15);">
  <div class="flex items-center justify-between px-6 py-5 border-b border-primary/10">
    <span class="text-sm font-headline tracking-widest uppercase text-primary">SYSTEM_CONFIG</span>
    <button onclick="window.fridayToggleSettings()" class="touch-button p-1.5 text-primary/60">
      <span class="material-symbols-outlined" style="font-size:18px;">close</span>
    </button>
  </div>
  <div class="flex-1 overflow-y-auto scrollbar-hide p-6 space-y-8">
    <div>
      <div class="text-[10px] font-mono tracking-widest uppercase text-primary/50 mb-3">VISUAL_PROTOCOL</div>
      <div id="themeSelect"></div>
    </div>
    <div>
      <div class="text-[10px] font-mono tracking-widest uppercase text-primary/50 mb-3">PROVIDER_NODES</div>
      <div id="settingsProviders"></div>
    </div>
    <div>
      <div class="text-[10px] font-mono tracking-widest uppercase text-primary/50 mb-3">MCP_NETWORK</div>
      <div id="settingsMCP"></div>
    </div>
    <div>
      <div class="text-[10px] font-mono tracking-widest uppercase text-primary/50 mb-3">TOOL_MODULES</div>
      <div id="settingsTools"></div>
    </div>
    <div>
      <div class="text-[10px] font-mono tracking-widest uppercase text-primary/50 mb-3">MEMORY_CORE</div>
      <div id="settingsMemory"></div>
      <button onclick="window.fridayClearMemory()" class="mt-3 touch-button px-3 py-1 text-[9px] font-mono tracking-widest uppercase text-error/60">PURGE_MEMORY</button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Add empty state**

```html
<div id="emptyState" class="hidden flex flex-col items-center justify-center min-h-[60vh] px-8 text-center">
  <div class="hex-clip w-24 h-24 bg-primary/10 flex items-center justify-center mb-8 glow-surface">
    <span class="text-3xl font-headline font-bold text-primary">F</span>
  </div>
  <div class="text-xs font-mono tracking-[0.3em] uppercase text-primary/80 mb-2">SYSTEM_READY: WHAT_CAN_I_HELP_WITH?</div>
  <div class="w-16 h-[1px] bg-primary/20 my-6"></div>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-3 max-w-3xl w-full">
    <button onclick="window.fridayQuickSend('Refactor this code')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">code_blocks</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">REFACTOR_CORE</div>
    </button>
    <button onclick="window.fridayQuickSend('Analyze data')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">analytics</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">DATA_ANALYSIS</div>
    </button>
    <button onclick="window.fridayQuickSend('Search the web')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">hub</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">LOGIC_BRIDGE</div>
    </button>
    <button onclick="window.fridayQuickSend('Check security')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">security</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">SECURE_TUNNEL</div>
    </button>
    <button onclick="window.fridayQuickSend('Help me think')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">neurology</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">SYNAPSE_LINK</div>
    </button>
    <button onclick="window.fridayQuickSend('Run a command')" class="angular-panel p-4 text-left hover:border-primary/40 transition-all">
      <span class="material-symbols-outlined text-primary mb-2" style="font-size:18px;">terminal</span>
      <div class="text-[9px] font-mono tracking-widest text-primary/50 uppercase">KERNEL_EXECUTE</div>
    </button>
  </div>
</div>
```

- [ ] **Step 6: Add mode buttons**

```html
<div class="flex items-center gap-2 justify-center mt-4">
  <button id="modeChat" class="touch-button px-4 py-1.5 text-[9px] font-mono tracking-widest uppercase text-primary">NODES</button>
  <button id="modeCommand" class="touch-button px-4 py-1.5 text-[9px] font-mono tracking-widest uppercase text-primary/30">FLOW</button>
  <button id="modeSearch" class="touch-button px-4 py-1.5 text-[9px] font-mono tracking-widest uppercase text-primary/30">QUERY</button>
</div>
```

Add to `<style>`:
```css
button.active { background: rgba(0, 207, 252, 0.15); border-color: rgba(0, 207, 252, 0.5); color: #69daff; box-shadow: 0 0 10px rgba(0, 207, 252, 0.2); }
```

- [ ] **Step 7: Add message templates**

```html
<template id="tplUserBubble">
  <div class="flex justify-end mb-8">
    <div class="max-w-[75%] p-6 relative" style="clip-path:polygon(5% 0,100% 0,100% 85%,95% 100%,0 100%,0 15%); background:rgba(105,218,255,0.05); border:1px solid rgba(105,218,255,0.15);">
      <div class="flex items-center justify-between mb-3">
        <span class="text-[9px] font-mono tracking-widest text-primary/40 uppercase">ADMIN_ROOT</span>
        <span class="text-[8px] font-mono text-primary/20">{TIME}</span>
      </div>
      <div class="text-sm font-body leading-relaxed text-on-surface/90">{CONTENT}</div>
    </div>
  </div>
</template>

<template id="tplFridayBubble">
  <div class="flex gap-5 items-start mb-8">
    <div class="flex-shrink-0 hex-clip w-10 h-10 bg-primary/10 flex items-center justify-center">
      <span class="text-primary font-bold text-sm">F</span>
    </div>
    <div class="flex-1 max-w-[85%]">
      <div class="angular-panel p-6">
        <div class="flex items-center gap-3 mb-4">
          <span class="text-[9px] font-mono tracking-widest text-primary uppercase">FRIDAY_CORE.V4</span>
          <span class="text-[8px] bg-primary/10 text-primary px-1.5 py-0.5 font-mono border border-primary/20">{PROVIDER}</span>
        </div>
        <div class="text-sm font-body leading-relaxed text-on-surface/85">{CONTENT}</div>
      </div>
      <div class="text-[8px] font-mono text-primary/20 mt-2 px-2">{TIME}</div>
    </div>
  </div>
</template>
```

- [ ] **Step 8: Strip demo messages and add script tag**

Remove hardcoded demo content from chat area. Add before `</body>`:
```html
<script src="/static/chat-engine.js"></script>
```

- [ ] **Step 9: Verify and commit**

```bash
git add friday_ai/static/themes/neural.html
git commit -m "feat: add Neural theme with HUD aesthetic from stitch"
```

---

### Task 6: Create Prism theme

**Files:**
- Create: `friday_ai/static/themes/prism.html`

**Source files to reference:**
- Chat UI: `/home/sh4d0w/Downloads/stitch/friday_prism_chat_refined/code.html`
- Empty state: `/home/sh4d0w/Downloads/stitch/friday_prism_empty_state/code.html`

- [ ] **Step 1: Create prism.html from stitch source**

```bash
cp /home/sh4d0w/Downloads/stitch/friday_prism_chat_refined/code.html friday_ai/static/themes/prism.html
```

- [ ] **Step 2: Add standardized IDs**

1. The main scrollable area `<main class="h-screen w-full pt-12 pb-32 overflow-y-auto">` → add `id="chatArea"`
2. The input `<input class="w-full bg-transparent ... placeholder:text-neutral-800 uppercase">` → add `id="messageInput"`
3. The send/execute button `<button class="bg-red-600 text-black ... glitch-hover ...">EXECUTE</button>` → add `id="sendBtn"`

- [ ] **Step 3: Add settings button to header**

In the header bar:

```html
<button id="settingsBtn" class="text-neutral-600 hover:text-red-600 text-[9px] font-bold uppercase tracking-widest transition-colors">
  CONFIG
</button>
```

- [ ] **Step 4: Add settings panel and overlay**

```html
<div id="settingsOverlay" class="hidden fixed inset-0 bg-black/90 z-[90]"></div>

<div id="settingsPanel" class="hidden fixed top-0 right-0 h-full w-[400px] bg-black border-l-2 border-red-600 z-[100] flex flex-col shadow-[-20px_0_60px_rgba(255,26,26,0.1)]">
  <div class="flex items-center justify-between px-4 py-3 border-b-2 border-red-600">
    <span class="text-[10px] font-bold tracking-widest text-red-600 uppercase">SYSTEM_CONFIG</span>
    <button onclick="window.fridayToggleSettings()" class="text-neutral-600 hover:text-red-600 text-[9px] font-bold uppercase tracking-widest glitch-hover">CLOSE</button>
  </div>
  <div class="flex-1 overflow-y-auto p-4 space-y-6">
    <div>
      <div class="text-[9px] text-red-600/60 tracking-widest uppercase font-bold mb-3">THEME_PROTOCOL</div>
      <div id="themeSelect"></div>
    </div>
    <div>
      <div class="text-[9px] text-red-600/60 tracking-widest uppercase font-bold mb-3">PROVIDER_ARRAY</div>
      <div id="settingsProviders"></div>
    </div>
    <div>
      <div class="text-[9px] text-red-600/60 tracking-widest uppercase font-bold mb-3">MCP_UPLINKS</div>
      <div id="settingsMCP"></div>
    </div>
    <div>
      <div class="text-[9px] text-red-600/60 tracking-widest uppercase font-bold mb-3">TOOL_REGISTRY</div>
      <div id="settingsTools"></div>
    </div>
    <div>
      <div class="text-[9px] text-red-600/60 tracking-widest uppercase font-bold mb-3">MEMORY_BANK</div>
      <div id="settingsMemory"></div>
      <button onclick="window.fridayClearMemory()" class="mt-3 text-[9px] text-red-600/40 hover:text-red-600 font-bold uppercase tracking-widest">PURGE_ALL</button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Add empty state**

```html
<div id="emptyState" class="hidden flex flex-col items-center justify-center min-h-[60vh] px-8 text-center kinetic-bg">
  <div class="text-7xl font-bold text-red-600 mb-2 font-headline" style="text-shadow: 0 0 30px rgba(255,26,26,0.3);">F</div>
  <div class="text-xs font-bold tracking-[0.3em] text-white/80 uppercase mb-1">WHAT CAN I HELP WITH?</div>
  <div class="text-[9px] font-mono tracking-widest text-neutral-700 uppercase mb-10">SYSTEM_STATE: READY // V.04</div>
  <div class="flex flex-wrap gap-2 justify-center max-w-2xl">
    <button onclick="window.fridayQuickSend('Analyze patterns')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">psychology</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">NEURAL_LINK</span>
    </button>
    <button onclick="window.fridayQuickSend('Find files')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">folder_open</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">FILESYSTEM</span>
    </button>
    <button onclick="window.fridayQuickSend('Trace network')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">hub</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">NETWORK_MAP</span>
    </button>
    <button onclick="window.fridayQuickSend('Generate key')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">vpn_key</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">CRYPT_KEY</span>
    </button>
    <button onclick="window.fridayQuickSend('Check logs')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">terminal</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">SYSTEM_LOGS</span>
    </button>
    <button onclick="window.fridayQuickSend('Run a command')" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-2 text-left hover:border-red-600 transition-colors flex items-center gap-3">
      <span class="material-symbols-outlined text-red-600" style="font-size:16px;">bolt</span>
      <span class="text-[9px] font-bold tracking-widest text-neutral-500 uppercase">KINETIC</span>
    </button>
  </div>
</div>
```

- [ ] **Step 6: Add mode buttons**

```html
<div class="flex items-center gap-1 justify-center mt-3">
  <button id="modeChat" class="shard-rect bg-red-600/10 border border-red-600/30 px-4 py-1 text-[9px] font-bold tracking-widest text-red-600 uppercase">CHAT</button>
  <button id="modeCommand" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-1 text-[9px] font-bold tracking-widest text-neutral-600 uppercase">COMMAND</button>
  <button id="modeSearch" class="shard-rect bg-neutral-950 border border-neutral-800 px-4 py-1 text-[9px] font-bold tracking-widest text-neutral-600 uppercase">SEARCH</button>
</div>
```

Add to `<style>`:
```css
button.active { background: rgba(255, 26, 26, 0.1); border-color: rgba(255, 26, 26, 0.4); color: #ff1a1a; }
```

- [ ] **Step 7: Add message templates**

```html
<template id="tplUserBubble">
  <div class="flex justify-end mb-6 px-4 md:px-24">
    <div class="flex flex-col gap-1 max-w-2xl items-end">
      <div class="flex items-center gap-2 px-1">
        <span class="text-[8px] font-mono text-neutral-700">{TIME}</span>
        <span class="text-[9px] border border-neutral-700 px-1 font-bold">ROOT</span>
      </div>
      <div class="bg-white text-black shard-right p-5">
        <div class="text-sm font-body leading-relaxed">{CONTENT}</div>
      </div>
    </div>
  </div>
</template>

<template id="tplFridayBubble">
  <div class="flex mb-6 px-4 md:px-24">
    <div class="flex flex-col gap-1 max-w-2xl">
      <div class="flex items-center gap-2 px-1">
        <span class="text-[9px] bg-red-600 text-black px-1 font-bold">PRISM_04</span>
        <span class="text-[8px] bg-neutral-900 text-neutral-500 px-1 font-mono">{PROVIDER}</span>
        <span class="text-[8px] font-mono text-neutral-700">{TIME}</span>
      </div>
      <div class="bg-neutral-900 shard-left p-5 border-l-4 border-red-600">
        <div class="text-sm font-body leading-relaxed text-neutral-300">{CONTENT}</div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 8: Strip demo messages and add script tag**

Remove demo content. Add before `</body>`:
```html
<script src="/static/chat-engine.js"></script>
```

- [ ] **Step 9: Verify and commit**

```bash
git add friday_ai/static/themes/prism.html
git commit -m "feat: add Prism theme with kinetic stealth aesthetic from stitch"
```

---

### Task 7: Integration testing and cleanup

**Files:**
- Verify: all files in `friday_ai/static/` and `friday_ai/static/themes/`

- [ ] **Step 1: Verify existing Python tests still pass**

```bash
cd /home/sh4d0w/Projects/friday
python -m pytest tests/ -v --tb=short
```

Expected: 279 tests pass. No backend changes were made, so this should be clean.

- [ ] **Step 2: Start the Friday server**

```bash
cd /home/sh4d0w/Projects/friday
python -m friday_ai.server &
```

- [ ] **Step 3: Test index.html loader**

Open `http://localhost:65535` in browser. Should redirect to `/static/themes/obsidian.html` (default theme).

Verify:
- Page loads with Obsidian theme (dark purple, glassmorphism, sidebar)
- Empty state shows with quick actions
- No JS console errors

- [ ] **Step 4: Test chat functionality on Obsidian**

1. Type a message and send → message appears in user bubble with Obsidian styling
2. Response appears in AI bubble with provider badge
3. Markdown works: send "test `inline code` and **bold**" → verify rendering
4. Conversation appears in sidebar
5. Create new conversation → empty state shows
6. Switch between conversations

- [ ] **Step 5: Test theme switching**

1. Click settings button → settings panel slides out
2. Verify providers, MCP, tools, memory sections load
3. Click "Techno" in theme select → page reloads to Techno theme
4. Verify Techno loads with green terminal aesthetic, scanlines
5. Send a message → verify terminal-styled bubbles
6. Switch to Neural → verify cyan HUD, angular panels
7. Switch to Prism → verify red kinetic, shard clip-paths
8. Switch back to Obsidian → verify conversation history preserved

- [ ] **Step 6: Test each theme's visual fidelity**

For each theme, compare against stitch screenshots:
- Obsidian: `Downloads/stitch/friday_obsidian_chat_refined/screen.png`
- Techno: `Downloads/stitch/friday_techno_chat_refined/screen.png`
- Neural: `Downloads/stitch/friday_neural_chat_refined/screen.png`
- Prism: `Downloads/stitch/friday_prism_chat_refined/screen.png`

Check: colors, fonts, borders, animations, clip-paths, glassmorphism, scrollbars all match.

- [ ] **Step 7: Test pywebview compatibility**

```bash
cd /home/sh4d0w/Projects/friday
python bin/friday-window.py
```

Press Super+F to open the floating window. Verify:
- Theme loads correctly in webview
- Chat works
- Settings panel works
- No localStorage crash (safeStorage wrapper handles it)

- [ ] **Step 8: Clean up and final commit**

Remove the Gemini backup if no longer needed, add `.superpowers/` to `.gitignore`:

```bash
echo ".superpowers/" >> .gitignore
git add .gitignore
git add friday_ai/static/
git commit -m "feat: complete theme system — 4 themes with live switching"
```

- [ ] **Step 9: Stop the server**

```bash
kill %1
```
