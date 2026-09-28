"""MCP client for the official Fusion server.

Fusion answers HTTP 502 unless the request uses Expect: 100-continue and
Connection: close. urllib and httpx do not do that, so this client speaks
HTTP on a socket.
"""

from __future__ import annotations

import json
import socket
import time
import uuid

from fusion_cad_ai.config import EXEC_TIMEOUT_S, FUSION_MCP_URL, PROTOCOL_VERSION, fusion_host_port
from fusion_cad_ai.errors import FcaError
from fusion_cad_ai.logger import log
from fusion_cad_ai.transport.base import READ_ONLY_OPS
from fusion_cad_ai.transport.envelope import build_script, payload_or_raise


class OfficialMcpTransport:
    def __init__(self, url: str | None = None, timeout_s: float | None = None) -> None:
        self.url = url or FUSION_MCP_URL
        self.timeout_s = float(timeout_s or EXEC_TIMEOUT_S)
        host, port = _host_port(self.url)
        self.host = host
        self.port = port
        self.session: str | None = None
        self._id = 0
        self._ready = False

    def call(
        self,
        op: str,
        params: dict | None = None,
        *,
        timeout_s: float | None = None,
        read_only: bool | None = None,
    ) -> dict:
        params = dict(params or {})
        readonly = op in READ_ONLY_OPS if read_only is None else read_only
        if not readonly:
            self._ensure_no_dialog()
        request_id = uuid.uuid4().hex[:12]
        script = build_script(op, params, request_id)
        started = time.perf_counter()
        text = self._call_tool(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": script, "readOnly": bool(readonly)}},
            timeout_s or self.timeout_s,
        )
        result = payload_or_raise(text)
        result.setdefault("request_id", request_id)
        result["elapsed_s"] = round(time.perf_counter() - started, 3)
        return result

    def screenshot(self, direction: str, width_px: int, height_px: int) -> dict:
        text = self._call_tool(
            "fusion_mcp_read",
            {
                "queryType": "screenshot",
                "direction": direction,
                "width": int(width_px),
                "height": int(height_px),
                "antiAliasing": True,
            },
            timeout_s=60,
        )
        return {"raw": text, "direction": direction}

    def read(self, arguments: dict, timeout_s: float = 30) -> dict:
        text = self._call_tool("fusion_mcp_read", arguments, timeout_s=timeout_s)
        return _parse_json_text(text)

    def list_tools(self) -> list[dict]:
        self._ensure()
        reply = self._request("tools/list", {}, timeout=30)
        tools = (reply.get("result") or {}).get("tools") or []
        return list(tools)

    def _ensure_no_dialog(self) -> None:
        try:
            data = self.read({"queryType": "activeCommand"}, timeout_s=20)
        except FcaError:
            raise
        except Exception as exc:
            log(f"activeCommand недоступен: {exc}", "WARN")
            return
        if isinstance(data, dict) and data.get("isDefaultCommand") is False:
            command = data.get("commandId") or data.get("activeCommand") or "команда"
            raise FcaError(
                "COMMAND_DIALOG_OPEN",
                f"В Fusion открыт диалог команды {command}",
                hint="Закройте диалог или дождитесь окончания команды. SelectCommand этому не мешает.",
            )

    def _ensure(self) -> None:
        if self._ready:
            return
        try:
            self._request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "fusion-cad-ai", "version": "2.0.0"},
                },
                timeout=30,
            )
            self._notify("notifications/initialized", {})
        except FcaError:
            raise
        except OSError as exc:
            raise FcaError(
                "FUSION_NOT_REACHABLE",
                f"Официальный Fusion MCP недоступен на {self.host}:{self.port}",
                hint="Запустите Fusion и включите MCP Server Adapter.",
            ) from exc
        self._ready = True

    def _call_tool(self, name: str, arguments: dict, timeout_s: float) -> str:
        self._ensure()
        reply = self._request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout_s)
        if reply.get("error"):
            err = reply["error"]
            message = err.get("message") if isinstance(err, dict) else str(err)
            return str(message)
        result = reply.get("result") or {}
        if result.get("isError") and not result.get("content"):
            raise FcaError("FUSION_API_ERROR", "инструмент Fusion вернул isError")
        return _content_text(result)

    def _notify(self, method: str, params: dict) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params}, timeout=30)

    def _request(self, method: str, params: dict, timeout: float) -> dict:
        self._id += 1
        return self._post(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params},
            timeout=timeout,
        )

    def _post(self, payload: dict, timeout: float) -> dict:
        body = json.dumps(payload).encode("utf-8")
        path = _path_of(self.url)
        header = [
            f"POST {path} HTTP/1.1",
            f"Host: {self.host}:{self.port}",
            f"MCP-Protocol-Version: {PROTOCOL_VERSION}",
            "Accept: application/json, text/event-stream",
            "Content-Type: application/json",
            f"Content-Length: {len(body)}",
            "Expect: 100-continue",
            "Connection: close",
            "User-Agent: fusion-cad-ai/2.0",
        ]
        if self.session:
            header.append(f"Mcp-Session-Id: {self.session}")
        raw_header = ("\r\n".join(header) + "\r\n\r\n").encode("ascii")
        try:
            sock = socket.create_connection((self.host, self.port), timeout=timeout)
        except OSError as exc:
            raise FcaError(
                "FUSION_NOT_REACHABLE",
                f"Нет соединения с {self.host}:{self.port}",
                hint="Запустите Fusion и включите официальный MCP.",
            ) from exc
        sock.settimeout(timeout)
        try:
            sock.sendall(raw_header)
            status, headers, rest = _read_head(sock, b"")
            if status == 100:
                sock.sendall(body)
                status, headers, rest = _read_head(sock, rest)
            elif status >= 400:
                raise FcaError("FUSION_NOT_REACHABLE", f"HTTP {status} до тела запроса")
            else:
                sock.sendall(body)
            payload_bytes = _read_body(sock, headers, rest)
        except socket.timeout as exc:
            raise FcaError(
                "TIMEOUT",
                f"Fusion не ответил за {timeout:.0f} с",
                hint="Долгую операцию запускайте как job и смотрите job_status.",
            ) from exc
        except FcaError:
            raise
        except OSError as exc:
            raise FcaError("FUSION_NOT_REACHABLE", f"Соединение с Fusion оборвалось: {exc}") from exc
        finally:
            sock.close()
        sid = headers.get("mcp-session-id")
        if sid:
            self.session = sid
        text = payload_bytes.decode("utf-8", errors="replace")
        if "text/event-stream" in headers.get("content-type", ""):
            text = "".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
        if status >= 400:
            raise FcaError("FUSION_NOT_REACHABLE", f"HTTP {status}: {text[:300]}")
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FcaError("FUSION_API_ERROR", f"Ответ Fusion не JSON: {text[:300]}") from exc


