# Friday AI Theme System — Design Spec

## Objective

Replace Gemini's broken single-file theme implementation with a proper multi-file architecture that faithfully reproduces all 4 premium themes from stitch.zip (Obsidian, Techno, Neural, Prism) with live switching and full chat functionality.

## Decisions

- All 4 themes implemented with full visual fidelity to stitch source files
- All existing features carried over: chat, conversations, markdown, settings, modes, theme switcher, empty state, keyboard shortcuts
- Separate theme HTML files + shared chat-engine.js
- Sidebar-less themes (Techno, Neural, Prism): conversations persist in localStorage but UI is single-session focused

## File Structure

```
friday_ai/static/
├── index.html              # Loader — reads localStorage, redirects to active theme
├── chat-engine.js          # Shared JS — chat logic, markdown, settings, conversations
└── themes/
    ├── obsidian.html       # Complete page: Tailwind config + CSS + HTML
    ├── techno.html         # Each includes <script src="/static/chat-engine.js">
    ├── neural.html
    └── prism.html
```

## Serving Flow

1. User hits `GET /` which serves `index.html`
2. `index.html` checks `localStorage.getItem('friday_theme')`, defaults to `obsidian`
3. Redirects to `/static/themes/{theme}.html`
4. Theme page loads with its own Tailwind config + CSS + HTML structure
5. `chat-engine.js` initializes, binds to standardized element IDs
6. Theme switch from settings saves preference and navigates to `/static/themes/{name}.html`

Backend change: none required — FastAPI's existing `StaticFiles` mount already serves subdirectories.

### pywebview compatibility
`index.html` loader and `chat-engine.js` both use a `safeStorage` wrapper around `localStorage` that returns fallback values when storage is unavailable (common in Linux webview environments). If localStorage is blocked, theme defaults to Obsidian and conversations are ephemeral (in-memory only for the session).

## Standardized Element IDs

Every theme HTML must provide these IDs for chat-engine.js binding.

### Required (all themes)

| ID | Purpose |
|----|---------|
| `#chatArea` | Scrollable message container |
| `#messageInput` | Textarea/input for typing |
| `#sendBtn` | Send button |
| `#settingsPanel` | Settings slide-out panel |
| `#settingsOverlay` | Backdrop overlay behind settings |
| `#settingsBtn` | Button that opens settings |
| `#emptyState` | Empty state container (shown when no messages) |
| `#modeChat` | Chat mode toggle button |
| `#modeCommand` | Command mode toggle button |
| `#modeSearch` | Search mode toggle button |
| `#settingsProviders` | Container for provider health data |
| `#settingsMCP` | Container for MCP server status |
| `#settingsTools` | Container for loaded tools |
| `#settingsMemory` | Container for memory entries |
| `#themeSelect` | Theme picker container |

### Optional (Obsidian only)

| ID | Purpose |
|----|---------|
| `#conversationList` | Sidebar conversation list |
| `#newConvoBtn` | New conversation button |
| `#sidebar` | The sidebar element |

chat-engine.js null-guards optional elements. If `#conversationList` doesn't exist, conversation switching is silently skipped in the UI but data persists in localStorage.

## Theme Implementation Strategy

### Source mapping

| Theme | Source file | Target |
|-------|-----------|--------|
| Obsidian | `stitch/friday_obsidian_chat_refined/code.html` | `themes/obsidian.html` |
| Techno | `stitch/friday_techno_chat_refined/code.html` | `themes/techno.html` |
| Neural | `stitch/friday_neural_chat_refined/code.html` | `themes/neural.html` |
| Prism | `stitch/friday_prism_chat_refined/code.html` | `themes/prism.html` |

### Additional source material per theme

- Settings panel: `friday_*_settings_theme_switcher/` designs
- Empty state: `friday_*_empty_state/` designs
- Design specs: `DESIGN.md` files in `friday_obsidian/`, `obsidian_command/`, `neural_ether/`, `prism_core/`

