"""Second spike pass: measure the FCA document and try exports. Does not save or close."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from spike_official_mcp import Mcp, log, spike_line, tool_text  # noqa: E402

OUT = ROOT / ".runtime" / "spike"

SCRIPT = r'''
import json, os
import adsk.core, adsk.fusion

OUT = r"C:\Cursor_Projects\MCP_Fusion360\.runtime\spike"

def _try(label, fn):
    try:
        ok, path = fn()
        size = os.path.getsize(path) if path and os.path.isfile(path) else 0
        return {"label": label, "ok": bool(ok), "bytes": int(size)}
    except Exception as exc:
        return {"label": label, "ok": False, "error": str(exc).splitlines()[-1][:240]}

def run(_context: str):
    os.makedirs(OUT, exist_ok=True)
    app = adsk.core.Application.get()
    docs = []
    target = None
    for i in range(app.documents.count):
        doc = app.documents.item(i)
        docs.append({"name": doc.name, "saved": bool(doc.isSaved), "modified": bool(doc.isModified)})
        if doc.name and "FCA_spike" in doc.name:
            target = doc
    if target is None:
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            if doc.name != "3DPT021-2" and doc.isModified:
                target = doc
                break
    if target is None:
        print("SPIKE|" + json.dumps({"error": "no FCA document", "documents": docs}))
        return
    target.activate()
    try:
        target.name = "FCA_spike"
    except Exception as exc:
        rename = str(exc).splitlines()[-1][:160]
    else:
        rename = ""
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    body = root.bRepBodies.item(0) if root.bRepBodies.count else None
    info = {
        "documents": docs,
        "active": target.name,
        "rename": rename,
        "bodies": int(root.bRepBodies.count),
        "designType": int(design.designType),
        "designIntent": int(design.designIntent),
        "units": str(design.unitsManager.defaultLengthUnits),
    }
    if body is None:
        print("SPIKE|" + json.dumps(info))
        return
    props = body.physicalProperties
    bbox = body.boundingBox
    info["volume_internal"] = float(props.volume)
    info["bbox_x10"] = [
        (bbox.maxPoint.x - bbox.minPoint.x) * 10.0,
        (bbox.maxPoint.y - bbox.minPoint.y) * 10.0,
        (bbox.maxPoint.z - bbox.minPoint.z) * 10.0,
    ]
    mgr = design.exportManager
    root_comp = root
    exports = []
    pairs = [
        ("step", lambda: (mgr.execute(mgr.createSTEPExportOptions(os.path.join(OUT, "cube.step"), root_comp)), os.path.join(OUT, "cube.step"))),
        ("stl", lambda: (mgr.execute(mgr.createSTLExportOptions(body, os.path.join(OUT, "cube.stl"))), os.path.join(OUT, "cube.stl"))),
        ("3mf", lambda: (mgr.execute(mgr.createC3MFExportOptions(body, os.path.join(OUT, "cube.3mf"))), os.path.join(OUT, "cube.3mf"))),
        ("obj", lambda: (mgr.execute(mgr.createOBJExportOptions(body, os.path.join(OUT, "cube.obj"))), os.path.join(OUT, "cube.obj"))),
        ("f3d", lambda: (mgr.execute(mgr.createFusionArchiveExportOptions(os.path.join(OUT, "cube.f3d"), root_comp)), os.path.join(OUT, "cube.f3d"))),
        ("smt", lambda: (mgr.execute(mgr.createSMTExportOptions(os.path.join(OUT, "cube.smt"), root_comp)), os.path.join(OUT, "cube.smt"))),
        ("usd", lambda: (mgr.execute(mgr.createUSDExportOptions(os.path.join(OUT, "cube.usdz"), root_comp)), os.path.join(OUT, "cube.usdz"))),
        ("iges", lambda: (mgr.execute(mgr.createIGESExportOptions(os.path.join(OUT, "cube.iges"), root_comp)), os.path.join(OUT, "cube.iges"))),
        ("sat", lambda: (mgr.execute(mgr.createSATExportOptions(os.path.join(OUT, "cube.sat"), root_comp)), os.path.join(OUT, "cube.sat"))),
    ]
    for label, fn in pairs:
        exports.append(_try(label, fn))
    img = os.path.join(OUT, "viewport.png")
    try:
        image_ok = bool(app.activeViewport.saveAsImageFile(img, 320, 240))
        image_bytes = os.path.getsize(img) if os.path.isfile(img) else 0
        image_error = ""
    except Exception as exc:
        image_ok = False
        image_bytes = 0
        image_error = str(exc).splitlines()[-1][:200]
    info["exports"] = exports
    info["image_ok"] = image_ok
    info["image_bytes"] = image_bytes
    info["image_error"] = image_error
    info["isSaved"] = bool(target.isSaved)
    print("SPIKE|" + json.dumps(info))
'''

CAPS = r'''
import json
import adsk.core
import adsk.fusion
import adsk.cam
import adsk.drawing
import adsk.volume

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    caps = {
        "cam": True,
        "recognized_hole": hasattr(adsk.cam, "RecognizedHole"),
        "drawing": True,
        "drawing_export": hasattr(adsk.drawing, "DrawingExportManager"),
        "volume": hasattr(adsk.volume, "VolumetricModel"),
        "beam_network": hasattr(adsk.volume, "BeamNetwork"),
        "thread_query": hasattr(adsk.fusion, "ThreadDataQuery"),
        "flat_pattern": hasattr(adsk.fusion, "FlatPattern"),
    }
    if design is not None:
        try:
            table = design.configurationTopTable
            caps["configurationTopTable"] = None if table is None else int(table.rows.count)
        except Exception as exc:
            caps["configurationTopTable"] = str(exc).splitlines()[-1][:180]
        try:
            caps["renderManager"] = design.renderManager is not None
        except Exception as exc:
            caps["renderManager"] = str(exc).splitlines()[-1][:180]
    print("SPIKE|" + json.dumps(caps))
'''


def main() -> int:
    mcp = Mcp()
    mcp.initialize()
    report = {}
    for name, code, timeout in (("exports", SCRIPT, 300), ("capabilities", CAPS, 60)):
        log(f"script {name}")
        resp = mcp.call(
            "fusion_mcp_execute",
            {"featureType": "script", "object": {"script": code, "readOnly": False}},
            timeout=timeout,
        )
        text = tool_text(resp)
        try:
            wrapped = json.loads(text)
            message = wrapped.get("message") or wrapped.get("error") or text
        except json.JSONDecodeError:
            message = text
        parsed = spike_line(message if isinstance(message, str) else json.dumps(message))
        report[name] = parsed
        report[name + "_elapsed_s"] = resp.get("_elapsed_s")
        log(json.dumps(parsed, ensure_ascii=False)[:500])
    dest = ROOT / "docs" / "spike" / "2705.1.25.followup.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
