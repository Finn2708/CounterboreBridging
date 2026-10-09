"""Tool body construction for counterbore bridges.

Everything is derived from the selected floor face: its outward normal, its outer
loop (the counterbore outline) and its inner loops (the holes). No world axes are
used, so the result does not depend on how the part is oriented.

Each hole gets one cut layer per bridge direction. Layer k removes the part of the
counterbore outline that lies inside the strips of layers 1..k, where a strip covers
the hole's extent across its bridge direction. Layer 1 is next to the counterbore.

By default there is one layer per direction of the hole's straight edges, running
along those edges, so a hex hole gets three layers and the last one ends exactly on
the hole outline. Holes without at least two edge directions (round holes, slots) get
two layers at 90 degrees. A picked reference overrides the directions: the layers are
then spread evenly from the reference, and the hole shape only sets their number.
"""

import json
import math

import adsk.core
import adsk.fusion

# Strips are this much wider than a curved hole outline on each side, so that strip
# faces are not tangent to the hole (cm). Sides that lie on a straight hole edge get none.
STRIP_GAP = 1e-4
# Chord tolerance when sampling hole outlines (cm).
STROKE_TOLERANCE = 1e-5
# Edge directions closer than this are treated as one direction (radians).
ANGLE_TOLERANCE = math.radians(0.5)
# Holes with more edge directions than this (e.g. faceted circles) count as round.
MAX_AUTO_LAYERS = 6

_tbm = adsk.fusion.TemporaryBRepManager.get()


class BridgeError(Exception):
    """The selected geometry cannot be bridged.

    message is an English text with {} placeholders for values; the UI translates
    message and then fills in the values.
    """

    def __init__(self, message: str, *values):
        super().__init__(message.format(*values))
        self.message = message
        self.values = values


class Hole:
    """One inner loop of a floor face: sampled outline points and its straight edges."""

    def __init__(self, loop: adsk.fusion.BRepLoop):
        self.points = []
        self.lines = []  # (unit direction, start point)
        for edge in loop.edges:
            evaluator = edge.evaluator
            ok, start, end = evaluator.getParameterExtents()
            ok, strokes = evaluator.getStrokes(start, end, STROKE_TOLERANCE)
            self.points.extend(strokes)
            if isinstance(edge.geometry, adsk.core.Line3D):
                direction = edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
                direction.normalize()
                self.lines.append((direction, edge.startVertex.geometry))

    def edge_angles(self, u: adsk.core.Vector3D, v: adsk.core.Vector3D):
        """Distinct directions of the straight edges, as angles from u in [0, pi)."""
        angles = []
        for direction, _ in self.lines:
            angle = math.atan2(direction.dotProduct(v), direction.dotProduct(u)) % math.pi
            if math.pi - angle < ANGLE_TOLERANCE:
                angle = 0.0  # parallel to u, whichever way round the edge runs
            if not any(_angle_distance(angle, known) < ANGLE_TOLERANCE for known in angles):
                angles.append(angle)
        return sorted(angles)


def is_floor(face: adsk.fusion.BRepFace) -> bool:
    """A face can be bridged if it is planar and has at least one hole."""
    return (
        face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType
        and any(not loop.isOuter for loop in face.loops)
    )


def holes(face: adsk.fusion.BRepFace):
    return [Hole(loop) for loop in face.loops if not loop.isOuter]


def direction_of(entity) -> adsk.core.Vector3D:
    """Direction of a linear edge, sketch line or construction axis, in the entity's context."""
    if isinstance(entity, adsk.fusion.SketchLine):
        line = entity.worldGeometry
        return line.startPoint.vectorTo(line.endPoint)
    if isinstance(entity, adsk.fusion.ConstructionAxis):
        return entity.geometry.direction
    if isinstance(entity, adsk.fusion.BRepEdge) and isinstance(entity.geometry, adsk.core.Line3D):
        return entity.startVertex.geometry.vectorTo(entity.endVertex.geometry)
    raise BridgeError("The reference must be a straight edge, sketch line or construction axis.")


