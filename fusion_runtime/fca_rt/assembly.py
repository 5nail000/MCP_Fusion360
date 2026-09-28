"""Components and joints. Occurrence geometry is used so the joint lives in the assembly."""

from __future__ import annotations

from fca_rt.doc import active_design, require_fca
from fca_rt.errors import RtError
from fca_rt.log import log


def add_component(name: str) -> str:
    import adsk.core

    design = require_fca()
    from fca_rt import session

    existing = _occurrence(design.rootComponent, name)
    if existing is not None:
        session.STATE.active_component = name
        return name
    transform = adsk.core.Matrix3D.create()
    occurrence = design.rootComponent.occurrences.addNewComponent(transform)
    occurrence.component.name = name
    try:
        occurrence.name = name
    except Exception as exc:
        log(f"occurrence name: {exc}", "WARN")
    session.STATE.active_component = name
    return name


def create_joint(kind: str, a: str, b: str, limits: dict | None = None) -> dict:
    import adsk.fusion

    design = require_fca()
    occ_a = _occurrence(design.rootComponent, a)
    occ_b = _occurrence(design.rootComponent, b)
    if occ_a is None or occ_b is None:
        raise RtError("FUSION_API_ERROR", f"Компонент {a} или {b} не найден")
    candidates = []
    placed = _cylinder_geometry(occ_a) or _planar_geometry(occ_a) or _cylinder_geometry(occ_b) or _planar_geometry(occ_b)
    if placed is not None:
        candidates.append(placed)
    point = _point_geometry(occ_a) or _point_geometry(occ_b)
    if point is not None:
        candidates.append(point)
    if not candidates and kind.lower() != "rigid":
        raise RtError("FUSION_API_ERROR", "Не найдена геометрия для шарнира")
    if not candidates:
        candidates.append(None)
    # As-built keeps the modeled clearance. A regular joint would drag the parts together.
    # A planar-face joint origin is rejected on this build; a vertex point is the fallback.
    last_error = "шарнир не создан"
    joint = None
    for geometry in candidates:
        try:
            joint_input = design.rootComponent.asBuiltJoints.createInput(occ_a, occ_b, geometry)
        except Exception as exc:
            last_error = f"AsBuiltJoint createInput: {exc}"
            continue
        if joint_input is None or not _set_motion(joint_input, kind):
            last_error = f"Тип шарнира {kind} не принят"
            continue
        try:
            joint = design.rootComponent.asBuiltJoints.add(joint_input)
        except Exception as exc:
            last_error = f"AsBuiltJoint add: {exc}"
            continue
        if joint is not None:
            break
    if joint is None:
        raise RtError("FUSION_API_ERROR", last_error)
    if joint is None:
        raise RtError("FUSION_API_ERROR", "Шарнир не создан")
    joint.name = f"{kind}_{a}_{b}"
    _apply_limits(joint, limits or {})
    return {"name": joint.name, "kind": kind, "a": a, "b": b}


def interference(objects: str = "", include_coincident: bool = False) -> dict:
    import adsk.core

    design = require_fca()
    chosen = [item.strip() for item in objects.split(",") if item.strip()]
    collection = adsk.core.ObjectCollection.create()
    for body in _proxy_bodies(design, chosen):
        collection.add(body)
    if collection.count < 2:
        return {"interference": False, "pairs": [], "reason": "меньше двух тел"}
    tool_input = design.createInterferenceInput(collection)
    try:
        tool_input.areCoincidentFacesIncluded = bool(include_coincident)
    except Exception:
        pass
    results = design.analyzeInterference(tool_input)
    pairs = []
    for index in range(results.count):
        item = results.item(index)
        volume = 0.0
        try:
            volume = float(item.interferenceBody.physicalProperties.volume) * 1000.0
        except Exception:
            volume = 0.0
        pairs.append({"index": index, "volume_mm3": volume})
    return {"interference": bool(pairs), "pairs": pairs}