### Changes to each source file

1. Add standardized IDs to existing elements (no structural changes)
2. Strip hardcoded demo messages — chat-engine.js renders dynamically
3. Add settings panel section from theme's own settings design with standardized IDs
4. Add empty state from theme's empty state design
5. Add `<script src="/static/chat-engine.js"></script>` at the bottom
6. Add `<template id="tplUserBubble">` and `<template id="tplFridayBubble">` with theme-styled message markup containing `{CONTENT}`, `{TIME}`, `{PROVIDER}` slots

### Preserved from source (no changes)

- Tailwind config (colors, borderRadius, fontFamily)
- CSS animations (pulse, scanline, light trails, kinetic drift)
- Fonts (Inter, JetBrains Mono, Space Grotesk per theme)
- Clip-paths (angular panels, shard layouts)
- Glassmorphism / backdrop-blur
- All HTML structure and classes
- Material Symbols icons

## chat-engine.js Modules

### 1. Init
`DOMContentLoaded` listener discovers available elements, sets up event listeners, loads conversation from localStorage, checks `/health`.

### 2. Chat
`sendMessage()` posts to `/chat`, renders user bubble via template, shows thinking indicator, renders AI response with markdown. Prefixes message with `run ` or `search ` based on active mode.

### 3. Message Rendering
Uses `<template>` tags defined in each theme HTML:
- `<template id="tplUserBubble">` — theme-styled user message with `{CONTENT}` and `{TIME}` slots
- `<template id="tplFridayBubble">` — theme-styled AI message with `{CONTENT}`, `{TIME}`, `{PROVIDER}` slots
- chat-engine.js clones template, fills slots via string replacement, appends to `#chatArea`
- Each theme fully controls bubble appearance — no shared CSS, no generic markup

### 4. Markdown
`parseMarkdown(text)` handles:
- Code blocks with syntax highlighting + copy button
- Inline code
- Tables
- Headings (h1-h3), horizontal rules, blockquotes
- Bold, italic, strikethrough
- Links (target=_blank)
- Ordered and unordered lists

Outputs semantic HTML that inherits theme styles.

### 5. Conversations
CRUD operations on `localStorage` key `friday_conversations`:
- `newConversation()` — creates new entry, sets as active
- `loadConversation(id)` — renders stored messages
- `saveStorage()` — persists current state
- Obsidian: renders list in `#conversationList`
- Other themes: tracks `activeConvoId` silently, auto-creates on first message

### 6. Settings
`toggleSettings()` slides `#settingsPanel` in/out. Populates:
- `#settingsProviders` from `GET /health`
- `#settingsMCP` from `GET /mcp/status`
- `#settingsTools` from `POST /reload`
- `#settingsMemory` from `POST /memory/list`
- `#themeSelect` shows 4 theme options with active highlight

### 7. Modes
Tracks `currentMode` (chat/command/search). Highlights active mode button. Prefixes messages accordingly.

### 8. Keyboard
- Enter to send (Shift+Enter for newline)
- Ctrl+L to clear chat
- Textarea auto-resize on input

## Theme Switching

### Mechanism
1. User clicks theme option in `#themeSelect`
2. `applyTheme(name)` saves `friday_theme` to localStorage
3. Navigates to `/static/themes/{name}.html`
4. New page loads, chat-engine.js initializes, restores conversation from localStorage

### Persisted state (survives theme switch)
- `friday_conversations` — all conversation data
- `friday_theme` — active theme name
- `friday_active_convo` — which conversation was open

## What This Design Avoids (Gemini's mistakes)

- No compressing 4 themes into one file
- No JSON blob theme payloads
- No `{TEXT}` template tokens with regex replacement
- No shared/generic CSS across themes
- No `document.write()` or innerHTML-based page replacement
- No minification of theme HTML
- No loss of theme-specific animations, clip-paths, or visual identity
