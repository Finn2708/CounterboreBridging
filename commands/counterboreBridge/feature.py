"""The Counterbore Bridge custom feature: creation, recompute and update.

A Counterbore Bridge groups a base feature (the bridge tool body, built by
geometry.tool_body) and a combine feature that cuts it from the part. Its inputs are
stored on the custom feature itself:

- parameters "layerHeight" and "angle" (editable in the Parameters dialog)
- dependencies "floor0".."floorN" (the counterbore floors) and optionally "reference"
- named values "layers" ("auto" or a number) and "floor0".."floorN" (fingerprints
  of the floors)

Fusion's Custom Feature API is a preview. On recompute it sometimes resolves a floor
dependency to the wrong face (a neighbouring counterbore, or a fragment of a floor).
Every resolved floor is therefore checked against its fingerprint and, if it does not
match, looked up again in the cut body. If that fails too, the feature reports an error
instead of cutting the wrong place.
"""

import traceback

import adsk.core
import adsk.fusion

from . import geometry
from .strings import tr

DEFINITION_ID = "FinnWeithoff_CounterboreBridge"

app = adsk.core.Application.get()
_definition: adsk.fusion.CustomFeatureDefinition = None

# Outcome of the most recent computes, newest last (for diagnostics and the test script).
compute_log = []


class Settings:
    def __init__(self, layer_height="0.2 mm", angle="0 deg", layers=None, reference=None):
        self.layer_height = layer_height  # expression
        self.angle = angle  # expression
        self.layers = layers  # None: one layer per straight-edge direction of each hole
        self.reference = reference  # straight edge, sketch line or construction axis, or None


def define(name: str, icon_folder: str, edit_command_id: str) -> adsk.fusion.CustomFeatureDefinition:
    """Create the custom feature definition. Call once from the add-in's run()."""
    global _definition
    _definition = adsk.fusion.CustomFeatureDefinition.create(DEFINITION_ID, name, icon_folder)
    _definition.editCommandId = edit_command_id
    return _definition


def native(entity):
    return entity.nativeObject if entity is not None and entity.nativeObject else entity


def group_by_body(faces):
    """Split selected floor faces into lists that share the same (native) body."""
    groups = []
    for face in faces:
        for group in groups:
            if native(group[0]).body == native(face).body:
                group.append(face)
                break
        else:
            groups.append([face])
    return groups


def create(floors, settings: Settings) -> adsk.fusion.CustomFeature:
    """Create one Counterbore Bridge for floors that all belong to the same body.

    floors are the faces as selected (proxies when picked in an assembly).
    """
    body = native(floors[0]).body
    component = body.parentComponent
    design = adsk.fusion.Design.cast(app.activeProduct)
    tool = _tool(floors, settings.layer_height, settings.angle, settings.layers, settings.reference)

    base = component.features.baseFeatures.add()
    base.startEdit()
    component.bRepBodies.add(tool, base)
    base.finishEdit()

    # The floors are cut by the combine below. Fusion only accepts them as dependencies
    # while they are intact, so the custom feature first wraps just the base feature
    # and is extended to the combine afterwards.
    feature_input = component.features.customFeatures.createInput(_definition)
    feature_input.addCustomParameter(
        "layerHeight", tr("Layer height"), adsk.core.ValueInput.createByString(settings.layer_height), "mm", True
    )
    feature_input.addCustomParameter(
        "angle", tr("Angle"), adsk.core.ValueInput.createByString(settings.angle), "deg", True
    )
    for i, floor in enumerate(floors):
        feature_input.addDependency(f"floor{i}", floor)
    if settings.reference is not None:
        feature_input.addDependency("reference", settings.reference)
    feature_input.setStartAndEndFeatures(base, base)
    feature = component.features.customFeatures.add(feature_input)
    _store_settings(feature, floors, settings.layers)

    tools = adsk.core.ObjectCollection.create()
    tools.add(base.bodies.item(0))
    combine_input = component.features.combineFeatures.createInput(body, tools)
    combine_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combine = component.features.combineFeatures.add(combine_input)

    feature.timelineObject.rollTo(True)
    feature.setStartAndEndFeatures(base, combine)
    feature.timelineObject.rollTo(False)
    if design.timeline.markerPosition < design.timeline.count:
        design.timeline.moveToEnd()
    return feature


def update(feature: adsk.fusion.CustomFeature, floors, settings: Settings):
    """Apply new inputs to an existing feature. The timeline must be rolled to just before it."""
    params = feature.parameters
    params.itemById("layerHeight").expression = settings.layer_height
    params.itemById("angle").expression = settings.angle
    feature.dependencies.deleteAll()
    for i, floor in enumerate(floors):
        feature.dependencies.add(f"floor{i}", floor)
    if settings.reference is not None:
        feature.dependencies.add("reference", settings.reference)
    names = feature.customNamedValues
    for i in range(names.count - 1, -1, -1):
        names.remove(names.idByIndex(i))
    _store_settings(feature, floors, settings.layers)
    tool = _tool(floors, settings.layer_height, settings.angle, settings.layers, settings.reference)
    _replace_tool(feature, tool)


