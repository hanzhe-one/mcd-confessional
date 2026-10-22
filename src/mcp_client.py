"""麦门告解室 - 麦当劳 MCP 最小客户端（标准库实现，零第三方依赖）。

通过 streamablehttp 协议与麦当劳 MCP Server (https://mcp.mcd.cn) 通信，
支持 initialize / tools/call 两个动作，足够本项目的告解数据采集使用。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-03-26"


class MCPError(RuntimeError):
    """MCP 调用失败。"""


class MCPClient:
    """最小可用的麦当劳 MCP 客户端。

    用法::

        client = MCPClient()               # Token 从环境变量 MCD_MCP_TOKEN 读取
        client.initialize()
        result = client.call_tool("order-list")
    """

    def __init__(self, url: str | None = None, token: str | None = None) -> None:
        self.url = url or os.environ.get("MCD_MCP_URL", DEFAULT_MCP_URL)
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        self.session_id: str | None = None
        self._req_id = 0
        self._initialized = False

    # ------------------------------------------------------------------ #
    # 协议层
    # ------------------------------------------------------------------ #
    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _post(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.session_id = resp.headers.get("mcp-session-id") or self.session_id
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover - 网络异常路径
            detail = exc.read().decode("utf-8", "ignore")
            raise MCPError("MCP HTTP {}: {}".format(exc.code, detail[:300])) from exc
        except urllib.error.URLError as exc:
            raise MCPError("MCP 连接失败: {}".format(exc.reason)) from exc

        # JSON-RPC 通知（notification）没有 id，服务端按规范返回空响应体（202/204），
        # 此时不应尝试解析 JSON —— 这是真机联调才会暴露的坑。
        if not body.strip():
            return {}
        return self._parse_body(body)

    @staticmethod
    def _parse_body(body: str) -> dict:
        """streamablehttp 的响应可能是纯 JSON，也可能是 SSE 流，两种都兼容。"""
        text = body.strip()
        if not text:
            return {}
        if text.startswith("event:") or text.startswith("data:"):
            # SSE 可能包含多个 data 帧，取最后一个带 result/error 的
            last: dict | None = None
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    parsed = json.loads(payload)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                    last = parsed
                elif last is None:
                    last = parsed
            if last is None:
                raise MCPError("SSE 响应中未找到有效 data 帧")
            return last
        return json.loads(text)

    def initialize(self) -> None:
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "mcd-confessional", "version": "1.0.0"},
                },
            }
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    # ------------------------------------------------------------------ #
    # 工具调用
    # ------------------------------------------------------------------ #
    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """调用 MCP 工具，返回解析后的 JSON data 字段。

        部分工具（如 list-nutrition-foods）返回的是字符串而非对象，
        这里统一放回 {"data": ...} 形状，调用方按需取用。
        """
        if not self._initialized:
            self.initialize()

        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        if "error" in resp and resp["error"]:
            raise MCPError("MCP 工具 {} 报错: {}".format(name, resp["error"]))

        result = resp.get("result", {})
        if result.get("isError"):
            raise MCPError("MCP 工具 {} 执行业务失败".format(name))

        texts = [
            block.get("text", "")
            for block in result.get("content", [])
            if block.get("type") == "text"
        ]
        raw = "\n".join(t for t in texts if t)
        if not raw:
            return {"data": None}

        # MCP 约定：文本块里通常是 JSON 字符串，解析之；失败则原样返回文本
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            # 麦当劳 MCP 的实际返回形如「# API Response Information ... ## Original Response
            # {"success":true,...}」，即"给模型看的说明 + 原始 JSON"，
            # 必须从文本里抠出 JSON 对象，否则所有业务字段都取不到。
            parsed = self._extract_json(raw)
            if parsed is None:
                return {"data": raw, "raw_text": raw}

        if isinstance(parsed, dict) and "data" in parsed:
            return parsed
        return {"data": parsed, "raw_text": raw}

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从「说明文字 + JSON」的混合文本里提取第一个完整的 JSON 对象。"""
        marker = "## Original Response"
        idx = text.find(marker)
        candidate = text[idx + len(marker):].strip() if idx >= 0 else text.strip()

        start = candidate.find("{")
        if start < 0:
            return None

        depth = 0
        in_str = False
        escaped = False
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(candidate[start:i + 1])
                        except ValueError:
                            return None
        return None

    # ------------------------------------------------------------------ #
    # 业务便捷方法（本项目用到的四个工具）
    # ------------------------------------------------------------------ #
    def get_orders(self) -> list[dict]:
        resp = self.call_tool("order-list")
        data = resp.get("data")
        if isinstance(data, dict):
            return data.get("list") or []
        if isinstance(data, list):
            return data
        return []

    def get_nutrition_text(self) -> str:
        resp = self.call_tool("list-nutrition-foods")
        data = resp.get("data")
        if isinstance(data, str):
            return data
        raise MCPError("list-nutrition-foods 返回格式异常")

    def get_current_time(self) -> dict:
        resp = self.call_tool("now-time-info")
        data = resp.get("data")
        return data if isinstance(data, dict) else {}

    def get_coupons_text(self) -> str:
        """卡包优惠券（MCP 返回为格式化文本，尽力而为地解析）。"""
        try:
            resp = self.call_tool("query-my-coupons", {"page": "1", "pageSize": "50"})
        except MCPError:
            return ""
        data = resp.get("data")
        return data if isinstance(data, str) else ""
