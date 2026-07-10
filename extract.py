#!/usr/bin/env python3
r"""
Extract visible chat messages from a logged-in browser page.

Windows example:
  powershell -ExecutionPolicy Bypass -File .\start_chrome_debug.ps1 -Url "https://web.telegram.org/a/"
  python .\extract.py --platform telegram --output telegram.md

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform as os_platform
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


BRIDGE_BACKEND = "auto"
BROWSER_URL = "http://127.0.0.1:9222"
TAB_MATCHES: list[str] = ["douyin.com"]
_CDP_CLIENT: "ChromeCDP | None" = None

IMPORTANT_KEYWORDS = (
    "重点",
    "精华",
    "总结",
    "结论",
    "方案",
    "建议",
    "方法",
    "流程",
    "步骤",
    "注意",
    "风险",
    "问题",
    "原因",
    "解决",
    "复盘",
    "数据",
    "增长",
    "转化",
    "成交",
    "客户",
    "价格",
    "成本",
    "利润",
    "工具",
    "模型",
    "提示词",
    "AI",
    "http",
    "https",
)


@dataclass(frozen=True)
class PlatformConfig:
    name: str
    tab_matches: tuple[str, ...]
    chat_title: str
    conversation_title_selectors: tuple[str, ...]
    conversation_click_selectors: tuple[str, ...]
    scroll_selectors: tuple[str, ...]
    message_selectors: tuple[str, ...]


PLATFORMS: dict[str, PlatformConfig] = {
    "douyin": PlatformConfig(
        name="douyin",
        tab_matches=("douyin.com",),
        chat_title="Douyin",
        conversation_title_selectors=(".conversationConversationItemtitle",),
        conversation_click_selectors=(".conversationConversationItemwrapper", "[role='listitem']", "li", "div"),
        scroll_selectors=(".messageMessageListlist",),
        message_selectors=(".TextMessageTextpureText",),
    ),
    "telegram": PlatformConfig(
        name="telegram",
        tab_matches=("web.telegram.org",),
        chat_title="Telegram",
        conversation_title_selectors=(
            ".chatlist-chat .title",
            ".ListItem .title",
            "[class*='ChatInfo'] [class*='title']",
            "[class*='chat'] [class*='title']",
        ),
        conversation_click_selectors=(".chatlist-chat", ".ListItem", "[role='listitem']", "a", "div"),
        scroll_selectors=(
            ".MessageList",
            ".messages-container",
            ".custom-scroll",
            "[class*='message-list']",
            "[class*='MessageList']",
        ),
        message_selectors=(
            ".Message .text-content",
            ".message .text-content",
            "[data-message-id] .text-content",
            "[class*='message'] [class*='text-content']",
            "[class*='Message'] [class*='text']",
        ),
    ),
    "twitter": PlatformConfig(
        name="twitter",
        tab_matches=("x.com", "twitter.com"),
        chat_title="X / Twitter",
        conversation_title_selectors=(
            "[data-testid='conversation'] [dir='auto']",
            "[data-testid='cellInnerDiv'] [dir='auto']",
        ),
        conversation_click_selectors=("[data-testid='conversation']", "[data-testid='cellInnerDiv']", "a", "div"),
        scroll_selectors=(
            "[aria-label='Timeline: Messages']",
            "[data-testid='primaryColumn']",
            "main",
        ),
        message_selectors=(
            "[data-testid='messageEntry'] [dir='auto']",
            "[data-testid='DmScrollerContainer'] [dir='auto']",
            "[data-testid='cellInnerDiv'] [dir='auto']",
            "[data-testid='tweetText']",
        ),
    ),
    "wechat": PlatformConfig(
        name="wechat",
        tab_matches=("web.wechat.com", "wx.qq.com", "wechat"),
        chat_title="WeChat",
        conversation_title_selectors=(
            ".nickname_text",
            ".nickname",
            ".chat_item .nickname",
            "[class*='nickname']",
        ),
        conversation_click_selectors=(".chat_item", ".chatItem", "[role='listitem']", "li", "div"),
        scroll_selectors=(".chat_bd", ".message-list", ".scroll-content", "[class*='message']", "main"),
        message_selectors=(
            ".message .plain",
            ".bubble_cont .plain",
            ".message .js_message_plain",
            "[class*='message'] [class*='plain']",
            "[class*='bubble']",
        ),
    ),
    "qq": PlatformConfig(
        name="qq",
        tab_matches=("qq.com",),
        chat_title="QQ",
        conversation_title_selectors=(
            ".recent-item .name",
            ".chat-item .name",
            ".list-item .name",
            "[class*='conversation'] [class*='name']",
        ),
        conversation_click_selectors=(".recent-item", ".chat-item", ".list-item", "[role='listitem']", "li", "div"),
        scroll_selectors=(".message-list", ".chat-list", ".aio-msg-list", "[class*='message']", "main"),
        message_selectors=(
            ".msg-content",
            ".message-content",
            ".msg-text",
            "[class*='message'] [class*='content']",
            "[class*='msg'] [class*='text']",
        ),
    ),
    "generic": PlatformConfig(
        name="generic",
        tab_matches=("",),
        chat_title="Generic chat page",
        conversation_title_selectors=("[role='listitem']", "li", "a", "button"),
        conversation_click_selectors=("[role='listitem']", "li", "a", "button", "div"),
        scroll_selectors=("[role='log']", "[aria-live]", "main", "body"),
        message_selectors=(
            "[data-message-id]",
            "[data-testid*='message' i]",
            "[class*='message' i]",
            "[class*='msg' i]",
            "[role='article']",
        ),
    ),
}


class BrowserBridgeError(RuntimeError):
    """Raised when JavaScript cannot be executed in the browser."""


class SimpleWebSocket:
    """Small WebSocket client for Chrome DevTools Protocol, stdlib only."""

    def __init__(self, ws_url: str, timeout: int = 15):
        self.url = urllib.parse.urlparse(ws_url)
        self.timeout = timeout
        self.sock: socket.socket | ssl.SSLSocket | None = None

    def connect(self) -> None:
        if self.url.scheme not in {"ws", "wss"}:
            raise BrowserBridgeError(f"Unsupported WebSocket scheme: {self.url.scheme}")

        host = self.url.hostname or "127.0.0.1"
        port = self.url.port or (443 if self.url.scheme == "wss" else 80)
        raw_sock = socket.create_connection((host, port), timeout=self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname=host) if self.url.scheme == "wss" else raw_sock
        self.sock.settimeout(self.timeout)

        path = self.url.path or "/"
        if self.url.query:
            path += "?" + self.url.query

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        headers = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.sock.sendall(headers.encode("ascii"))
        response = self._recv_until(b"\r\n\r\n")
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise BrowserBridgeError("Chrome DevTools WebSocket handshake failed.")

        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if accept.encode("ascii") not in response:
            raise BrowserBridgeError("Chrome DevTools WebSocket handshake was rejected.")

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self) -> str:
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise BrowserBridgeError("Chrome DevTools WebSocket closed.")
            if opcode == 0x9:
                self._send_frame(0xA, payload)

    def _recv_until(self, marker: bytes) -> bytes:
        assert self.sock is not None
        data = b""
        while marker not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        assert self.sock is not None
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend(struct.pack("!BH", 0x80 | 126, length))
        else:
            header.extend(struct.pack("!BQ", 0x80 | 127, length))

        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_frame(self) -> tuple[int, bytes]:
        assert self.sock is not None
        header = self._recv_exact(2)
        first, second = header[0], header[1]
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _recv_exact(self, size: int) -> bytes:
        assert self.sock is not None
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise BrowserBridgeError("Unexpected end of Chrome DevTools WebSocket data.")
            data += chunk
        return data


class ChromeCDP:
    def __init__(self, browser_url: str, tab_matches: list[str]):
        self.browser_url = browser_url.rstrip("/")
        self.tab_matches = [m.lower() for m in tab_matches if m]
        self.ws: SimpleWebSocket | None = None
        self.next_id = 1

    def connect(self) -> None:
        target = self._find_target()
        self.ws = SimpleWebSocket(target["webSocketDebuggerUrl"])
        self.ws.connect()
        self.command("Runtime.enable")

    def close(self) -> None:
        if self.ws:
            self.ws.close()
            self.ws = None

    def evaluate(self, code: str) -> str | None:
        result = self.command(
            "Runtime.evaluate",
            {
                "expression": code,
                "awaitPromise": True,
                "returnByValue": True,
                "userGesture": True,
            },
        )
        if "exceptionDetails" in result:
            text = result["exceptionDetails"].get("text", "JavaScript execution failed")
            raise BrowserBridgeError(text)

        remote = result.get("result", {})
        if remote.get("type") == "undefined":
            return None
        value = remote.get("value")
        if value is None:
            return None
        return str(value)

    def command(self, method: str, params: dict | None = None) -> dict:
        if self.ws is None:
            raise BrowserBridgeError("Chrome DevTools connection is not open.")

        message_id = self.next_id
        self.next_id += 1
        self.ws.send_text(json.dumps({"id": message_id, "method": method, "params": params or {}}))

        while True:
            message = json.loads(self.ws.recv_text())
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise BrowserBridgeError(message["error"].get("message", "Chrome DevTools command failed"))
            return message.get("result", {})

    def _find_target(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.browser_url}/json", timeout=5) as response:
                targets = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BrowserBridgeError(
                f"Cannot connect to Chrome at {self.browser_url}. "
                "Start Chrome with .\\start_chrome_debug.ps1 first."
            ) from exc

        pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            raise BrowserBridgeError("No debuggable Chrome tabs found.")

        if not self.tab_matches:
            return pages[0]

        for page in pages:
            haystack = f"{page.get('url', '')} {page.get('title', '')}".lower()
            if any(match in haystack for match in self.tab_matches):
                return page

        available = "\n".join(f"- {p.get('title', '(untitled)')} | {p.get('url', '')}" for p in pages)
        raise BrowserBridgeError(
            f"No Chrome tab matched {', '.join(self.tab_matches)}. Open the target chat page first.\n{available}"
        )


def run_js_applescript(code: str) -> str | None:
    js_path = os.path.join(tempfile.gettempdir(), "_chat_extract_js.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(code)

    script = (
        'tell application "Google Chrome"\n'
        f'set jsFile to POSIX file "{js_path}"\n'
        "set jsContent to read jsFile\n"
        "execute active tab of front window javascript jsContent\n"
        "end tell"
    )
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15, encoding="utf-8")
    out = r.stdout.strip()
    if not out or out == "missing value":
        return None
    return out


def run_js_cdp(code: str) -> str | None:
    global _CDP_CLIENT
    if _CDP_CLIENT is None:
        _CDP_CLIENT = ChromeCDP(BROWSER_URL, TAB_MATCHES)
        _CDP_CLIENT.connect()
    return _CDP_CLIENT.evaluate(code)


def run_js(code: str) -> str | None:
    backend = BRIDGE_BACKEND
    if backend == "auto":
        backend = "applescript" if os_platform.system() == "Darwin" else "cdp"

    if backend == "applescript":
        return run_js_applescript(code)
    if backend == "cdp":
        return run_js_cdp(code)
    raise BrowserBridgeError(f"Unknown backend: {backend}")


def js_array(items: tuple[str, ...] | list[str]) -> str:
    return json.dumps(list(items), ensure_ascii=False)


def click_chat(name: str, config: PlatformConfig) -> bool:
    name_json = json.dumps(name, ensure_ascii=False)
    r = run_js(
        f"""
