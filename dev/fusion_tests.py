"""Regression test for the Counterbore Bridge feature. Runs inside Fusion.

Builds a new, unsaved fixture document and creates bridges through the add-in's own
feature code (not the dialog):

- a block rotated 37 degrees about a skewed axis (root body), with five counterbores:
  round/round, hex/hex rotated 15, round/square rotated 20, rectangle/slot, and a round
  one on the underside
- the same block in a transformed sub-component (picked as proxies, like in the UI)
- the same block in a nested component, all five floors in one feature
- small round blocks with a sketch line at 30 degrees as the bridge reference, in the
  root and in the sub-component
- a small hex block with a manual layer count

It checks the automatic layer count per hole shape, then edits every feature's
parameters and an upstream pocket depth, checks that everything recomputes to the
same result in every context, and that no sliver faces are left. The document is left open for inspection. Previous
fixture documents are closed without saving.

Run inside Fusion with app and adsk in scope; the outcome is in the result dict.
"""

import math
import sys
import traceback

import adsk.core
import adsk.fusion

P = adsk.core.Point3D.create
V = adsk.core.Vector3D.create
FO = adsk.fusion.FeatureOperations
TAG = ("CounterboreBridgingTests", "fixture")
HEALTHY = adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState


def addin_module(suffix):
    return next(m for k, m in sys.modules.items() if k.endswith("CounterboreBridging_py." + suffix))


feature = addin_module("commands.counterboreBridge.feature")
geometry = addin_module("commands.counterboreBridge.geometry")
result = globals().get("result", {})
report = result
failures = report.setdefault("failures", [])


def check(condition, message):
    if not condition:
        failures.append(message)
    return condition


# ---------------------------------------------------------------- fixture

POCKETS = [  # name, x, side; the floor is probed at (x + 0.45, 1, z)
    ("round/round", 1, "top"),
    ("hex/hex15", 3, "top"),
    ("round/square20", 5, "top"),
    ("rect/slot", 7, "top"),
    ("bottom round/round", 9, "bottom"),
]


def _polygon(sketch, points):
    for i in range(len(points)):
        sketch.sketchCurves.sketchLines.addByTwoPoints(points[i], points[(i + 1) % len(points)])


def _regular(cx, cy, circum_r, count, rot_deg):
    return [
        P(cx + circum_r * math.cos(math.radians(rot_deg + 360 * i / count)),
          cy + circum_r * math.sin(math.radians(rot_deg + 360 * i / count)), 0)
        for i in range(count)
    ]


def _rect(cx, cy, length, width, rot_deg):
    a = math.radians(rot_deg)
    return [
        P(cx + math.cos(a) * x - math.sin(a) * y, cy + math.sin(a) * x + math.cos(a) * y, 0)
        for x, y in ((-length / 2, -width / 2), (length / 2, -width / 2), (length / 2, width / 2), (-length / 2, width / 2))
    ]


def _cut(component, sketch, distance=None):
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    if distance is None:
        cut_input = component.features.extrudeFeatures.createInput(profiles, FO.CutFeatureOperation)
        cut_input.setOneSideExtent(
            adsk.fusion.ThroughAllExtentDefinition.create(), adsk.fusion.ExtentDirections.PositiveExtentDirection
        )
        return component.features.extrudeFeatures.add(cut_input)
    return component.features.extrudeFeatures.addSimple(profiles, adsk.core.ValueInput.createByReal(distance), FO.CutFeatureOperation)


def _plane_at(component, z):
    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(component.xYConstructionPlane, adsk.core.ValueInput.createByReal(z))
    return component.constructionPlanes.add(plane_input)


