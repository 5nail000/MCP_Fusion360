"""Read-only-to-the-repo probe of the official Fusion MCP on this machine.

Creates one unsaved design named FCA_spike and exports into .runtime/spike.
Does not save or close Fusion documents and does not touch the cloud.
"""

from __future__ import annotations

import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime" / "spike"
DOCS = ROOT / "docs"
URL = "http://127.0.0.1:27182/mcp"
PROTOCOL = "2025-06-18"


def _read_http_head(sock: socket.socket, buf: bytes) -> tuple[int, dict[str, str], bytes]:
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1", errors="replace").split("\r\n")
    status = int(lines[0].split(" ")[1])
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status, headers, rest


def log(message: str, level: str = "INFO") -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [{level}] {message}", file=sys.stderr, flush=True)


class Mcp:
    def __init__(self) -> None:
        self.session: str | None = None
        self._id = 0

    def _post(self, payload: dict, timeout: float) -> dict:
        """POST with Expect: 100-continue. Fusion MCP returns 502 without it."""
        body = json.dumps(payload).encode("utf-8")
        header_lines = [
            "POST /mcp HTTP/1.1",
            "Host: 127.0.0.1:27182",
            f"MCP-Protocol-Version: {PROTOCOL}",
            "Accept: application/json, text/event-stream",
            "User-Agent: fca-spike/0.1",
            "Content-Type: application/json",
            f"Content-Length: {len(body)}",
            "Expect: 100-continue",
            "Connection: close",
        ]
        if self.session:
            header_lines.append(f"Mcp-Session-Id: {self.session}")
        raw_headers = ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii")
        started = time.perf_counter()
        sock = socket.create_connection(("127.0.0.1", 27182), timeout=timeout)
        sock.settimeout(timeout)
        try:
            sock.sendall(raw_headers)
            status, resp_headers, rest = _read_http_head(sock, b"")
            if status == 100:
                sock.sendall(body)
                status, resp_headers, rest = _read_http_head(sock, rest)
            elif status >= 400:
                raise RuntimeError(f"HTTP {status} before body")
            else:
                sock.sendall(body)
            length = int(resp_headers.get("content-length", "0") or "0")
            payload_bytes = rest
            while len(payload_bytes) < length:
                chunk = sock.recv(min(65536, length - len(payload_bytes)))
                if not chunk:
                    break
                payload_bytes += chunk
            sid = resp_headers.get("mcp-session-id")
            if sid:
                self.session = sid
            ctype = resp_headers.get("content-type", "")
            text = payload_bytes[:length].decode("utf-8", errors="replace") if length else ""
        finally:
            sock.close()
        if "text/event-stream" in ctype:
            text = "".join(
                line[5:].strip() for line in text.splitlines() if line.startswith("data:")
            )
        elapsed = time.perf_counter() - started
        if status >= 400:
            raise RuntimeError(f"HTTP {status}: {text[:500]!r}")
        parsed = json.loads(text) if text.strip() else {}
        parsed["_elapsed_s"] = round(elapsed, 3)
        return parsed

    def initialize(self) -> dict:
        self._id += 1
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "fca-spike", "version": "0.1.0"},
                },
            },
            timeout=30,
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=30)
        return result

    def request(self, method: str, params: dict | None = None, timeout: float = 60) -> dict:
        self._id += 1
        return self._post(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}},
            timeout=timeout,
        )

    def call(self, name: str, arguments: dict, timeout: float = 120) -> dict:
        return self.request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=timeout,
        )


def tool_text(response: dict) -> str:
    result = response.get("result") or {}
    if response.get("error"):
        return json.dumps(response["error"], ensure_ascii=False)
    content = result.get("content") or []
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
        elif isinstance(block, dict):
            parts.append(json.dumps(block, ensure_ascii=False)[:500])
    if parts:
        return "\n".join(parts)
    return json.dumps(result, ensure_ascii=False)[:4000]


