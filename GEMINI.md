# Friday — AI System Assistant

## Your Task: Redesign the Browser Chat UI

The file to edit: `friday_ai/static/index.html` (single HTML file, embedded CSS+JS)

The backend API runs at `http://127.0.0.1:65535`. All endpoints are already working.

## API Reference

```
GET  /health              → {"status": "online", "providers": ["ollama", "claude-cli", ...]}
POST /chat                → body: {"message": "...", "force_provider": "...", "race": true}
                            → {"response": "...", "provider": "ollama"}
POST /classify            → body: {"message": "..."}
                            → {"intent": "system|complex|search|chat|dangerous|unknown"}
GET  /context             → {"context": "...system prompt and history..."}
POST /reload              → {"reloaded": 19, "tools": ["run_shell", "memory_save", ...]}
POST /memory/list         → {"entries": ["user uses Cosmic DE", "user has GTX 1650"]}
POST /memory/forget       → query: keyword → {"status": "ok", "forgot": "..."}
POST /memory/clear        → {"status": "cleared"}
POST /session/save        → {"status": "saved"}
POST /session/load        → {"status": "loaded"}
GET  /mcp/status          → {"servers": [...], "tools": [...]}
POST /mcp/reconnect       → {"connected": [...]}
```

## Design Requirements

Build a **premium, polished** chat interface. The user wants the best features from ChatGPT, Claude, Gemini, and Discord combined. This is a portfolio project — it needs to look impressive.

### Must-have features

**Layout:**
- Left sidebar (collapsible) with:
  - Friday branding/logo
  - "New chat" button
  - Conversation history (stored in localStorage)
  - Delete conversation button
- Main chat area with message bubbles
- Bottom input bar

**Chat messages:**
- User messages: right-aligned, subtle accent border
- Friday messages: left-aligned, with avatar (purple "F"), provider tag (OLLAMA, CLAUDE-CLI, etc.), timestamp
- Animated typing indicator (bouncing dots) while waiting
- Full markdown rendering:
  - Code blocks with syntax highlighting AND copy button
  - Bold, italic, strikethrough
  - Headers (h1-h3)
  - Bullet/numbered lists
  - Blockquotes
  - Horizontal rules
  - Links
  - Tables
- Empty state with logo, tagline, and 6 quick-action buttons

**Input area:**
- Mode switcher: 3 pill buttons (Chat | Command | Search)
  - Chat: normal message
  - Command: adds context hint for tool use
  - Search: adds "search " prefix
- Auto-resizing textarea
- Send button with icon
- Keyboard hints: Enter=send, Shift+Enter=newline, Ctrl+L=clear

**Settings panel (slide-out from right or modal):**
- Show current config values (model, provider_mode, port)
- Toggle MCP servers on/off (call /mcp/reconnect after changes)
- Show memory entries (call /memory/list)
- Show tool list (call /reload)
- Provider status with health dots

**Conversation management:**
- Store in localStorage: {id, title, messages[], createdAt}
- Title = first user message truncated to 30 chars
- Load conversation on click
- Delete with confirmation
- "New chat" clears current and starts fresh

### Visual Style

**Theme: Dark, premium, NOT flat/boring**

- Background: `#08080f` (very dark blue-black)
- Surfaces: glass effect — `rgba(255,255,255,0.03)` with `backdrop-filter: blur(20px)`
- Accent: animated purple gradient `linear-gradient(135deg, #8b5cf6, #6d28d9, #4f46e5)`
- Borders: `rgba(255,255,255,0.06)`
- Text primary: `#e8e8f0`
- Text secondary: `#6b6b8a`
- User bubble: `rgba(139, 92, 246, 0.08)` with purple border
- Friday bubble: `rgba(255,255,255,0.03)` glass
- Code blocks: `#0a0a14` with border, monospace font, copy button top-right
- Sidebar: slightly lighter surface with glass
- Animations: subtle `0.2s ease` transitions on everything
- Hover states on all interactive elements
- Purple glow (`box-shadow`) on accent elements
- Scrollbar: thin, matching theme

**Fonts:**
- Body: `Inter` from Google Fonts
- Code: `JetBrains Mono` from Google Fonts

**Inspirations:**
- ChatGPT's clean layout and sidebar
- Claude's elegant message styling and markdown
- Discord's dark theme compactness
- Vercel's glassmorphism aesthetic

### Technical constraints
- Single HTML file, all CSS+JS embedded
- No external JS libraries (vanilla JS only)
- Google Fonts for typography only
- Must work in Chrome, Firefox, and WebKit (pywebview)
- API calls to same origin (no CORS issues)
- Responsive: works at 480px wide (floating window) and full screen

### What NOT to do
- Don't use any JS framework (React, Vue, etc.)
- Don't add external dependencies
- Don't change any backend files
- Don't use light theme
- Don't make it look like a prototype or wireframe

## Testing

After editing index.html:
1. Start backend: `.venv/bin/uvicorn friday_ai.server:app --host 127.0.0.1 --port 65535`
2. Open `http://127.0.0.1:65535` in browser
3. Test: send "hello", verify response appears with provider tag
4. Test: send "run whoami", verify tool calling works
5. Test: sidebar conversation save/load
6. Test: settings panel shows providers and tools
7. Test: code block rendering with copy button

## Project Context
- Arch Linux, Cosmic DE, GTK-based
- User: VIT student building this for portfolio + daily use
- The TUI version will be built separately by Claude Code
- This browser UI is the secondary interface
- Keep it impressive — this will be shown to interviewers
