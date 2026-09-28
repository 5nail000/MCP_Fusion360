"""Volumetric lattice. The graph node list is read from the live build, not hardcoded as success."""

from __future__ import annotations

from fca_rt.doc import require_fca
from fca_rt.errors import RtError
from fca_rt.log import log


def apply(cell_mm: float = 4.0, radius_mm: float = 0.6) -> dict:
    import adsk.volume

    design = require_fca()
    root = design.rootComponent
    if root.bRepBodies.count == 0:
        from fca_rt.features import box

        box(20, 20, 20, center_mm=(10, 10, 10), name="lattice_bounds")
    body = root.bRepBodies.item(root.bRepBodies.count - 1)
    features = root.features.volumetricModelFeatures
    feature_input = features.createInput(body)
    feature = features.add(feature_input)
    if feature is None:
        raise RtError("FUSION_API_ERROR", "VolumetricModelFeature не создан")
    model = feature.volumetricModel if hasattr(feature, "volumetricModel") else None
    node_types: list[str] = []
    attached = ""
    if model is not None:
        try:
            graph = model.getGraph(adsk.volume.GraphTypes.PrimaryGraphType)
            node_types = list(graph.allPossibleNodeTypes)
            attached = _attach_lattice(graph, node_types, cell_mm, radius_mm)
        except Exception as exc:
            log(f"volumetric graph: {exc}", "WARN")
            attached = str(exc).splitlines()[-1][:180]
    return {
        "created": True,
        "cell_mm": float(cell_mm),
        "radius_mm": float(radius_mm),
        "node_types_sample": node_types[:12],
        "lattice": attached,
        "preview_api": True,
    }


def _attach_lattice(graph, node_types: list[str], cell_mm: float, radius_mm: float) -> str:
    import adsk.core
    import adsk.volume

    preferred = next((item for item in node_types if "attice" in item or "Beam" in item or "Gyroid" in item), "")
    node_type = preferred or ("ReferencedGeometrySDF" if "ReferencedGeometrySDF" in node_types else "")
    if not node_type:
        return "в билде нет узла решётки; модель объёма создана без графа"
    node = graph.addNode("fca_lattice", node_type)
    if node is None:
        return f"узел {node_type} не добавился"
    network = adsk.volume.BeamNetwork.create()
    pitch = cell_mm / 10.0
    radius = radius_mm / 10.0
    vertices = []
    beams = []
    radii = []
    for i in range(3):
        for j in range(3):
            vertices.append(adsk.core.Point3D.create(i * pitch, j * pitch, 0))
            vertices.append(adsk.core.Point3D.create(i * pitch, j * pitch, pitch * 2))
            start = len(vertices) - 2
            beams.extend((start, start + 1))
            radii.extend((radius, radius))
    network.vertices = vertices
    network.beams = beams
    network.radii = radii
    for prop in _properties(node):
        if hasattr(prop, "beamNetwork"):
            prop.beamNetwork = network
            return f"beam network на узле {node_type}"
    return f"узел {node_type} создан, свойство beamNetwork не найдено"


def _properties(node):
    props = getattr(node, "properties", None)
    if props is None:
        return []
    try:
        return [props.item(index) for index in range(props.count)]
    except Exception:
        return []