def motion_sweep(joint_index: int, start_deg: float, stop_deg: float, steps: int) -> dict:
    import math

    design = require_fca()
    from fca_rt.snapshots import capture, restore

    joint = _joint_at(design, joint_index)
    capture("fca_auto_before_motion")
    hit = None
    occurrence = getattr(joint, "occurrenceOne", None)
    base = _matrix_copy(occurrence.transform) if occurrence is not None else None
    try:
        motion = joint.jointMotion
        for step in range(max(steps, 1) + 1):
            angle = start_deg + (stop_deg - start_deg) * step / max(steps, 1)
            # The joint keeps the rest pose. Suppress it so the sweep transform is what interference sees.
            try:
                joint.isSuppressed = True
            except Exception:
                pass
            _set_angle(motion, angle, occurrence, base)
            report = interference("")
            if report["interference"]:
                hit = angle
                break
    finally:
        restore("fca_auto_before_motion")
        if occurrence is not None and base is not None:
            try:
                occurrence.transform = base
            except Exception:
                pass
    return {"collision": hit is not None, "angle_deg": hit, "restored": True, "steps": steps}


def _joint_at(design, index: int):
    collections = (design.rootComponent.asBuiltJoints, design.rootComponent.joints)
    cursor = index
    for collection in collections:
        if cursor < collection.count:
            return collection.item(cursor)
        cursor -= collection.count
    raise RtError("FUSION_API_ERROR", "Шарнир не найден")


def _set_motion(joint_input, kind: str) -> bool:
    import adsk.fusion

    axis = adsk.fusion.JointDirections.ZAxisJointDirection
    kind = kind.lower()
    if kind == "rigid":
        return bool(joint_input.setAsRigidJointMotion())
    if kind == "revolute":
        return bool(joint_input.setAsRevoluteJointMotion(axis))
    if kind == "slider":
        return bool(joint_input.setAsSliderJointMotion(axis))
    if kind == "cylindrical":
        return bool(joint_input.setAsCylindricalJointMotion(axis))
    if kind == "pin-slot":
        return bool(joint_input.setAsPinSlotJointMotion(axis, adsk.fusion.JointDirections.XAxisJointDirection))
    if kind == "planar":
        return bool(joint_input.setAsPlanarJointMotion(axis))
    if kind == "ball":
        return bool(joint_input.setAsBallJointMotion(adsk.fusion.JointDirections.YAxisJointDirection, adsk.fusion.JointDirections.XAxisJointDirection))
    raise RtError("FUSION_API_ERROR", f"Неизвестный шарнир {kind}")


def _apply_limits(joint, limits: dict) -> None:
    if not limits:
        return
    motion = joint.jointMotion
    rotation = getattr(motion, "rotationLimits", None)
    if rotation is None:
        return
    if "min_deg" in limits:
        rotation.isMinimumValueEnabled = True
        rotation.minimumValue = float(limits["min_deg"]) * 3.141592653589793 / 180.0
    if "max_deg" in limits:
        rotation.isMaximumValueEnabled = True
        rotation.maximumValue = float(limits["max_deg"]) * 3.141592653589793 / 180.0


def _set_angle(motion, angle_deg: float, occurrence=None, base=None) -> None:
    import math

    if hasattr(motion, "rotationValue"):
        try:
            motion.rotationValue = math.radians(angle_deg)
        except Exception:
            pass
    # rotationValue is stored on the joint but does not move the occurrence on this build.
    if occurrence is not None and base is not None:
        _spin_occurrence(occurrence, base, angle_deg)


def _spin_occurrence(occurrence, base, angle_deg: float) -> None:
    import math

    import adsk.core

    spin = adsk.core.Matrix3D.create()
    spin.setToRotation(
        math.radians(angle_deg),
        adsk.core.Vector3D.create(0.0, 0.0, 1.0),
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
    )
    combined = _matrix_copy(base)
    combined.transformBy(spin)
    occurrence.transform = combined


