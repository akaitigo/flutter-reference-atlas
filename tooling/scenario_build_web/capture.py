#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Capture a built Flutter Web page through Chrome DevTools Protocol."""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class WebSocket:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\nOrigin: http://127.0.0.1\r\n\r\n"
        )
        self.socket.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.socket.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket upgrade failed: {response[:120]!r}")
        self.next_id = 1

    def _read_exact(self, count: int) -> bytes:
        value = b""
        while len(value) < count:
            chunk = self.socket.recv(count - len(value))
            if not chunk:
                raise RuntimeError("Chrome DevTools WebSocket closed")
            value += chunk
        return value

    def _send(self, value: dict) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def _receive(self) -> dict:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if second & 0x80 else None
        payload = self._read_exact(length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x8:
            raise RuntimeError("Chrome DevTools WebSocket closed")
        if opcode != 0x1:
            return self._receive()
        return json.loads(payload)

    def command(self, method: str, params: dict | None = None) -> dict:
        command_id = self.next_id
        self.next_id += 1
        self._send({"id": command_id, "method": method, "params": params or {}})
        while True:
            response = self._receive()
            if response.get("id") == command_id:
                if "error" in response:
                    raise RuntimeError(f"CDP {method} failed: {response['error']}")
                return response.get("result", {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-data-dir", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    args = parser.parse_args()

    active_port = args.user_data_dir / "DevToolsActivePort"
    for _ in range(100):
        if active_port.is_file():
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Chrome DevToolsActivePort was not created")
    port = int(active_port.read_text().splitlines()[0])
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10))
    page = next((item for item in targets if item.get("type") == "page"), None)
    if page is None:
        raise RuntimeError("Chrome page target was not found")
    client = WebSocket(page["webSocketDebuggerUrl"])
    client.command("Runtime.enable")
    client.command("Page.enable")
    observed = None
    expression = "JSON.stringify({origin:location.origin,flutterView:document.querySelector('flutter-view')!==null})"
    for _ in range(120):
        result = client.command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        value = result.get("result", {}).get("value")
        if value:
            observed = json.loads(value)
            if observed.get("origin", "").startswith("http://127.0.0.1:") and observed.get("flutterView") is True:
                break
        time.sleep(0.25)
    else:
        raise RuntimeError(f"Flutter first-frame oracle was not observed: {observed}")
    document = client.command("DOM.getDocument")
    placeholder = client.command("DOM.querySelector", {
        "nodeId": document["root"]["nodeId"], "selector": "flt-semantics-placeholder",
    })
    if placeholder.get("nodeId"):
        client.command("DOM.focus", {"nodeId": placeholder["nodeId"]})
    client.command("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": 0, "y": 0,
    })
    client.command("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": 0, "y": 0, "button": "left", "clickCount": 1,
    })
    client.command("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": 0, "y": 0, "button": "left", "clickCount": 1,
    })
    client.command("Input.dispatchKeyEvent", {
        "type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
    })
    client.command("Input.dispatchKeyEvent", {
        "type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
    })
    time.sleep(0.5)
    accessibility = client.command("Accessibility.getFullAXTree")
    semantics_result = client.command("Runtime.evaluate", {
        "expression": "JSON.stringify(Array.from(document.querySelectorAll('[aria-label]')).map(node=>({tag:node.tagName,label:node.getAttribute('aria-label'),role:node.getAttribute('role')})))",
        "returnByValue": True,
    })
    semantics_value = semantics_result.get("result", {}).get("value", "[]")
    tree = {"accessibility": accessibility, "dom_semantics": json.loads(semantics_value)}
    screenshot = client.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    args.observation.write_text(json.dumps(observed, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    args.tree.write_text(json.dumps(tree, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    args.screenshot.write_bytes(base64.b64decode(screenshot["data"]))
    try:
        client.command("Browser.close")
    except (OSError, RuntimeError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
