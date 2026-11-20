---
name: windows-playwright-install
description: >-
  Install Playwright + Chromium for Python on a Windows machine where the default
  browser CDN is unreachable and the system is missing the standard VC++ 2015-2022
  runtime. Use this skill when: installing Playwright into a Python venv on Windows;
  `playwright install chromium` dies at 0% with no error; or importing a Python
  C extension (playwright/greenlet/Pillow/tencentcloud) fails with
  "ImportError: DLL load failed ... 找不到指定的模块". Encapsulates the npmmirror
  download-host workaround and the Edge-WebView VC++ runtime copy + .pth fix.
agent_created: true
---

# Windows Playwright + Chromium Install (blocked-CDN / missing-VC++-runtime edition)

This skill packages a non-obvious, repeatable procedure that fails in two specific
ways on locked-down Windows machines (e.g. the <本机> / managed-python environment):

1. `playwright install chromium` downloads 0% then exits 1 — the default CDN
   `cdn.playwright.dev` is unreachable at the network layer.
2. After install, `from playwright.sync_api import sync_playwright` fails with
   `ImportError: DLL load failed while importing _greenlet: 找不到指定的模块`
   because the system only has `_clr0400` VC++ runtime variants, not the standard
   `vcruntime140_1.dll` / `msvcp140.dll`.

## When to use

- Setting up Playwright (browser automation / screenshot collection) on Windows.
- Any Python C extension import fails with a "DLL load failed / 找不到指定的模块"
  error and the machine is missing standard VC++ 2015-2022 runtime DLLs.

## Procedure

### 1. Prepare the venv

If the managed venv directory exists but is an empty shell (no `Scripts/python.exe`),
rebuild it with the managed Python:

```
PY="~/.workbuddy/binaries/python/versions/3.13.12/python.exe"
VENV="~/.workbuddy/binaries/python/envs/default"
"$PY" -m venv "$VENV"
```

Then install Playwright (PyPI is normally reachable even inside the sandbox):

```
"$VENV/Scripts/python.exe" -m pip install playwright
```

### 2. Install the Chromium browser via the npmmirror host

The default `cdn.playwright.dev` may be unreachable. Switch to the China mirror:

```
set PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
"$VENV/Scripts/python.exe" -m playwright install chromium
```

- This downloads `chromium-<rev>`, `chromium_headless_shell-<rev>`, `ffmpeg-<rev>`,
  `winldd-<rev>` into `%LOCALAPPDATA%\ms-playwright`.
- If the sandbox blocks the download, re-run with the sandbox disabled (the
  download needs outbound network to the mirror). The trailing `__dirlock`
  "safe-delete / trash" error at the very end is harmless — the browser files are
  already on disk.
- Verify the browser files exist before troubleshooting launch.

### 3. Fix the missing VC++ runtime (DLL load failure)

When a Python C extension (greenlet/playwright, Pillow, tencentcloud) fails to
import due to a missing `vcruntime140_1.dll` / `msvcp140.dll`:

a. Locate a full 64-bit VC++ 2015-2022 runtime on the machine. A reliable source
   is the Edge WebView2 payload (definitely 64-bit because it lives in System32):

```
SRC="C:/Windows/System32/Microsoft-Edge-WebView"
```

b. Copy the whole runtime set into the venv's `Scripts` directory (highest priority
   in the DLL search path for the interpreter) **and** into the specific extension
   package directory that fails to import (CPython's extension-loader search does
   NOT reliably include `Scripts`, but DOES include the extension's own dir):

```
DST="~/.workbuddy/binaries/python/envs/default/Scripts"
cp "$SRC"/*.dll "$DST/"
cp "$SRC"/*.dll "~/.workbuddy/binaries/python/envs/default/Lib/site-packages/greenlet/"
```

   The set includes: `vcruntime140.dll`, `vcruntime140_1.dll`, `msvcp140.dll`,
   `msvcp140_codecvt_ids.dll`, `concrt140.dll`, `vccorlib140.dll`.

c. Make the fix durable for ALL extensions in this venv by adding a `.pth` that
   registers the `Scripts` dir on the DLL search path (so future extensions like
   Pillow / tencentcloud also resolve the runtime without per-package copies):

```
# ~/.workbuddy/binaries/python/envs/default/Lib/site-packages/zzz_vcruntime.pth
import os; os.add_dll_directory(r"~/.workbuddy\binaries\python\envs\default\Scripts")
```

### 4. Verify

Run a headless launch + screenshot using the same API the collector uses
(`launch_persistent_context`):

```python
from playwright.sync_api import sync_playwright
import tempfile, os
ud = tempfile.mkdtemp()
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=ud, headless=True,
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.new_page()
    page.goto("data:text/html,<h1>ok</h1>")
    page.screenshot(path="C:/tmp/_pw_test.png")
    ctx.close()
print("LAUNCH_OK")
```

If `LAUNCH_OK` prints and the screenshot file is non-empty, the install is good.

## Notes / pitfalls

- Do NOT copy the `_clr0400` variants from `C:/Windows/System32` directly — those
  are .NET-CLR-specific and will not satisfy a normal C extension. Use the
  `Microsoft-Edge-WebView` subfolder (full runtime).
- The proper system-wide fix is installing the Visual C++ Redistributable for
  Visual Studio 2022 (x64), which places the DLLs in System32. The per-venv copy
  + `.pth` is a sufficient, non-invasive alternative that survives venv recreation
  only if re-applied (re-run step 3 after `python -m venv`).
- pip 26's "safe-delete" (recycle-bin) step fails closed in headless sessions
  (`windows-sandbox-recycle-bin-unavailable`). If `pip install` aborts on a
  partially-installed package, remove the residual package dir from
  `Lib/site-packages` and reinstall.