def _matrix_copy(matrix):
    import adsk.core

    copy = adsk.core.Matrix3D.create()
    copy.setWithArray(list(matrix.asArray()))
    return copy


def _occurrence_bodies(occurrence) -> list:
    bodies = occurrence.bRepBodies
    if bodies.count == 0:
        bodies = occurrence.component.bRepBodies
    return [bodies.item(index) for index in range(bodies.count)]


def _occurrence(component, name: str):
    for index in range(component.occurrences.count):
        occurrence = component.occurrences.item(index)
        if occurrence.component.name == name or occurrence.name == name:
            return occurrence
        found = _occurrence(occurrence.component, name)
        if found is not None:
            return found
    return None


def _bodies(design, names: list[str]):
    from fca_rt.features import _walk_bodies

    for body in _walk_bodies(design.rootComponent):
        if not names or body.name in names:
            yield body


def _proxy_bodies(design, names: list[str]):
    root = design.rootComponent
    for index in range(root.bRepBodies.count):
        body = root.bRepBodies.item(index)
        if not names or body.name in names:
            yield body
    for occurrence in _iter_occurrences(root):
        yielded = False
        for index in range(occurrence.bRepBodies.count):
            proxy = occurrence.bRepBodies.item(index)
            label = _body_label(proxy)
            if not names or label in names:
                yielded = True
                yield proxy
        if yielded:
            continue
        for index in range(occurrence.component.bRepBodies.count):
            native = occurrence.component.bRepBodies.item(index)
            if names and native.name not in names:
                continue
            try:
                yield native.createForAssemblyContext(occurrence)
            except Exception:
                yield native


def _iter_occurrences(component):
    for index in range(component.occurrences.count):
        occurrence = component.occurrences.item(index)
        yield occurrence
        yield from _iter_occurrences(occurrence.component)


def _body_label(body) -> str:
    native = getattr(body, "nativeObject", None)
    if native is not None and getattr(native, "name", ""):
        return str(native.name)
    return str(getattr(body, "name", "") or "")


def _in_context(occurrence, entity):
    if getattr(entity, "assemblyContext", None) is not None:
        return entity
    try:
        return entity.createForAssemblyContext(occurrence)
    except Exception:
        return entity


def _point_geometry(occurrence):
    import adsk.fusion

    for body in _occurrence_bodies(occurrence):
        if body.vertices.count == 0:
            continue
        vertex = _in_context(occurrence, body.vertices.item(0))
        try:
            return adsk.fusion.JointGeometry.createByPoint(vertex)
        except Exception:
            continue
    return None


def _cylinder_geometry(occurrence):
    import adsk.core
    import adsk.fusion

    for body in _occurrence_bodies(occurrence):
        for face in body.faces:
            geom = face.geometry
            if isinstance(geom, adsk.core.Cylinder):
                return adsk.fusion.JointGeometry.createByCylinderOrConeFace(
                    _in_context(occurrence, face),
                    adsk.fusion.JointQuadrantAngleTypes.StartJointQuadrantAngleType,
                    adsk.fusion.JointKeyPointTypes.MiddleKeyPoint,
                )
    return None


def _planar_geometry(occurrence):
    import adsk.core
    import adsk.fusion

    bodies = _occurrence_bodies(occurrence)
    if not bodies:
        return None
    body = bodies[0]
    for face in body.faces:
        if isinstance(face.geometry, adsk.core.Plane):
            contextual = _in_context(occurrence, face)
            if contextual.edges.count == 0:
                continue
            try:
                return adsk.fusion.JointGeometry.createByPlanarFace(
                    contextual,
                    contextual.edges.item(0),
                    adsk.fusion.JointKeyPointTypes.CenterKeyPoint,
                )
            except Exception:
                continue
    return None