def floor_frame(face: adsk.fusion.BRepFace, reference: adsk.core.Vector3D = None):
    """Outward normal n and in-plane axes (u, v) of a floor face.

    u is the reference direction if given, otherwise the longest straight edge of the
    counterbore outline, then of the holes, then the face's own u direction.
    """
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    n.normalize()
    u = reference.copy() if reference else None
    if u is None:
        for outer in (True, False):
            lines = [
                edge
                for loop in face.loops
                if loop.isOuter == outer
                for edge in loop.edges
                if isinstance(edge.geometry, adsk.core.Line3D)
            ]
            if lines:
                longest = max(lines, key=lambda edge: edge.length)
                u = longest.startVertex.geometry.vectorTo(longest.endVertex.geometry)
                break
    if u is None:
        u = face.geometry.uDirection.copy()
    along_n = n.copy()
    along_n.scaleBy(u.dotProduct(n))
    u.subtract(along_n)
    if u.length < 1e-9:
        raise BridgeError("The reference is perpendicular to the counterbore floor.")
    u.normalize()
    return n, u, n.crossProduct(u)


def auto_layers(hole: Hole, u: adsk.core.Vector3D, v: adsk.core.Vector3D) -> int:
    """Automatic layer count: one per straight-edge direction, 2 for round holes and slots."""
    count = len(hole.edge_angles(u, v))
    return count if 2 <= count <= MAX_AUTO_LAYERS else 2


def bridge_angles(hole: Hole, u, v, angle: float, layers=None, follow_hole=True):
    """Bridge directions of the layers of one hole, as angles from u.

    layers None: auto_layers() layers. With follow_hole they run along the hole's
    straight edges (a slot's single direction plus its perpendicular); holes without
    straight edges, and all holes without follow_hole (a reference was picked), get
    evenly spread directions starting at angle. A number: that many layers, evenly
    spread over 180 degrees starting at angle.
    """
    if layers is None:
        edges = hole.edge_angles(u, v)
        if follow_hole and 2 <= len(edges) <= MAX_AUTO_LAYERS:
            return edges
        if follow_hole and len(edges) == 1:
            return [edges[0], edges[0] + math.pi / 2]
        layers = auto_layers(hole, u, v)
    return [angle + k * math.pi / layers for k in range(layers)]


def angle_matters(face: adsk.fusion.BRepFace, layers, has_reference: bool) -> bool:
    """Whether the angle setting changes the bridges of this floor."""
    if layers is not None or has_reference:
        return True
    n, u, v = floor_frame(face)
    return any(not 1 <= len(hole.edge_angles(u, v)) <= MAX_AUTO_LAYERS for hole in holes(face))


def tool_body(
    face: adsk.fusion.BRepFace,
    angle: float,
    layers,
    layer_height: float,
    reference: adsk.core.Vector3D = None,
) -> adsk.fusion.BRepBody:
    """Temporary body containing all bridge layers below one floor face.

    angle is in radians, layers None for automatic (see bridge_angles), layer_height
    in cm. The body is in the coordinate space of the face (pass native faces to get a
    body in component space).
    """
    if not is_floor(face):
        raise BridgeError("The counterbore floor must be planar and contain a hole.")
    if (layers is not None and layers < 1) or layer_height <= 0:
        raise BridgeError("Need at least one layer and a positive layer height.")
    n, u0, v0 = floor_frame(face, reference)

    # The counterbore outline, one layer thick: a box over the floor minus the part itself.
    bounds = adsk.core.Application.get().measureManager.getOrientedBoundingBox(face, u0, v0)
    centre = bounds.centerPoint.copy()
    centre.translateBy(_scaled(n, layer_height / 2))
    slab = _box(centre, u0, v0, bounds.length, bounds.width, layer_height)
    _tbm.booleanOperation(slab, _tbm.copy(face.body), adsk.fusion.BooleanTypes.DifferenceBooleanType)

    origin = face.pointOnFace
    span = 2 * max(bounds.length, bounds.width) + 1
    tool = None
    for hole in holes(face):
        strips = []
        for k, a in enumerate(bridge_angles(hole, u0, v0, angle, layers, reference is None), start=1):
            uk = _rotated(u0, n, a)
            vk = n.crossProduct(uk)
            strips.append(_strip(hole, origin, uk, vk, span))
            layer = _tbm.copy(slab)
            for strip in strips:
                _tbm.booleanOperation(layer, strip, adsk.fusion.BooleanTypes.IntersectionBooleanType)
            shift = adsk.core.Matrix3D.create()
            shift.translation = _scaled(n, -k * layer_height)
            _tbm.transform(layer, shift)
            if tool is None:
                tool = layer
            else:
                _tbm.booleanOperation(tool, layer, adsk.fusion.BooleanTypes.UnionBooleanType)
    return tool


