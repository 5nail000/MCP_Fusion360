"""Parametric features. Distances go to Fusion as strings with mm, never as raw centimetres."""

from __future__ import annotations

import math

from fca_rt.doc import active_design, require_fca, root_component
from fca_rt.errors import RtError
from fca_rt.log import log
from fca_rt.sketch import add_circle, add_rectangle, largest_profile, plane_offset
from fca_rt.units import expr_mm


def remember(name: str, body) -> str:
    from fca_rt import session

    token = ""
    try:
        token = str(body.entityToken)
    except Exception:
        token = name
    try:
        body.name = name
    except Exception as exc:
        log(f"body name {name}: {exc}", "WARN")
    session.STATE.names[name] = {"token": token, "component": root_component().name}
    return name


def body_by_name(name: str):
    _app, design = active_design()
    from fca_rt import session

    record = session.STATE.names.get(name) or {}
    token = record.get("token") or ""
    if token:
        try:
            found = design.findEntityByToken(token)
            body = _body_from_token(found)
            if body is not None:
                return body
        except Exception:
            pass
    for body in _walk_bodies(design.rootComponent):
        if body.name == name and _is_body(body):
            return body
    seen = [body.name for body in _walk_bodies(design.rootComponent) if getattr(body, "name", "")]
    raise RtError("FUSION_API_ERROR", f"Тело {name} не найдено", hint=", ".join(seen[:12]))


def box(size_x_mm: float, size_y_mm: float, size_z_mm: float, *, center_mm=(0.0, 0.0, 0.0), join: str | None = None, name: str | None = None, size_z_expr: str | None = None) -> str:
    require_fca()
    component = root_component()
    cx, cy, cz = center_mm
    z0 = cz - size_z_mm / 2.0
    plane = plane_offset(component, component.xYConstructionPlane, z0)
    sketch = component.sketches.add(plane)
    add_rectangle(sketch, cx - size_x_mm / 2.0, cy - size_y_mm / 2.0, cx + size_x_mm / 2.0, cy + size_y_mm / 2.0)
    operation, participants = _join_or_new(join)
    body = _extrude(component, largest_profile(sketch), expr_mm(size_z_mm, size_z_expr), operation, participants)
    title = name or (join or _fresh_name("box"))
    if join:
        return join
    return remember(title, body)


def cylinder(diameter_mm: float, height_mm: float, *, center_mm=(0.0, 0.0, 0.0), axis: str = "z", join: str | None = None, name: str | None = None, diameter_expr: str | None = None, height_expr: str | None = None) -> str:
    require_fca()
    if axis != "z":
        raise RtError("FUSION_API_ERROR", "Положительный цилиндр пока строится вдоль Z. Вырез может идти вдоль X, Y или Z.")
    component = root_component()
    cx, cy, cz = center_mm
    z0 = cz - height_mm / 2.0
    plane = plane_offset(component, component.xYConstructionPlane, z0)
    sketch = component.sketches.add(plane)
    add_circle(sketch, cx, cy, diameter_mm)
    _try_diameter_dimension(sketch, diameter_expr or f"{diameter_mm} mm")
    operation, participants = _join_or_new(join)
    body = _extrude(component, largest_profile(sketch), expr_mm(height_mm, height_expr), operation, participants)
    if join:
        return join
    return remember(name or _fresh_name("cylinder"), body)


def cut_cylinder(target: str, diameter_mm: float, height_mm: float, center_mm=(0.0, 0.0, 0.0), *, axis: str = "z", diameter_expr: str | None = None) -> str:
    require_fca()
    component = root_component()
    host = body_by_name(target)
    sketch, depth = _cut_sketch(component, axis, center_mm, diameter_mm, height_mm)
    _try_diameter_dimension(sketch, diameter_expr or f"{diameter_mm} mm")
    _extrude(component, largest_profile(sketch), expr_mm(depth, None), _cut_operation(), [host])
    return target


def cut_box(target: str, size_mm, center_mm=(0.0, 0.0, 0.0)) -> str:
    require_fca()
    component = root_component()
    host = body_by_name(target)
    sx, sy, sz = size_mm
    cx, cy, cz = center_mm
    plane = plane_offset(component, component.xYConstructionPlane, cz - sz / 2.0)
    sketch = component.sketches.add(plane)
    add_rectangle(sketch, cx - sx / 2.0, cy - sy / 2.0, cx + sx / 2.0, cy + sy / 2.0)
    _extrude(component, largest_profile(sketch), expr_mm(sz, None), _cut_operation(), [host])
    return target


def fillet_z(target: str, which: str, radius_mm: float, *, radius_expr: str | None = None) -> str:
    require_fca()
    if radius_mm <= 0:
        return target
    import adsk.core

    component = root_component()
    body = body_by_name(target)
    edges = _edges_at(body, which)
    if edges.count == 0:
        raise RtError("FUSION_API_ERROR", f"Нет рёбер для скругления ({which})")
    feature_input = component.features.filletFeatures.createInput()
    feature_input.edgeSetInputs.addConstantRadiusEdgeSet(
        edges,
        adsk.core.ValueInput.createByString(expr_mm(radius_mm, radius_expr)),
        False,
    )
    feature = component.features.filletFeatures.add(feature_input)
    if feature is None:
        raise RtError("FUSION_API_ERROR", "Скругление не создано")
    return target