(function() {{
  var targetName = {name_json};
  var titleSelectors = {js_array(config.conversation_title_selectors)};
  var clickSelectors = {js_array(config.conversation_click_selectors)};

  function norm(text) {{
    return (text || '').replace(/\\s+/g, ' ').trim();
  }}

  function closestClickable(el) {{
    for (var i = 0; i < clickSelectors.length; i++) {{
      var found = el.closest(clickSelectors[i]);
      if (found) return found;
    }}
    return el;
  }}

  for (var s = 0; s < titleSelectors.length; s++) {{
    var items = document.querySelectorAll(titleSelectors[s]);
    for (var i = 0; i < items.length; i++) {{
      var text = norm(items[i].textContent);
      if (text === targetName || text.indexOf(targetName) >= 0) {{
        var wrapper = closestClickable(items[i]);
        var rect = wrapper.getBoundingClientRect();
        wrapper.dispatchEvent(new MouseEvent('click', {{
          bubbles: true,
          cancelable: true,
          clientX: rect.x + rect.width / 2,
          clientY: rect.y + rect.height / 2,
          view: window
        }}));
        return 'clicked';
      }}
    }}
  }}
  return 'not found';
}})()
"""
    )
    return r == "clicked"


def get_page_title() -> str:
    r = run_js("(function(){return document.title || location.hostname || 'chat';})()")
    return r or "chat"


def get_scroll_info(config: PlatformConfig) -> dict:
    r = run_js(
        f"""