def build_block(component, name):
    """10 x 2 x 1 cm block with the five counterbores. Returns the top pocket cut feature."""
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(P(0, 0, 0), P(10, 2, 0))
    block = component.features.extrudeFeatures.addSimple(
        sketch.profiles.item(0), adsk.core.ValueInput.createByReal(1), FO.NewBodyFeatureOperation
    )
    block.bodies.item(0).name = name
    top = component.sketches.add(_plane_at(component, 1))
    top.sketchCurves.sketchCircles.addByCenterRadius(P(1, 1, 0), 0.5)
    _polygon(top, _regular(3, 1, 0.5 / math.cos(math.radians(30)), 6, 0))
    top.sketchCurves.sketchCircles.addByCenterRadius(P(5, 1, 0), 0.5)
    _polygon(top, _rect(7, 1, 1.2, 0.8, 10))
    top_pockets = _cut(component, top, -0.3)
    bottom = component.sketches.add(component.xYConstructionPlane)
    bottom.sketchCurves.sketchCircles.addByCenterRadius(P(9, 1, 0), 0.5)
    _cut(component, bottom, 0.3)
    holes = component.sketches.add(component.xYConstructionPlane)
    holes.sketchCurves.sketchCircles.addByCenterRadius(P(1, 1, 0), 0.275)
    _polygon(holes, _regular(3, 1, 0.275 / math.cos(math.radians(30)), 6, 15))
    _polygon(holes, _rect(5, 1, 0.45, 0.45, 20))
    _polygon(holes, _rect(7, 1, 0.7, 0.3, 10))
    holes.sketchCurves.sketchCircles.addByCenterRadius(P(9, 1, 0), 0.275)
    _cut(component, holes)
    return top_pockets


def _matrix(angle_deg, axis, translation):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(angle_deg), V(*axis), P(0, 0, 0))
    m.translation = V(*translation)
    return m


def close_fixtures():
    for doc in list(app.documents):
        design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        if doc.dataFile is None and design is not None and design.attributes.itemByName(*TAG) is not None:
            doc.close(False)


def build_fixture():
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.attributes.add(TAG[0], TAG[1], "1")
    root = design.rootComponent

    skew = _matrix(37, (1, 2, 3), (-2, 5, 3))
    root_pockets = build_block(root, "Skewed")
    bodies = adsk.core.ObjectCollection.create()
    bodies.add(root.bRepBodies.itemByName("Skewed"))
    move_input = root.features.moveFeatures.createInput2(bodies)
    move_input.defineAsFreeMove(skew)
    root.features.moveFeatures.add(move_input)

    sub = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    sub.component.name = "Sub"
    build_block(sub.component, "SubBlock")
    sub.transform2 = _matrix(-120, (-1, 0.3, 0.5), (4, -6, -2))

    outer = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    outer.component.name = "Outer"
    inner = outer.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    inner.component.name = "Inner"
    build_block(inner.component, "NestedBlock")
    outer.transform2 = _matrix(70, (0, 1, 0), (0, 8, 0))
    inner = inner.createForAssemblyContext(outer)
    inner.transform2 = _matrix(25, (0, 0, 1), (1, 1, 1))
    design.snapshots.add()  # capture the occurrence positions

    return design, {
        "root": root, "sub": sub, "inner": inner, "skew": skew, "root_pockets": root_pockets,
        # Round counterbores with a sketch line at 30 degrees, in the root and in the sub-component.
        "reference": build_small_block(root, "RefBlock", "round"),
        "sub_reference": build_small_block(sub.component, "SubRefBlock", "round").createForAssemblyContext(sub),
        # Hex counterbore for the manual layer count.
        "manual": build_small_block(root, "ManualHex", "hex", y0=-7),
        # Hex counterbore whose bridges follow a reference line instead of the hex flats.
        "hex_reference": build_small_block(root, "RefHex", "hex", y0=-10),
    }