def chamfer_z(target: str, which: str, distance_mm: float, *, distance_expr: str | None = None) -> str:
    require_fca()
    if distance_mm <= 0:
        return target
    import adsk.core

    component = root_component()
    body = body_by_name(target)
    edges = _edges_at(body, which)
    if edges.count == 0:
        raise RtError("FUSION_API_ERROR", f"Нет рёбер для фаски ({which})")
    feature_input = component.features.chamferFeatures.createInput2()
    feature_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        edges,
        adsk.core.ValueInput.createByString(expr_mm(distance_mm, distance_expr)),
        False,
    )
    feature = component.features.chamferFeatures.add(feature_input)
    if feature is None:
        raise RtError("FUSION_API_ERROR", "Фаска не создана")
    return target


def summaries() -> list[dict]:
    from fca_rt.units import cm3_to_mm3

    _app, design = active_design()
    rows = []
    for body in _walk_bodies(design.rootComponent):
        try:
            volume = cm3_to_mm3(float(body.physicalProperties.volume))
            faces = int(body.faces.count)
        except Exception:
            volume = 0.0
            faces = 0
        rows.append({"name": body.name, "volume_mm3": volume, "faces": faces})
    return rows


def _extrude(component, profile, distance_expr: str, operation, participants):
    import adsk.core
    import adsk.fusion

    features = component.features.extrudeFeatures
    feature_input = features.createInput(profile, operation)
    distance = adsk.core.ValueInput.createByString(distance_expr)
    try:
        feature_input.setDistanceExtent(False, distance)
    except Exception:
        extent = adsk.fusion.DistanceExtentDefinition.create(distance)
        feature_input.setOneSideExtent(extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    if participants:
        try:
            feature_input.participantBodies = [body for body in participants if _is_body(body)]
        except Exception as exc:
            log(f"participantBodies: {exc}", "WARN")
    feature = features.add(feature_input)
    if feature is None:
        raise RtError("FUSION_API_ERROR", "Выдавливание не создано")
    if feature.bodies.count == 0:
        raise RtError("FUSION_API_ERROR", "Выдавливание не дало тела")
    return feature.bodies.item(0)


def _join_or_new(join: str | None):
    import adsk.fusion

    if not join:
        return adsk.fusion.FeatureOperations.NewBodyFeatureOperation, None
    return adsk.fusion.FeatureOperations.JoinFeatureOperation, [body_by_name(join)]


def _cut_operation():
    import adsk.fusion

    return adsk.fusion.FeatureOperations.CutFeatureOperation


def _cut_sketch(component, axis: str, center_mm, diameter_mm: float, height_mm: float):
    cx, cy, cz = center_mm
    if axis == "z":
        plane = plane_offset(component, component.xYConstructionPlane, cz - height_mm / 2.0)
        sketch = component.sketches.add(plane)
        add_circle(sketch, cx, cy, diameter_mm)
        return sketch, height_mm
    if axis == "x":
        # yZ sketch: X is -global Z, Y is +global Y.
        plane = plane_offset(component, component.yZConstructionPlane, cx - height_mm / 2.0)
        sketch = component.sketches.add(plane)
        add_circle(sketch, -cz, cy, diameter_mm)
        return sketch, height_mm
    if axis == "y":
        # xZ sketch: X is +global X, Y is -global Z.
        plane = plane_offset(component, component.xZConstructionPlane, cy - height_mm / 2.0)
        sketch = component.sketches.add(plane)
        add_circle(sketch, cx, -cz, diameter_mm)
        return sketch, height_mm
    raise RtError("FUSION_API_ERROR", f"Неизвестная ось {axis}")


def _edges_at(body, which: str):
    import adsk.core

    bbox = body.boundingBox
    target = bbox.maxPoint.z if which == "top" else bbox.minPoint.z
    collection = adsk.core.ObjectCollection.create()
    tolerance = 0.002
    for edge in body.edges:
        geometry = edge.geometry
        center = getattr(geometry, "center", None)
        if center is not None and abs(center.z - target) <= tolerance:
            collection.add(edge)
            continue
        try:
            start = edge.startVertex.geometry
            end = edge.endVertex.geometry
        except Exception:
            continue
        if abs(start.z - target) <= tolerance and abs(end.z - target) <= tolerance:
            collection.add(edge)
    return collection


def _try_diameter_dimension(sketch, expression: str) -> None:
    try:
        circle = sketch.sketchCurves.sketchCircles.item(sketch.sketchCurves.sketchCircles.count - 1)
        text = circle.centerSketchPoint.geometry
        dimension = sketch.sketchDimensions.addDiameterDimension(circle, text)
        dimension.parameter.expression = expression
    except Exception as exc:
        log(f"diameter dimension skipped: {exc}", "WARN")


def _fresh_name(prefix: str) -> str:
    from fca_rt import session

    return f"{prefix}-{len(session.STATE.names) + 1}"


def _is_body(entity) -> bool:
    return entity is not None and hasattr(entity, "boundingBox") and hasattr(entity, "faces") and hasattr(entity, "name")


def _body_from_token(found):
    if found is None:
        return None
    items = found if isinstance(found, (list, tuple)) else [found]
    for item in items:
        if _is_body(item):
            return item
    return None


def _walk_bodies(component):
    for index in range(component.bRepBodies.count):
        yield component.bRepBodies.item(index)
    for index in range(component.occurrences.count):
        yield from _walk_bodies(component.occurrences.item(index).component)


def bolt_centers(diameter_mm: float, count: int) -> list[tuple[float, float]]:
    radius = diameter_mm / 2.0
    return [
        (radius * math.cos(2.0 * math.pi * index / count), radius * math.sin(2.0 * math.pi * index / count))
        for index in range(count)
    ]