def read_settings(feature: adsk.fusion.CustomFeature) -> Settings:
    """Current settings of a feature, for the edit dialog (floors: see resolved_floors)."""
    reference = feature.dependencies.itemById("reference")
    return Settings(
        layer_height=feature.parameters.itemById("layerHeight").expression,
        angle=feature.parameters.itemById("angle").expression,
        layers=_layers(feature),
        reference=reference.entity if reference is not None else None,
    )


def cut_body(feature: adsk.fusion.CustomFeature):
    """The body the feature cuts (native), from its floors; None if they cannot be resolved."""
    try:
        floors = resolved_floors(feature)
    except geometry.BridgeError:
        return None
    return floors[0][1].body if floors else None


def resolved_floors(feature: adsk.fusion.CustomFeature, how: list = None):
    """The feature's floors in the current timeline state, as (selected, native) pairs.

    selected is in the context the floor was picked in (a proxy for assemblies), native
    is the face in its component. Raises BridgeError if a floor cannot be found.
    """
    floors = []
    for i in range(_floor_count(feature)):
        print_ = feature.customNamedValues.value(f"floor{i}")
        dependency = feature.dependencies.itemById(f"floor{i}")
        selected = dependency.entity if dependency is not None else None
        floor = native(selected)
        if geometry.matches(floor, print_):
            source = "dependency"
        else:
            # The combine's target body cannot be read during a compute, so search the
            # body Fusion resolved first, then the other bodies of the component.
            bodies = [floor.body] if floor is not None else []
            bodies += [body for body in feature.parentComponent.bRepBodies if body not in bodies]
            floor = next((f for f in map(lambda b: geometry.find_floor(b, print_), bodies) if f), None)
            if floor is None:
                raise geometry.BridgeError("Counterbore floor {} not found.", i + 1)
            context = getattr(selected, "assemblyContext", None) if selected is not None else None
            selected = floor.createForAssemblyContext(context) if context is not None else floor
            source = "fingerprint"
        if how is not None:
            how.append(source)
        floors.append((selected, floor))
    return floors


def on_compute(args: adsk.fusion.CustomFeatureEventArgs):
    """Handler for the customFeatureCompute event."""
    feature = args.customFeature
    if _combine(feature) is None:
        return  # still being created: create() adds the combine after customFeatures.add()
    entry = {"feature": feature.name, "floors": []}
    compute_log.append(entry)
    del compute_log[:-50]
    try:
        reference = feature.dependencies.itemById("reference")
        layer_height = feature.parameters.itemById("layerHeight").value
        angle = feature.parameters.itemById("angle").value
        layers = _layers(feature)
        tool = None
        for selected, floor in resolved_floors(feature, entry["floors"]):
            direction = _native_direction(reference.entity, selected) if reference is not None else None
            tool = _union(tool, geometry.tool_body(floor, angle, layers, layer_height, direction))
        _replace_tool(feature, tool)
        entry["ok"] = True
    except Exception as error:  # report in the timeline rather than raising into Fusion
        entry["error"] = str(error)
        entry["trace"] = traceback.format_exc(limit=-3)
        try:
            args.computeStatus.statusMessages.addError("DRPOINT_COMPUTE_FAILED", "")
        except Exception as status_error:
            entry["status_error"] = str(status_error)


def _tool(floors, layer_height, angle, layers, reference):
    units = adsk.fusion.Design.cast(app.activeProduct).unitsManager
    height = units.evaluateExpression(layer_height, "cm")
    rotation = units.evaluateExpression(angle, "rad")
    tool = None
    for floor in floors:
        direction = _native_direction(reference, floor) if reference is not None else None
        part = geometry.tool_body(native(floor), rotation, layers, height, direction)
        tool = _union(tool, part)
    return tool


def _native_direction(reference, floor):
    """Reference direction expressed in the coordinate space of the floor's component.

    Both are as selected: proxies (and root entities) are in assembly space already.
    """
    direction = geometry.direction_of(reference)
    to_assembly = _context_transform(floor)
    if to_assembly is not None:
        to_native = to_assembly.copy()
        to_native.invert()
        direction.transformBy(to_native)
    return direction


def _context_transform(entity):
    context = getattr(entity, "assemblyContext", None)
    return context.transform2 if context is not None else None


def _union(tool, part):
    if tool is None:
        return part
    adsk.fusion.TemporaryBRepManager.get().booleanOperation(tool, part, adsk.fusion.BooleanTypes.UnionBooleanType)
    return tool


def _store_settings(feature, floors, layers):
    names = feature.customNamedValues
    names.addOrSetValue("layers", "auto" if layers is None else str(layers))
    names.addOrSetValue("floorCount", str(len(floors)))
    for i, floor in enumerate(floors):
        names.addOrSetValue(f"floor{i}", geometry.fingerprint(native(floor)))


def _layers(feature):
    value = feature.customNamedValues.value("layers")
    return None if value == "auto" else int(value)


def _floor_count(feature):
    return int(feature.customNamedValues.value("floorCount"))


def _base(feature):
    return next(f for f in feature.features if f.objectType == adsk.fusion.BaseFeature.classType())


def _combine(feature):
    return next((f for f in feature.features if f.objectType == adsk.fusion.CombineFeature.classType()), None)


def _replace_tool(feature, tool):
    base = _base(feature)
    base.startEdit()
    base.updateBody(base.bodies.item(0), tool)
    base.finishEdit()