def fingerprint(face: adsk.fusion.BRepFace) -> str:
    """Compact description of a floor face, used to check what Fusion resolves on recompute."""
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    n.normalize()
    found = []
    for hole in holes(face):
        points = hole.points
        cx = sum(p.x for p in points) / len(points)
        cy = sum(p.y for p in points) / len(points)
        cz = sum(p.z for p in points) / len(points)
        size = max(points[0].distanceTo(p) for p in points)
        found.append([cx, cy, cz, size])
    return json.dumps({"normal": [n.x, n.y, n.z], "holes": found})


def matches(face: adsk.fusion.BRepFace, print_: str) -> bool:
    """True if the face is a floor with the same orientation and holes in the same places.

    Hole positions are compared after projecting onto the face's plane, so a changed
    counterbore depth still matches, while the floor of a neighbouring counterbore or
    the opposite end of the same hole does not.
    """
    if face is None or not face.isValid or not is_floor(face):
        return False
    expected = json.loads(print_)
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    n.normalize()
    if n.dotProduct(adsk.core.Vector3D.create(*expected["normal"])) < 0.999:
        return False
    plane = face.geometry
    found = json.loads(fingerprint(face))["holes"]
    if len(found) != len(expected["holes"]):
        return False
    for x, y, z, size in expected["holes"]:
        target = plane.origin.vectorTo(adsk.core.Point3D.create(x, y, z))
        target.subtract(_scaled(plane.normal, target.dotProduct(plane.normal)))
        projected = plane.origin.copy()
        projected.translateBy(target)
        if not any(
            projected.distanceTo(adsk.core.Point3D.create(fx, fy, fz)) < max(0.25 * size, 1e-3)
            for fx, fy, fz, fsize in found
        ):
            return False
    return True


def find_floor(body: adsk.fusion.BRepBody, print_: str):
    """The face of body that matches a fingerprint, or None."""
    for face in body.faces:
        if face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType and matches(face, print_):
            return face
    return None


def _strip(hole: Hole, origin, uk, vk, span):
    """Box along uk covering the hole's extent across vk.

    A side gets STRIP_GAP of clearance unless a straight hole edge parallel to uk lies
    exactly on it; then the strip is flush with that edge, and the last layer of a
    polygonal hole ends exactly on the hole outline.
    """
    across = [origin.vectorTo(p).dotProduct(vk) for p in hole.points]
    low, high = min(across), max(across)
    flush = [
        origin.vectorTo(start).dotProduct(vk)
        for direction, start in hole.lines
        if abs(direction.dotProduct(vk)) < 1e-6
    ]
    if not any(abs(offset - low) < STROKE_TOLERANCE for offset in flush):
        low -= STRIP_GAP
    if not any(abs(offset - high) < STROKE_TOLERANCE for offset in flush):
        high += STRIP_GAP
    centre = origin.copy()
    centre.translateBy(_scaled(vk, (low + high) / 2))
    return _box(centre, uk, vk, span, high - low, span)


def _angle_distance(a, b):
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _box(centre, length_dir, width_dir, length, width, height):
    return _tbm.createBox(
        adsk.core.OrientedBoundingBox3D.create(centre, length_dir, width_dir, length, width, height)
    )


def _rotated(vector, axis, angle):
    rotation = adsk.core.Matrix3D.create()
    rotation.setToRotation(angle, axis, adsk.core.Point3D.create(0, 0, 0))
    result = vector.copy()
    result.transformBy(rotation)
    return result


def _scaled(vector, factor):
    result = vector.copy()
    result.scaleBy(factor)
    return result
