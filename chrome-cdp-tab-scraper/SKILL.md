---
name: chrome-cdp-tab-scraper
description: >-
  Read and scrape the content of Chrome tabs the user currently has open on
  their local machine, by connecting to Chrome over the Chrome DevTools
  Protocol (CDP). Use this when a user asks to inspect, capture, or scrape
  web pages they already have open in their browser (e.g. "look at the sites I
  have open", "grab the page I'm viewing", "read my open tabs during a patrol
  task"). The bundled script is pure Python standard library — no playwright,
  no pip install — which matters because venv creation and `pip install
  --target` are broken in the managed WorkBuddy Python environment.
agent_created: true
---

# Chrome CDP Tab Scraper

Capture the live content of Chrome tabs the user already has open, by driving
their local Chrome through the DevTools Protocol. This does NOT launch a new
browser and does NOT see a separate Playwright profile — it attaches to the
user's actual running session, so it can read logged-in pages (Douyin,
hotspot tools, dashboards, etc.) exactly as the user sees them.

## When to use

- The user wants to read / scrape / archive pages they currently have open.
- A recurring task (e.g. a "hotspot patrol") should also ingest the user's open
  browser tabs, not just fetch fresh URLs.
- Avoid when the user only wants pages the agent opens itself — that is plain
  browser automation, not this skill.

## How to use

### 1. Enable the debug port on the user's Chrome

Chrome must be started with a remote debugging port. The cleanest way is a
launcher that closes the running Chrome and reopens it with the SAME
`--user-data-dir` plus `--remote-debugging-port=9222`, so the user's tabs and
logins are restored:

```
taskkill /F /IM chrome.exe
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\Users\<user>\AppData\Local\Google\Chrome\User Data"
```

Tell the user to save unsent form data first (the restart closes windows).
After this, `http://localhost:9222/json/list` returns all open targets.

### 2. List and scrape

Run the bundled `scripts/cdp_tab_scraper.py`:

```
python cdp_tab_scraper.py --list            # JSON list of open page tabs
python cdp_tab_scraper.py --scrape 0,2,5    # grab selected indices
python cdp_tab_scraper.py --scrape all       # grab every open tab
```

Scraped pages are saved as `<timestamp>_<index>_<title>.html` and `.txt` under
`001_chrome_capture/`. Each tab is read via CDP `Runtime.evaluate`
(`document.documentElement.outerHTML`, `document.body.innerText`, etc.) — the
already-rendered DOM, so SPA sites (Douyin, etc.) yield real text, though
lazy-loaded or anti-bot-gated sections may need targeted handling.

### 3. Privacy boundary

Once the debug port is open, anyone who can reach `localhost:9222` can read
EVERY open tab, including logged-in accounts and private content. Keep the
port open only while working, and tell the user to close it (exit Chrome or
restart without the flag) when done.

## Environment notes (non-obvious)

- In the managed WorkBuddy Python (`~/.workbuddy/binaries/python/...`),
  `python -m venv` reports success but creates an empty directory, and
  `pip install --target=...` does not persist files. Do NOT rely on playwright
  or any pip package here. The bundled script is intentionally **zero external
  dependencies** — it hand-rolls a minimal RFC6455 WebSocket client over
  `socket` to speak CDP. Run it with the plain managed `python.exe`.
- Use Windows-style paths (`C:/Users/...`) when passing file paths to the
  managed `python.exe` from Git Bash; leading `/c/...` paths get double-converted.

## Files

- `scripts/cdp_tab_scraper.py` — the reusable scraper (stdlib only).