(function() {{
  var selectors = {js_array(config.scroll_selectors)};

  function visible(el) {{
    var rect = el.getBoundingClientRect();
    var style = window.getComputedStyle(el);
    return rect.height > 80 && rect.width > 100 && style.display !== 'none' && style.visibility !== 'hidden';
  }}

  function bySelectors() {{
    for (var i = 0; i < selectors.length; i++) {{
      var nodes = document.querySelectorAll(selectors[i]);
      for (var n = 0; n < nodes.length; n++) {{
        var el = nodes[n];
        if (visible(el) && el.scrollHeight > el.clientHeight + 20) return el;
      }}
    }}
    return null;
  }}

  function bestScrollable() {{
    var all = Array.prototype.slice.call(document.querySelectorAll('body, main, section, div, ul'));
    var best = null;
    var bestScore = 0;
    for (var i = 0; i < all.length; i++) {{
      var el = all[i];
      if (!visible(el) || el.scrollHeight <= el.clientHeight + 20) continue;
      var rect = el.getBoundingClientRect();
      var score = el.scrollHeight + rect.height * 3;
      if (score > bestScore) {{
        best = el;
        bestScore = score;
      }}
    }}
    return best;
  }}

  var el = bySelectors() || bestScrollable() || document.scrollingElement || document.documentElement;
  window.__chatExtractScroller = el;
  return JSON.stringify({{
    sh: el ? el.scrollHeight : 0,
    ch: el ? el.clientHeight : 0,
    st: el ? el.scrollTop : 0,
    tag: el ? el.tagName : '',
    className: el ? String(el.className || '') : ''
  }});
}})()
"""
    )
    if not r:
        raise BrowserBridgeError("Could not locate a scrollable message container.")
    return json.loads(r)


def set_scroll_top(pos: int) -> None:
    run_js(
        f"""