def spike_line(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("SPIKE|"):
            return json.loads(line[6:])
    return {"raw": text[:4000]}


SCRIPT_STATE_A = r'''
import json, sys, types
import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    marker = sys.modules.get("fca_spike_marker")
    info = {
        "version": str(app.version),
        "doc_count": int(app.documents.count),
        "marker_before": getattr(marker, "value", None),
    }
    mod = types.ModuleType("fca_spike_marker")
    mod.value = 7
    sys.modules["fca_spike_marker"] = mod
    prod = app.activeProduct
    design = adsk.fusion.Design.cast(prod) if prod else None
    info["has_design"] = design is not None
    if design is not None:
        info["designType"] = int(design.designType)
        info["designIntent"] = int(design.designIntent)
        info["defaultLengthUnits"] = str(design.unitsManager.defaultLengthUnits)
    names = []
    for i in range(app.documents.count):
        doc = app.documents.item(i)
        names.append({"name": doc.name, "isSaved": bool(doc.isSaved), "isModified": bool(doc.isModified)})
    info["documents"] = names
    print("SPIKE|" + json.dumps(info))
'''

SCRIPT_STATE_B = r'''
import json, sys

def run(_context: str):
    marker = sys.modules.get("fca_spike_marker")
    print("SPIKE|" + json.dumps({"marker_after": getattr(marker, "value", None)}))
'''

SCRIPT_CUBE = r'''
import json, os, traceback
import adsk.core, adsk.fusion

OUT = r"C:\Cursor_Projects\MCP_Fusion360\.runtime\spike"

def _export(mgr, label, options, path):
    try:
        ok = bool(mgr.execute(options))
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        return {"label": label, "ok": ok, "bytes": size, "path_ok": size > 32}
    except Exception as exc:
        return {"label": label, "ok": False, "error": str(exc).splitlines()[-1][:300]}

def run(_context: str):
    os.makedirs(OUT, exist_ok=True)
    app = adsk.core.Application.get()
    doc = None
    for i in range(app.documents.count):
        item = app.documents.item(i)
        if item.name and "FCA_spike" in item.name:
            doc = item
            break
    created = False
    if doc is None:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        created = True
    doc.activate()
    try:
        doc.name = "FCA_spike"
    except Exception as exc:
        name_error = str(exc)
    else:
        name_error = ""
    design = adsk.fusion.Design.cast(app.activeProduct)
    before = {
        "designType": int(design.designType),
        "designIntent": int(design.designIntent),
        "defaultLengthUnits": str(design.unitsManager.defaultLengthUnits),
    }
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    intent_error = ""
    try:
        design.designIntent = adsk.fusion.DesignIntentTypes.HybridDesignIntentType
    except Exception as exc:
        intent_error = str(exc).splitlines()[-1][:300]
    root = design.rootComponent
    if root.bRepBodies.count == 0:
        sketch = root.sketches.add(root.xYConstructionPlane)
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(0, 0, 0),
            adsk.core.Point3D.create(1.0, 1.0, 0),
        )
        ext_in = root.features.extrudeFeatures.createInput(
            sketch.profiles.item(0),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByString("10 mm"))
        root.features.extrudeFeatures.add(ext_in)
    body = root.bRepBodies.item(0)
    props = body.physicalProperties
    bbox = body.boundingBox
    img = os.path.join(OUT, "viewport.png")
    image_ok = False
    image_error = ""
    try:
        image_ok = bool(app.activeViewport.saveAsImageFile(img, 320, 240))
    except Exception as exc:
        image_error = str(exc).splitlines()[-1][:300]
    mgr = design.exportManager
    exports = [
        _export(mgr, "step", mgr.createSTEPExportOptions(os.path.join(OUT, "cube.step"), body), os.path.join(OUT, "cube.step")),
        _export(mgr, "stl", mgr.createSTLExportOptions(body, os.path.join(OUT, "cube.stl")), os.path.join(OUT, "cube.stl")),
        _export(mgr, "3mf", mgr.createC3MFExportOptions(body, os.path.join(OUT, "cube.3mf")), os.path.join(OUT, "cube.3mf")),
        _export(mgr, "obj", mgr.createOBJExportOptions(body, os.path.join(OUT, "cube.obj")), os.path.join(OUT, "cube.obj")),
        _export(mgr, "f3d", mgr.createFusionArchiveExportOptions(os.path.join(OUT, "cube.f3d"), body), os.path.join(OUT, "cube.f3d")),
        _export(mgr, "smt", mgr.createSMTExportOptions(os.path.join(OUT, "cube.smt"), body), os.path.join(OUT, "cube.smt")),
        _export(mgr, "usd", mgr.createUSDExportOptions(os.path.join(OUT, "cube.usd"), body), os.path.join(OUT, "cube.usd")),
        _export(mgr, "iges", mgr.createIGESExportOptions(os.path.join(OUT, "cube.iges"), body), os.path.join(OUT, "cube.iges")),
        _export(mgr, "sat", mgr.createSATExportOptions(os.path.join(OUT, "cube.sat"), body), os.path.join(OUT, "cube.sat")),
    ]
    info = {
        "created": created,
        "name_error": name_error,
        "doc_name": doc.name,
        "isSaved": bool(doc.isSaved),
        "isModified": bool(doc.isModified),
        "doc_count": int(app.documents.count),
        "before": before,
        "after_type": int(design.designType),
        "after_intent": int(design.designIntent),
        "intent_error": intent_error,
        "volume_internal": float(props.volume),
        "volume_mm3_if_cm3": float(props.volume) * 1000.0,
        "bbox_mm_if_cm": [
            (bbox.maxPoint.x - bbox.minPoint.x) * 10.0,
            (bbox.maxPoint.y - bbox.minPoint.y) * 10.0,
            (bbox.maxPoint.z - bbox.minPoint.z) * 10.0,
        ],
        "image_ok": image_ok,
        "image_bytes": os.path.getsize(img) if os.path.isfile(img) else 0,
        "image_error": image_error,
        "exports": exports,
    }
    print("SPIKE|" + json.dumps(info))
'''

SCRIPT_CAPS = r'''
import json
import adsk.core, adsk.fusion

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    caps = {}
    try:
        import adsk.cam
        caps["cam_import"] = True
        caps["recognized_hole"] = hasattr(adsk.cam, "RecognizedHole")
        caps["cam_product"] = adsk.cam.CAM.cast(design) is not None if design else False
    except Exception as exc:
        caps["cam_import"] = str(exc).splitlines()[-1][:200]
    try:
        import adsk.drawing
        caps["drawing_import"] = True
        caps["has_createDrawing"] = hasattr(adsk.drawing, "Drawing") or True
        caps["drawing_export_manager"] = hasattr(adsk.drawing, "DrawingExportManager")
    except Exception as exc:
        caps["drawing_import"] = str(exc).splitlines()[-1][:200]
    try:
        import adsk.volume
        caps["volume_import"] = True
        caps["volumetric_model"] = hasattr(adsk.volume, "VolumetricModel")
        caps["beam_network"] = hasattr(adsk.volume, "BeamNetwork")
    except Exception as exc:
        caps["volume_import"] = str(exc).splitlines()[-1][:200]
    if design is not None:
        try:
            table = design.configurationTopTable
            caps["configurationTopTable"] = table is not None
            caps["configuration_rows"] = int(table.rows.count) if table else 0
        except Exception as exc:
            caps["configurationTopTable"] = str(exc).splitlines()[-1][:200]
        try:
            caps["renderManager"] = design.renderManager is not None
        except Exception as exc:
            caps["renderManager"] = str(exc).splitlines()[-1][:200]
        try:
            import adsk.fusion as f
            caps["section_analyses"] = hasattr(design, "analyses")
            caps["flat_pattern"] = hasattr(f, "FlatPattern")
            caps["thread_query"] = hasattr(f, "ThreadDataQuery")
        except Exception as exc:
            caps["feature_probe"] = str(exc).splitlines()[-1][:200]
    print("SPIKE|" + json.dumps(caps))
'''

SCRIPT_SLEEP = r'''
import json, time

def run(_context: str):
    started = time.perf_counter()
    time.sleep(4)
    print("SPIKE|" + json.dumps({"slept_s": round(time.perf_counter() - started, 3)}))
'''

SCRIPT_TINY = r'''
def run(_context: str):
    print("SPIKE|{\"ok\": true}")
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (DOCS / "spike").mkdir(parents=True, exist_ok=True)
    (DOCS / "official-fusion-mcp").mkdir(parents=True, exist_ok=True)
    mcp = Mcp()
    log("initialize official Fusion MCP")
    init = mcp.initialize()
    report: dict = {"initialize": {k: v for k, v in init.items() if k != "_elapsed_s"}, "elapsed": {}}
    report["elapsed"]["initialize"] = init.get("_elapsed_s")

    log("tools/list")
    tools = mcp.request("tools/list", timeout=60)
    resources = mcp.request("resources/list", timeout=60)
    tool_items = (tools.get("result") or {}).get("tools") or []
    res_items = (resources.get("result") or {}).get("resources") or []
    snapshot = {
        "captured_local": datetime.now().isoformat(timespec="seconds"),
        "serverInfo": (init.get("result") or {}).get("serverInfo"),
        "protocol": (init.get("result") or {}).get("protocolVersion"),
        "capabilities": (init.get("result") or {}).get("capabilities"),
        "tool_names": [t.get("name") for t in tool_items],
        "tools": [
            {
                "name": t.get("name"),
                "description_chars": len(t.get("description") or ""),
                "inputSchema": t.get("inputSchema"),
                "annotations": t.get("annotations"),
            }
            for t in tool_items
        ],
        "resource_uris": [r.get("uri") for r in res_items],
    }
    snap_path = DOCS / "official-fusion-mcp" / "2705.1.25.json"
    snap_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"wrote {snap_path} tools={len(tool_items)} resources={len(res_items)}")

    def read(query: dict, key: str) -> None:
        log(f"read {key}")
        resp = mcp.call("fusion_mcp_read", query, timeout=60)
        text = tool_text(resp)
        if "base64Data" in text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = {"raw": text[:200]}
            data = payload.get("base64Data") or ""
            payload["base64_chars"] = len(data)
            payload.pop("base64Data", None)
            if data:
                import base64
                png = base64.b64decode(data)
                dest = OUT / "official_screenshot.png"
                dest.write_bytes(png)
                payload["png_bytes"] = len(png)
                payload["png_header"] = png[:8] == b"\x89PNG\r\n\x1a\n"
            report[key] = payload
        else:
            try:
                report[key] = json.loads(text)
            except json.JSONDecodeError:
                report[key] = {"raw": text[:4000]}
        report["elapsed"][key] = resp.get("_elapsed_s")

    read({"queryType": "licensing"}, "licensing")
    read({"queryType": "document", "operation": "open"}, "documents_open")
    read({"queryType": "activeCommand"}, "active_command")

    def script(name: str, code: str, timeout: float = 180, read_only: bool = False) -> None:
        log(f"script {name}")
        resp = mcp.call(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": code, "readOnly": read_only}},
            timeout=timeout,
        )
        text = tool_text(resp)
        report[name] = spike_line(text)
        report["elapsed"][name] = resp.get("_elapsed_s")
        if "raw" in report[name]:
            log(f"script {name} no SPIKE line", "WARN")

    script("state_a", SCRIPT_STATE_A, read_only=True)
    script("state_b", SCRIPT_STATE_B, read_only=True)
    script("cube_and_exports", SCRIPT_CUBE, timeout=300, read_only=False)
    script("capabilities", SCRIPT_CAPS, read_only=True)
    script("sleep4", SCRIPT_SLEEP, timeout=60, read_only=True)

    latencies = []
    log("latency x20")
    for i in range(20):
        resp = mcp.call(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": SCRIPT_TINY, "readOnly": True}},
            timeout=60,
        )
        latencies.append(resp.get("_elapsed_s"))
    latencies_sorted = sorted(x for x in latencies if isinstance(x, (int, float)))
    report["latency_20"] = {
        "samples_s": latencies,
        "p50_s": latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else None,
        "max_s": latencies_sorted[-1] if latencies_sorted else None,
    }

    read(
        {
            "queryType": "screenshot",
            "width": 64,
            "height": 64,
            "direction": "iso-top-right",
            "antiAliasing": False,
            "transparentBackground": True,
        },
        "screenshot",
    )

    dest = DOCS / "spike" / "2705.1.25.raw.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