def build_small_block(component, name, shape, y0=-4):
    """2 x 2 x 1 cm block at (0, y0) with one counterbore; returns a sketch line at 30 degrees."""
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(P(0, y0, 0), P(2, y0 + 2, 0))
    block = component.features.extrudeFeatures.addSimple(
        sketch.profiles.item(0), adsk.core.ValueInput.createByReal(1), FO.NewBodyFeatureOperation
    )
    block.bodies.item(0).name = name
    pocket = component.sketches.add(_plane_at(component, 1))
    hole = component.sketches.add(component.xYConstructionPlane)
    if shape == "round":
        pocket.sketchCurves.sketchCircles.addByCenterRadius(P(1, y0 + 1, 0), 0.5)
        hole.sketchCurves.sketchCircles.addByCenterRadius(P(1, y0 + 1, 0), 0.275)
    else:
        _polygon(pocket, _regular(1, y0 + 1, 0.5 / math.cos(math.radians(30)), 6, 0))
        _polygon(hole, _regular(1, y0 + 1, 0.275 / math.cos(math.radians(30)), 6, 15))
    _cut(component, pocket, -0.3)
    _cut(component, hole)
    lines = component.sketches.add(component.xYConstructionPlane)
    return lines.sketchCurves.sketchLines.addByTwoPoints(
        P(0, y0 - 0.5, 0), P(math.cos(math.radians(30)), y0 - 0.5 + math.sin(math.radians(30)), 0)
    )


def floor(fx, context, x, side):
    """Floor face of a pocket, picked like a user would (proxy in assemblies)."""
    z = 0.7 if side == "top" else 0.3
    local = P(x + 0.45, 1, z)
    if context == "root":
        component, point = fx["root"], local.copy()
        point.transformBy(fx["skew"])
    else:
        occurrence = fx[context]
        component, point = occurrence.component, local
    hits = component.findBRepUsingPoint(point, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 1e-4, False)
    for i in range(hits.count):
        face = hits.item(i)
        if face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType and geometry.is_floor(face):
            return face if context == "root" else face.createForAssemblyContext(fx[context])
    return None


def small_floor(component, y0=-4, occurrence=None):
    hits = component.findBRepUsingPoint(P(1.45, y0 + 1, 0.7), adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 1e-4, False)
    face = next((hits.item(i) for i in range(hits.count) if geometry.is_floor(hits.item(i))), None)
    return face.createForAssemblyContext(occurrence) if face is not None and occurrence else face


def volume(body):
    return body.volume * 1000  # mm3


def layer_count(face, layers, height=0.02, reference=None):
    """Number of layers the tool for a floor spans (its depth below the floor / layer height)."""
    floor_face = feature.native(face)
    tool = geometry.tool_body(floor_face, 0, layers, height, reference)
    n, u, v = geometry.floor_frame(floor_face)
    return app.measureManager.getOrientedBoundingBox(tool, u, v).height / height


def slivers(body, limit_mm2=0.001):
    return [round(f.area * 100, 6) for f in body.faces if f.area * 100 < limit_mm2]


# ---------------------------------------------------------------- run