(function() {{
  var el = window.__chatExtractScroller || document.scrollingElement || document.documentElement;
  if (el) el.scrollTop = {pos};
}})()
"""
    )


def collect_messages(config: PlatformConfig, min_length: int) -> list[str]:
    r = run_js(
        f"""
(function() {{
  var selectors = {js_array(config.message_selectors)};
  var minLength = {min_length};
  var scroller = window.__chatExtractScroller || document;
  var nodes = [];

  function norm(text) {{
    return (text || '')
      .replace(/\\u00a0/g, ' ')
      .replace(/[ \\t]+/g, ' ')
      .replace(/\\n{{3,}}/g, '\\n\\n')
      .trim();
  }}

  function pushNode(el) {{
    if (!el || nodes.indexOf(el) >= 0) return;
    var rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    nodes.push(el);
  }}

  for (var s = 0; s < selectors.length; s++) {{
    var found = scroller.querySelectorAll ? scroller.querySelectorAll(selectors[s]) : document.querySelectorAll(selectors[s]);
    for (var i = 0; i < found.length; i++) pushNode(found[i]);
  }}

  if (nodes.length === 0) {{
    var fallback = document.querySelectorAll('[data-message-id], [data-testid*="message" i], [class*="message" i], [class*="msg" i], [role="article"]');
    for (var f = 0; f < fallback.length; f++) pushNode(fallback[f]);
  }}

  var results = [];
  for (var n = 0; n < nodes.length; n++) {{
    var text = norm(nodes[n].innerText || nodes[n].textContent || '');
    if (text.length >= minLength) results.push(text);
  }}
  return JSON.stringify(results);
}})()
"""
    )
    if not r:
        return []
    try:
        return json.loads(r)
    except json.JSONDecodeError:
        return []


def extract_all(
    chat_name: str,
    config: PlatformConfig,
    output_path: str,
    seen_path: str | None = None,
    scroll_step: int = 500,
    min_length: int = 2,
    max_rounds: int | None = None,
) -> int:
    seen: set[str] = set()
    if seen_path and os.path.exists(seen_path):
        with open(seen_path, encoding="utf-8") as f:
            seen = set(json.load(f))

    info = get_scroll_info(config)
    total_h = int(info["sh"])
    if total_h <= 0:
        print("ERROR: Message list is empty or not loaded.")
        return 0

    print(f"Platform: {config.name}")
    print(f"Scroller: {info.get('tag', '')} {str(info.get('className', ''))[:80]}")
    print(f"ScrollHeight: {total_h}px")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    if seen_path:
        os.makedirs(os.path.dirname(os.path.abspath(seen_path)) or ".", exist_ok=True)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {chat_name} chat log\n\n")
        f.write(f"> Platform: {config.chat_title}\n")
        f.write(f"> Extracted at: {now_str}\n")
        f.write("> Message count: __PENDING__\n\n")
        f.write("---\n\n")

    positions = list(range(total_h, -scroll_step, -scroll_step))
    if max_rounds is not None:
        positions = positions[:max_rounds]

    total_new = 0
    for i, pos in enumerate(positions):
        set_scroll_top(pos)
        time.sleep(0.35)

        for message in collect_messages(config, min_length):
            message = message.strip()
            if message and message not in seen:
                seen.add(message)
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"- {message.replace(chr(10), chr(10) + '  ')}\n")
                total_new += 1

        if i % 20 == 0:
            pct = round((total_h - pos) / total_h * 100)
            print(f"  {pct}% | seen={len(seen)}")

    if seen_path:
        with open(seen_path, "w", encoding="utf-8") as f:
            json.dump(list(seen), f, ensure_ascii=False, indent=2)

    with open(output_path, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("__PENDING__", str(len(seen)))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Done: {len(seen)} total messages -> {output_path}")
    return total_new


def read_markdown_messages(markdown_path: str) -> list[str]:
    messages: list[str] = []
    current: list[str] = []

    with open(markdown_path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if line.startswith("- "):
                if current:
                    messages.append("\n".join(current).strip())
                current = [line[2:].strip()]
            elif current and line.startswith("  "):
                current.append(line.strip())

    if current:
        messages.append("\n".join(current).strip())

    return [m for m in messages if m]


def message_score(message: str) -> int:
    text = message.strip()
    score = min(len(text), 220) // 20
    score += sum(3 for keyword in IMPORTANT_KEYWORDS if keyword.lower() in text.lower())
    score += 4 if "http://" in text or "https://" in text else 0
    score += 2 if any(ch.isdigit() for ch in text) else 0
    score += 2 if "?" in text or "？" in text else 0
    score += 2 if any(marker in text for marker in ("1.", "2.", "①", "②", "：", ":")) else 0
    score -= 5 if len(text) < 12 else 0
    return score


def pick_digest_items(messages: list[str], max_items: int) -> list[str]:
    ranked = sorted(enumerate(messages), key=lambda item: (message_score(item[1]), item[0]), reverse=True)
    selected_indexes = sorted(index for index, message in ranked[:max_items] if message_score(message) > 0)
    return [messages[index] for index in selected_indexes]


def build_digest(markdown_path: str, title: str, max_items: int = 30) -> str:
    messages = read_markdown_messages(markdown_path)
    highlights = pick_digest_items(messages, max_items)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# {title}",
        "",
        f"> 生成时间: {generated_at}",
        f"> 原始消息数: {len(messages)}",
        f"> 精华条目数: {len(highlights)}",
        "",
        "## 核心精华",
        "",
    ]

    if highlights:
        for item in highlights:
            compact = item.replace("\n", "\n  ")
            lines.append(f"- {compact}")
    else:
        lines.append("- 未识别到足够有效的精华内容。建议检查原始 Markdown 是否已成功提取聊天消息。")

    lines.extend(
        [
            "",
            "## 原始文件",
            "",
            f"- `{Path(markdown_path).name}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_digest(markdown_path: str, digest_path: str, title: str, max_items: int) -> str:
    content = build_digest(markdown_path, title, max_items)
    os.makedirs(os.path.dirname(os.path.abspath(digest_path)) or ".", exist_ok=True)
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Digest written -> {digest_path}")
    return content


def publish_digest_to_feishu(
    digest_path: str,
    title: str,
    cli_name: str = "lark-cli",
    timeout: int = 120,
) -> None:
    cli_path = shutil.which(cli_name)
    if not cli_path:
        raise RuntimeError(
            f"Feishu CLI '{cli_name}' was not found. Install and authenticate lark-cli first, "
            "then rerun with --publish-feishu."
        )

    cwd = Path.cwd().resolve()
    content_path = Path(digest_path).resolve()
    cleanup_path: Path | None = None

    try:
        relative_content_path = content_path.relative_to(cwd)
    except ValueError:
        cleanup_path = cwd / f".feishu_publish_{int(time.time())}.md"
        cleanup_path.write_text(content_path.read_text(encoding="utf-8"), encoding="utf-8")
        relative_content_path = cleanup_path.relative_to(cwd)

    command = [
        cli_path,
        "docs",
        "+create",
        "--doc-format",
        "markdown",
        "--format",
        "json",
        "--title",
        title,
        "--content",
        f"@{relative_content_path.as_posix()}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if cleanup_path and cleanup_path.exists():
        cleanup_path.unlink()

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Feishu CLI failed with exit code {result.returncode}: {detail}")

    output = (result.stdout or result.stderr or "").strip()
    print("Feishu document created.")
    if output:
        print(output)


def default_temp_file(chat_name: str, platform_name: str, suffix: str) -> str:
    raw = f"{platform_name}_{chat_name}"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in raw).strip("_")
    return os.path.join(tempfile.gettempdir(), f"{safe or 'chat'}_{suffix}")


def default_digest_file(output_path: str) -> str:
    path = Path(output_path)
    return str(path.with_name(f"{path.stem}_digest.md"))


def resolve_platform(name: str) -> PlatformConfig:
    key = name.lower()
    aliases = {"x": "twitter", "tweet": "twitter", "tg": "telegram", "wx": "wechat"}
    key = aliases.get(key, key)
    if key not in PLATFORMS:
        raise SystemExit(f"Unknown platform '{name}'. Use --list-platforms to see supported values.")
    return PLATFORMS[key]


def main() -> None:
    global BRIDGE_BACKEND, BROWSER_URL, TAB_MATCHES

    parser = argparse.ArgumentParser(description="Extract messages from a logged-in browser chat page.")
    parser.add_argument("--platform", "-p", default="douyin", help="douyin, wechat, qq, telegram, twitter, generic.")
    parser.add_argument("--group", "-g", default=None, help="Optional chat/group name to click before extraction.")
    parser.add_argument("--chat", default=None, help="Alias of --group.")
    parser.add_argument("--output", "-o", default=None, help="Output Markdown file.")
    parser.add_argument("--seen", default=None, help="JSON file for dedup state.")
    parser.add_argument("--create-digest", action="store_true", help="Create a local digest Markdown after extraction.")
    parser.add_argument("--digest-output", default=None, help="Output path for digest Markdown.")
    parser.add_argument("--digest-max-items", type=int, default=30, help="Maximum highlight items in digest.")
    parser.add_argument("--publish-feishu", action="store_true", help="Create a Feishu document from the digest via lark-cli.")
    parser.add_argument("--feishu-title", default=None, help="Feishu document title.")
    parser.add_argument("--feishu-cli", default="lark-cli", help="Feishu CLI command name. Default: lark-cli.")
    parser.add_argument("--feishu-timeout", type=int, default=120, help="Feishu CLI timeout in seconds.")
    parser.add_argument("--step", type=int, default=500, help="Scroll step in pixels.")
    parser.add_argument("--min-length", type=int, default=2, help="Ignore extracted text shorter than this.")
    parser.add_argument("--max-rounds", type=int, default=None, help="Debug option: limit scroll samples.")
    parser.add_argument(
        "--backend",
        choices=["auto", "cdp", "applescript"],
        default="auto",
        help="Browser bridge. Windows uses cdp; macOS can use applescript.",
    )
    parser.add_argument("--browser-url", default=BROWSER_URL, help="Chrome DevTools HTTP URL for cdp backend.")
    parser.add_argument("--tab-match", default=None, help="Comma-separated text used to select the Chrome tab.")
    parser.add_argument("--list-platforms", action="store_true", help="Print supported platforms and exit.")
    args = parser.parse_args()

    if args.list_platforms:
        for key, config in PLATFORMS.items():
            print(f"{key}: tab matches {', '.join(config.tab_matches) or '(first tab)'}")
        return

    config = resolve_platform(args.platform)
    chat = args.group or args.chat

    BRIDGE_BACKEND = args.backend
    BROWSER_URL = args.browser_url
    TAB_MATCHES = [m.strip() for m in args.tab_match.split(",")] if args.tab_match else list(config.tab_matches)

    try:
        chat_name = chat or get_page_title()
        output = args.output or default_temp_file(chat_name, config.name, "today.md")
        seen_path = args.seen or default_temp_file(chat_name, config.name, "seen.json")

        if chat:
            print(f"Looking for chat: {chat}")
            if not click_chat(chat, config):
                print(f"ERROR: Could not find chat '{chat}' in the conversation list.")
                print("Open the chat manually, or copy the exact name shown in the conversation list.")
                sys.exit(1)
            print("Waiting for chat to load...")
            time.sleep(3)
        else:
            print("No --group supplied; extracting from the currently opened chat page.")

        extract_all(chat_name, config, output, seen_path, args.step, args.min_length, args.max_rounds)

        if args.create_digest or args.publish_feishu:
            today = datetime.now().strftime("%Y-%m-%d")
            digest_title = args.feishu_title or f"{chat_name} 群聊精华摘要 {today}"
            digest_path = args.digest_output or default_digest_file(output)
            write_digest(output, digest_path, digest_title, args.digest_max_items)

            if args.publish_feishu:
                publish_digest_to_feishu(digest_path, digest_title, args.feishu_cli, args.feishu_timeout)
    except BrowserBridgeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    finally:
        if _CDP_CLIENT is not None:
            _CDP_CLIENT.close()


if __name__ == "__main__":
    main()
