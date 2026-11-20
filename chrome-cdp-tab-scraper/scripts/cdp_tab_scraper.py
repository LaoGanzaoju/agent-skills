#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome CDP Tab Scraper (zero external dependencies)

Reads and scrapes the content of Chrome tabs the user currently has open, by
driving their local Chrome through the Chrome DevTools Protocol. No playwright,
no pip install — a minimal RFC6455 WebSocket client is hand-rolled over
`socket`, because venv creation and `pip install --target` are broken in the
managed WorkBuddy Python environment.

Prereq: Chrome must be started with a remote debugging port, e.g.
  chrome.exe --remote-debugging-port=9222 --user-data-dir="<User Data path>"

Usage:
  python cdp_tab_scraper.py --list
      List all open page tabs (index / title / url) as JSON.
  python cdp_tab_scraper.py --scrape 0,2,5
      Scrape the selected tab indices; save .html + .txt to 001_chrome_capture/.
  python cdp_tab_scraper.py --scrape all
      Scrape every open tab.

Notes:
  - Connects to the user's actual running session; reads already-rendered DOM,
    so SPA sites (Douyin, etc.) yield real text. Lazy/anti-bot sections may
    need targeted handling.
  - Anyone who can reach localhost:9222 can read EVERY open tab. Keep the port
    open only while working; close it when done.
"""
import sys
import os
import json
import base64
import struct
import socket
import urllib.request
import datetime
from pathlib import Path

HOST = "localhost"
PORT = 9222
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "001_chrome_capture"


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data


def ws_connect(url):
    assert url.startswith("ws://"), "only ws:// supported"
    rest = url[5:]
    host, _, path = rest.partition("/")
    path = "/" + path
    port = PORT
    if ":" in host:
        host, p = host.split(":")
        port = int(p)
    sock = socket.create_connection((host, port), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += sock.recv(4096)
    header_part = buf.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
    if "101" not in header_part:
        raise ConnectionError("WS handshake failed: " + header_part)
    return sock


def _send_text_frame(sock, text):
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytes([0x81])  # FIN + text
    length = len(payload)
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 65536:
        header += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", length)
    sock.sendall(header + mask + masked)


def _recv_frame(sock):
    hdr = _recv_exact(sock, 2)
    fin = (hdr[0] & 0x80) != 0
    opcode = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    if masked:
        mask = _recv_exact(sock, 4)
    payload = _recv_exact(sock, length)
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return fin, opcode, payload


def _recv_message(sock):
    fragments = []
    while True:
        fin, opcode, payload = _recv_frame(sock)
        if opcode == 0x8:  # close
            return None
        if opcode == 0x9:  # ping -> pong
            sock.sendall(bytes([0x8A, len(payload)]) + payload)
            continue
        if opcode == 0xA:  # pong
            continue
        fragments.append(payload)
        if fin:
            return b"".join(fragments)


def cdp_eval(sock, expression, msg_id=1):
    """Run a JS expression in the target page; return the CDP response object."""
    _send_text_frame(sock, json.dumps({"id": msg_id, "method": "Runtime.enable"}))
    while True:
        raw = _recv_message(sock)
        if raw is None:
            raise ConnectionError("connection closed")
        obj = json.loads(raw.decode("utf-8"))
        if obj.get("id") == msg_id:
            break
    _send_text_frame(sock, json.dumps({
        "id": msg_id + 1, "method": "Runtime.evaluate",
        "params": {"expression": expression, "returnByValue": True}
    }))
    while True:
        raw = _recv_message(sock)
        if raw is None:
            raise ConnectionError("connection closed")
        obj = json.loads(raw.decode("utf-8"))
        if obj.get("id") == msg_id + 1:
            return obj
        # ignore events (have "method", no "id")


def list_targets():
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/json/list", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR: cannot connect to {HOST}:{PORT}. Start Chrome with the debug port. Detail: {e}")
        sys.exit(2)
    tabs = []
    for i, t in enumerate(data):
        if t.get("type") == "page":
            tabs.append({
                "index": i, "title": t.get("title", ""),
                "url": t.get("url", ""), "ws": t.get("webSocketDebuggerUrl"),
            })
    return tabs


def _cdp_value(obj):
    try:
        return obj["result"]["result"]["value"]
    except Exception:
        return ""


def scrape(indices):
    OUT_DIR.mkdir(exist_ok=True)
    all_tabs = list_targets()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    for idx in indices:
        if idx < 0 or idx >= len(all_tabs):
            print(f"[skip] invalid index {idx}")
            continue
        tab = all_tabs[idx]
        ws_url = tab.get("ws")
        if not ws_url:
            print(f"[skip] index {idx} has no webSocketDebuggerUrl")
            continue
        try:
            sock = ws_connect(ws_url)
            html_obj = cdp_eval(sock, "document.documentElement.outerHTML", 1)
            text_obj = cdp_eval(sock, "document.body ? document.body.innerText : ''", 3)
            title_obj = cdp_eval(sock, "document.title", 5)
            url_obj = cdp_eval(sock, "location.href", 7)
            sock.sendall(bytes([0x88, 0x00]))  # close
            sock.close()
            html = _cdp_value(html_obj)
            text = _cdp_value(text_obj)
            title = _cdp_value(title_obj) or tab["title"]
            url = _cdp_value(url_obj) or tab["url"]
        except Exception as e:
            print(f"[fail] index {idx}: {e}")
            continue
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (title or "tab"))[:40]
        f_html = OUT_DIR / f"{ts}_{idx}_{safe}.html"
        f_txt = OUT_DIR / f"{ts}_{idx}_{safe}.txt"
        f_html.write_text(html or "", encoding="utf-8")
        f_txt.write_text(f"URL: {url}\nTITLE: {title}\nCHARS: {len(text or '')}\n\n{text}", encoding="utf-8")
        results.append({"index": idx, "title": title, "url": url,
                        "html": str(f_html), "txt": str(f_txt), "chars": len(text or "")})
        print(f"[done] {idx}: {title}  ({len(text or '')} chars) -> {f_txt.name}")
    return results


def main():
    args = sys.argv[1:]
    mode = None
    val = None
    if "--list" in args:
        mode = "list"
    elif "--scrape" in args:
        mode = "scrape"
        i = args.index("--scrape")
        val = args[i + 1] if i + 1 < len(args) else "all"
    else:
        print(__doc__)
        return

    if mode == "list":
        tabs = list_targets()
        print(json.dumps(tabs, ensure_ascii=False, indent=2))
        print(f"\n{len(tabs)} open tabs. Copy indices and use --scrape to capture.")
        return

    if mode == "scrape":
        if val.strip().lower() == "all":
            tabs = list_targets()
            indices = [t["index"] for t in tabs]
        else:
            indices = [int(x) for x in val.split(",") if x.strip() != ""]
        res = scrape(indices)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print(f"\nCaptured {len(res)} tabs into: {OUT_DIR}")
        return


if __name__ == "__main__":
    main()
