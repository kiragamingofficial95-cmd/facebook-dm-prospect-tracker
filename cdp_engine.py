"""
CDP Automation Engine for Facebook Prospect Tracker
Implements the exact technical playbook specified in the prompt:
- Remote debugging endpoint connection (ws / json/list)
- Formula bar focused editing with verification
- Messenger audit and status extraction
- Safe row deletion and cell updates
- CSV export verification using authenticated Chrome session
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime
import asyncio
import websockets

CDP_BASE_URL = "http://127.0.0.1:9222"

class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._msg_id = 0
        self._pending = {}

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
        asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if not future.done():
                        future.set_result(msg)
        except Exception:
            pass

    async def send(self, method, params=None):
        if params is None:
            params = {}
        self._msg_id += 1
        msg_id = self._msg_id
        future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future
        await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
        res = await future
        return res

    async def evaluate(self, expr, await_promise=True):
        res = await self.send("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise
        })
        if "result" in res and "result" in res["result"]:
            return res["result"]["result"].get("value")
        return None

    async def bring_to_front(self):
        await self.send("Page.bringToFront")
        await asyncio.sleep(0.3)

    async def key_down_up(self, key, code, vk=None):
        extra = {}
        if vk is not None:
            extra["windowsVirtualKeyCode"] = vk
            extra["nativeVirtualKeyCode"] = vk
        await self.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": key, "code": code, **extra})
        await self.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code, **extra})

    async def click(self, x, y, count=1, button="left"):
        await self.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": count})
        await self.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": count})

    async def type_text(self, text):
        for ch in str(text):
            await self.send("Input.dispatchKeyEvent", {"type": "char", "text": ch})
            await asyncio.sleep(0.015)

    async def commit_enter(self):
        await self.send("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": "Enter", "code": "Enter",
            "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
        })
        await self.send("Input.dispatchKeyEvent", {"type": "char", "text": "\r"})
        await self.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Enter", "code": "Enter",
            "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13
        })

    async def escape_revert(self):
        await self.key_down_up("Escape", "Escape", vk=27)
        await asyncio.sleep(0.2)
        await self.key_down_up("Escape", "Escape", vk=27)

    async def close(self):
        if self.ws:
            await self.ws.close()


def get_tabs(port=9222):
    try:
        url = f"http://127.0.0.1:{port}/json/list"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        return []


def parse_csv(csv_text):
    """Simple and robust CSV parser handling quotes and newlines."""
    import csv
    import io
    reader = csv.reader(io.StringIO(csv_text))
    return [row for row in reader]


def extract_doc_and_gid(url):
    """Extract Google Sheets Doc ID and GID from URL."""
    doc_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    gid_match = re.search(r'[#&?]gid=([0-9]+)', url)
    doc_id = doc_match.group(1) if doc_match else None
    gid = gid_match.group(1) if gid_match else "0"
    return doc_id, gid


async def export_sheet_csv(cdp: CDPClient, doc_id, gid):
    script = f"""
    (async () => {{
        try {{
            const url = 'https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}&cb=' + Date.now();
            const r = await fetch(url, {{ credentials: 'include' }});
            return await r.text();
        }} catch(e) {{
            return 'ERROR: ' + e.toString();
        }}
    }})()
    """
    res = await cdp.evaluate(script)
    return res


async def get_active_sheet_tabs_info(cdp: CDPClient):
    """Extract list of visible tab names and gids in the current Google Sheets page."""
    script = """
    (() => {
        const tabs = [];
        const items = document.querySelectorAll('.docs-sheet-tab');
        items.forEach(el => {
            const nameEl = el.querySelector('.docs-sheet-tab-name');
            const name = nameEl ? nameEl.innerText.trim() : el.innerText.trim();
            // Try to find tab id/gid from attributes
            const tabId = el.getAttribute('tab-id') || el.getAttribute('data-sheet-id') || el.id || '';
            const isActive = el.classList.contains('docs-sheet-active-tab');
            tabs.push({ name, tabId, isActive });
        });
        return tabs;
    })()
    """
    return await cdp.evaluate(script)