def _host_port(url: str) -> tuple[str, int]:
    if url == FUSION_MCP_URL:
        return fusion_host_port()
    rest = url.split("://", 1)[-1]
    host_port = rest.split("/", 1)[0]
    if ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        return host, int(port_s)
    return host_port, 80


def _path_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    if "/" not in rest:
        return "/mcp"
    return "/" + rest.split("/", 1)[1]


def _read_head(sock: socket.socket, buf: bytes) -> tuple[int, dict[str, str], bytes]:
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1", errors="replace").split("\r\n")
    if not lines or " " not in lines[0]:
        raise FcaError("FUSION_API_ERROR", f"Пустой HTTP-ответ: {head[:200]!r}")
    status = int(lines[0].split(" ")[1])
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status, headers, rest


def _read_body(sock: socket.socket, headers: dict[str, str], rest: bytes) -> bytes:
    if headers.get("transfer-encoding", "").lower() == "chunked":
        return _read_chunked(sock, rest)
    length = int(headers.get("content-length", "0") or "0")
    if length <= 0:
        chunks = [rest]
        while True:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    data = rest
    while len(data) < length:
        chunk = sock.recv(min(65536, length - len(data)))
        if not chunk:
            break
        data += chunk
    return data[:length]


def _read_chunked(sock: socket.socket, rest: bytes) -> bytes:
    buf = rest
    out = bytearray()
    while True:
        while b"\r\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                return bytes(out)
            buf += chunk
        line, _, buf = buf.partition(b"\r\n")
        size = int(line.split(b";", 1)[0] or b"0", 16)
        if size == 0:
            return bytes(out)
        while len(buf) < size + 2:
            chunk = sock.recv(65536)
            if not chunk:
                return bytes(out)
            buf += chunk
        out += buf[:size]
        buf = buf[size + 2 :]


def _content_text(result: dict) -> str:
    parts: list[str] = []
    for block in result.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
        elif block.get("type") == "image":
            parts.append(json.dumps({"data": block.get("data") or "", "mimeType": block.get("mimeType") or "image/png"}))
        else:
            parts.append(json.dumps(block, ensure_ascii=False)[:2000])
    if parts:
        return "\n".join(parts)
    return json.dumps(result, ensure_ascii=False)


def _parse_json_text(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return {"text": stripped[:2000]}
    if isinstance(data, dict) and isinstance(data.get("message"), str):
        try:
            inner = json.loads(data["message"])
            if isinstance(inner, dict):
                return inner
        except json.JSONDecodeError:
            pass
    return data if isinstance(data, dict) else {"value": data}