def run():
    close_fixtures()
    design, fx = build_fixture()
    settings = feature.Settings(layer_height="0.2 mm", angle="0 deg")  # automatic layers
    created = []

    # Automatic layer count: one layer per straight-edge direction of the hole.
    expected_layers = {"round/round": 2, "hex/hex15": 3, "round/square20": 2, "rect/slot": 2, "bottom round/round": 2}
    counts = {}
    for name, x, side in POCKETS:
        face = floor(fx, "root", x, side)
        if face is not None:
            counts[name] = round(layer_count(face, None), 3)
            check(abs(counts[name] - expected_layers[name]) < 1e-3, f"{name}: {counts[name]} layers, expected {expected_layers[name]}")
    report["auto_layers"] = counts
    manual_floor = small_floor(fx["root"], y0=-7)
    if check(manual_floor is not None, "manual: floor not found"):
        manual_count = layer_count(manual_floor, 4)
        check(abs(manual_count - 4) < 1e-3, f"manual: {manual_count} layers, expected 4")
        created.append(feature.create([manual_floor], feature.Settings("0.2 mm", "0 deg", 4)))

    # Root (skewed) and sub-component: one feature per counterbore, volume per counterbore.
    removed = {}
    for context, body_name in (("root", "Skewed"), ("sub", "SubBlock")):
        component = fx["root"] if context == "root" else fx[context].component
        for name, x, side in POCKETS:
            face = floor(fx, context, x, side)
            if not check(face is not None, f"{context} {name}: floor not found"):
                continue
            before = volume(component.bRepBodies.itemByName(body_name))
            try:
                created.append(feature.create([face], settings))
                removed[(context, name)] = before - volume(component.bRepBodies.itemByName(body_name))
            except Exception:
                check(False, f"{context} {name}: " + traceback.format_exc().strip().splitlines()[-1])
    for name, _, _ in POCKETS:
        a, b = removed.get(("root", name)), removed.get(("sub", name))
        if a is not None and b is not None:
            check(a > 0 and abs(a - b) < 1e-4, f"{name}: removed {a:.6f} mm3 in root vs {b:.6f} in sub")
    report["removed_mm3"] = {name: round(removed.get(("root", name), -1), 4) for name, _, _ in POCKETS}

    # Nested: all five floors in one feature.
    nested_body = fx["inner"].component.bRepBodies.itemByName("NestedBlock")
    before = volume(nested_body)
    faces = [floor(fx, "inner", x, side) for _, x, side in POCKETS]
    if check(all(faces), "nested: floor not found"):
        groups = feature.group_by_body(faces)
        check(len(groups) == 1, f"nested: grouped into {len(groups)} bodies")
        created.append(feature.create(faces, settings))
        total = before - volume(fx["inner"].component.bRepBodies.itemByName("NestedBlock"))
        expected = sum(removed.get(("root", name), 0) for name, _, _ in POCKETS)
        check(abs(total - expected) < 1e-4, f"nested: removed {total:.6f} mm3, expected {expected:.6f}")

    # Reference: first bridges along the 30 degree sketch line, in the root and in the
    # transformed sub-component (floor and line picked as proxies).
    # The hex case checks that a reference overrides the hex flats' directions.
    reference_cases = {
        "root": (small_floor(fx["root"]), fx["reference"], lambda: fx["root"].bRepBodies.itemByName("RefBlock"), -3),
        "sub": (small_floor(fx["sub"].component, occurrence=fx["sub"]), fx["sub_reference"],
                lambda: fx["sub"].component.bRepBodies.itemByName("SubRefBlock"), -3),
        "hex": (small_floor(fx["root"], y0=-10), fx["hex_reference"],
                lambda: fx["root"].bRepBodies.itemByName("RefHex"), -9),
    }

    def probe(case, angle_deg):
        a = math.radians(angle_deg)
        centre_y = reference_cases[case][3]
        return reference_cases[case][2]().pointContainment(P(1 + 0.4 * math.cos(a), centre_y + 0.4 * math.sin(a), 0.69))

    hex_floor = reference_cases["hex"][0]
    if hex_floor is not None:
        line_direction = geometry.direction_of(fx["hex_reference"])
        check(abs(layer_count(hex_floor, None, reference=line_direction) - 3) < 1e-3,
              "reference hex: expected 3 layers with a reference")
        native_hex = feature.native(hex_floor)
        check(not geometry.angle_matters(native_hex, None, False), "angle should not matter: hex, auto, no reference")
        check(geometry.angle_matters(native_hex, None, True), "angle should matter: hex with reference")
        check(geometry.angle_matters(native_hex, 2, False), "angle should matter: manual layers")
        check(geometry.angle_matters(feature.native(reference_cases["root"][0]), None, False),
              "angle should matter: round hole")

    for case, (ref_floor, line, _, _) in reference_cases.items():
        if check(ref_floor is not None, f"reference {case}: floor not found"):
            created.append(feature.create([ref_floor], feature.Settings("0.2 mm", "0 deg", None, line)))
            check(probe(case, 30) == adsk.fusion.PointContainment.PointOutsidePointContainment,
                  f"reference {case}: no cut along the 30 degree reference")
            check(probe(case, 120) == adsk.fusion.PointContainment.PointInsidePointContainment,
                  f"reference {case}: unexpected cut across the reference")

    # Timeline: one node per feature, nothing loose.
    loose = [
        design.timeline.item(i).name for i in range(design.timeline.count)
        if design.timeline.item(i).entity is not None
        and design.timeline.item(i).entity.objectType.split("::")[-1] in ("BaseFeature", "CombineFeature")
    ]
    check(not loose, f"loose base/combine features in the timeline: {loose}")
    check_health(created, "after creation")

    # Recompute 1: edit every feature's parameters.
    feature.compute_log.clear()
    for f in created:
        f.parameters.itemById("angle").expression = "15 deg"
        f.parameters.itemById("layerHeight").expression = "0.4 mm"
    report["edit_computes"] = _summarise(feature.compute_log)
    check(all(e.get("ok") for e in feature.compute_log), "compute failed after parameter edit")
    check_health(created, "after parameter edit")
    volumes = {
        "root": volume(fx["root"].bRepBodies.itemByName("Skewed")),
        "sub": volume(fx["sub"].component.bRepBodies.itemByName("SubBlock")),
        "nested": volume(fx["inner"].component.bRepBodies.itemByName("NestedBlock")),
    }
    check(max(volumes.values()) - min(volumes.values()) < 1e-3, f"volumes differ after parameter edit: {volumes}")
    report["volumes_after_edit_mm3"] = {k: round(v, 4) for k, v in volumes.items()}
    for case, (ref_floor, _, _, _) in reference_cases.items():
        if ref_floor is not None:
            check(probe(case, 45) == adsk.fusion.PointContainment.PointOutsidePointContainment,
                  f"reference {case}: no cut along reference + 15 degrees after edit")
            check(probe(case, 135) == adsk.fusion.PointContainment.PointInsidePointContainment,
                  f"reference {case}: unexpected cut across reference + 15 degrees after edit")

    # Recompute 2: deeper top pockets upstream (root block only). The rect/slot bridges run
    # along the slot (10 degrees; automatic layers ignore the angle) and must move down with the floor.
    def rect_probe():
        a = math.radians(10)
        point = P(7 + 0.5 * math.cos(a), 1 + 0.5 * math.sin(a), 0.58)
        point.transformBy(fx["skew"])
        return fx["root"].bRepBodies.itemByName("Skewed").pointContainment(point)

    check(rect_probe() == adsk.fusion.PointContainment.PointInsidePointContainment,
          "upstream: material missing below the original bridges")
    feature.compute_log.clear()
    extent = adsk.fusion.DistanceExtentDefinition.cast(fx["root_pockets"].extentOne)
    extent.distance.expression = "-4 mm"
    report["upstream_computes"] = _summarise(feature.compute_log)
    check(all(e.get("ok") for e in feature.compute_log), "compute failed after upstream change")
    check_health(created, "after upstream change")
    check(rect_probe() == adsk.fusion.PointContainment.PointOutsidePointContainment,
          "upstream: bridges did not follow the deeper counterbore")

    # No micro faces left by strips that are almost, but not exactly, flush with a hole edge.
    bodies = [
        fx["root"].bRepBodies.itemByName("Skewed"), fx["sub"].component.bRepBodies.itemByName("SubBlock"),
        fx["inner"].component.bRepBodies.itemByName("NestedBlock"), fx["root"].bRepBodies.itemByName("ManualHex"),
    ]
    for body in bodies:
        check(not slivers(body), f"{body.name}: sliver faces (mm2) {slivers(body)}")

    report["features"] = len(created)
    report["passed"] = not failures

    viewport = app.activeViewport
    camera = viewport.camera
    camera.isSmoothTransition = False
    camera.viewOrientation = adsk.core.ViewOrientations.IsoTopRightViewOrientation
    viewport.camera = camera
    viewport.fit()


def check_health(features, when):
    for f in features:
        check(
            f.healthState == HEALTHY,
            f"{f.parentComponent.name}/{f.name} unhealthy {when}: {f.healthState} {f.errorOrWarningMessage}",
        )


def _summarise(log):
    sources = [s for e in log for s in e.get("floors", [])]
    errors = [e for e in log if "error" in e]
    return {
        "computes": len(log),
        "errors": [f"{e['feature']}: {e['error']}" for e in errors[:3]] + [f"... {len(errors)} errors"],
        "first_trace": errors[0].get("trace") if errors else None,
        "floors_via_dependency": sources.count("dependency"),
        "floors_via_fingerprint": sources.count("fingerprint"),
    }


try:
    run()
except Exception:
    failures.append("test crashed: " + traceback.format_exc())
    report["passed"] = False
