"""Create and edit commands for the Counterbore Bridge custom feature."""

import os

import adsk.core
import adsk.fusion

from ... import config
from ...lib import fusion360utils as futil
from . import feature, geometry
from .strings import tr

app = adsk.core.Application.get()
ui = app.userInterface

CREATE_ID = f"{config.COMPANY_NAME}_{config.ADDIN_NAME}_create"
EDIT_ID = f"{config.COMPANY_NAME}_{config.ADDIN_NAME}_edit"
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidModifyPanel"
COMMAND_BESIDE_ID = "FusionMoveCommand"
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "")

# Handlers of the running command; released when it is destroyed.
local_handlers = []
# The compute handler lives as long as the add-in.
_compute_handler = None
# State of a running edit: the feature and the timeline object to roll back to.
_edit = {}


def start():
    global _compute_handler
    create_def = ui.commandDefinitions.addButtonDefinition(
        CREATE_ID,
        tr("Counterbore Bridge"),
        tr("Adds bridging layers below counterbores, so they print without support."),
        ICON_FOLDER,
    )
    futil.add_handler(create_def.commandCreated, create_created)
    edit_def = ui.commandDefinitions.addButtonDefinition(EDIT_ID, tr("Edit Counterbore Bridge"), "", ICON_FOLDER)
    futil.add_handler(edit_def.commandCreated, edit_created)

    definition = feature.define(tr("Counterbore Bridge"), ICON_FOLDER, EDIT_ID)
    _compute_handler = futil.add_handler(definition.customFeatureCompute, feature.on_compute)

    panel = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
    panel.controls.addCommand(create_def, COMMAND_BESIDE_ID, False)


def stop():
    global _compute_handler
    if _compute_handler is not None and feature._definition is not None:
        feature._definition.customFeatureCompute.remove(_compute_handler)
        _compute_handler = None
    panel = ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.itemById(CREATE_ID)
    if control:
        control.deleteMe()
    for command_id in (CREATE_ID, EDIT_ID):
        definition = ui.commandDefinitions.itemById(command_id)
        if definition:
            definition.deleteMe()


# ---------------------------------------------------------------- dialog


def _add_inputs(inputs: adsk.core.CommandInputs, settings: feature.Settings):
    floors = inputs.addSelectionInput(
        "floors",
        tr("Counterbore floors"),
        tr("Select the floor faces of the counterbores (the faces with the hole)."),
    )
    floors.addSelectionFilter(adsk.core.SelectionCommandInput.PlanarFaces)
    floors.setSelectionLimits(1, 0)

    reference = inputs.addSelectionInput(
        "reference",
        tr("Reference"),
        tr("Optional: straight edge, sketch line or axis the first bridges run along, instead of the hole's edges."),
    )
    reference.addSelectionFilter(adsk.core.SelectionCommandInput.LinearEdges)
    reference.addSelectionFilter(adsk.core.SelectionCommandInput.SketchLines)
    reference.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionLines)
    reference.setSelectionLimits(0, 1)

    angle = inputs.addValueInput("angle", tr("Angle"), "deg", adsk.core.ValueInput.createByString(settings.angle))
    angle.tooltip = tr(
        "Rotates the bridges from the reference. Without a reference it only applies to round holes "
        "and manual layers, as other holes set their own directions."
    )
    units = adsk.fusion.Design.cast(app.activeProduct).unitsManager.defaultLengthUnits
    inputs.addValueInput(
        "layerHeight", tr("Layer height"), units, adsk.core.ValueInput.createByString(settings.layer_height)
    )
    auto = inputs.addBoolValueInput("autoLayers", tr("Layers from hole shape"), True, "", settings.layers is None)
    auto.tooltip = tr(
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. "
        "Round holes and slots get 2."
    )
    layers = inputs.addIntegerSpinnerCommandInput("layers", tr("Layers"), 1, 6, 1, settings.layers or 2)
    layers.isEnabled = settings.layers is not None


def _read_inputs(inputs: adsk.core.CommandInputs):
    floors_input: adsk.core.SelectionCommandInput = inputs.itemById("floors")
    reference_input: adsk.core.SelectionCommandInput = inputs.itemById("reference")
    floors = [floors_input.selection(i).entity for i in range(floors_input.selectionCount)]
    settings = feature.Settings(
        layer_height=inputs.itemById("layerHeight").expression,
        angle=inputs.itemById("angle").expression,
        layers=None if inputs.itemById("autoLayers").value else inputs.itemById("layers").value,
        reference=reference_input.selection(0).entity if reference_input.selectionCount else None,
    )
    return floors, settings


def input_changed(args: adsk.core.InputChangedEventArgs):
    if args.input.id == "autoLayers":
        args.inputs.itemById("layers").isEnabled = not args.input.value
    _update_angle_state(args.inputs)


def _update_angle_state(inputs: adsk.core.CommandInputs):
    """Grey out the angle when it would not change any of the selected bridges."""
    floors, settings = _read_inputs(inputs)
    inputs.itemById("angle").isEnabled = not floors or any(
        geometry.angle_matters(feature.native(floor), settings.layers, settings.reference is not None)
        for floor in floors
    )


def _connect(command: adsk.core.Command, **handlers):
    for event_name, callback in handlers.items():
        futil.add_handler(getattr(command, event_name), callback, local_handlers=local_handlers)


def pre_select(args: adsk.core.SelectionEventArgs):
    if args.activeInput.id == "floors":
        face = adsk.fusion.BRepFace.cast(args.selection.entity)
        args.isSelectable = face is not None and geometry.is_floor(feature.native(face))


def validate(args: adsk.core.ValidateInputsEventArgs):
    inputs = args.inputs
    layer_height = inputs.itemById("layerHeight")
    args.areInputsValid = (
        inputs.itemById("floors").selectionCount > 0 and layer_height.isValidExpression and layer_height.value > 0
    )


def destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
    _edit.clear()


# ---------------------------------------------------------------- create


def create_created(args: adsk.core.CommandCreatedEventArgs):
    _add_inputs(args.command.commandInputs, feature.Settings())
    _connect(
        args.command,
        execute=create_execute,
        executePreview=create_preview,
        inputChanged=input_changed,
        preSelect=pre_select,
        validateInputs=validate,
        destroy=destroy,
    )


def _create(args: adsk.core.CommandEventArgs):
    floors, settings = _read_inputs(args.command.commandInputs)
    for group in feature.group_by_body(floors):
        feature.create(group, settings)


def create_execute(args: adsk.core.CommandEventArgs):
    try:
        _create(args)
    except geometry.BridgeError as error:
        args.executeFailed = True
        args.executeFailedMessage = tr(error.message).format(*error.values)


def create_preview(args: adsk.core.CommandEventArgs):
    try:
        _create(args)
        args.isValidResult = True
    except geometry.BridgeError:
        pass


# ---------------------------------------------------------------- edit


def edit_created(args: adsk.core.CommandCreatedEventArgs):
    edited = adsk.fusion.CustomFeature.cast(ui.activeSelections.item(0).entity)
    if edited is None:
        return
    _edit["feature"] = edited
    _add_inputs(args.command.commandInputs, feature.read_settings(edited))
    _connect(
        args.command,
        activate=edit_activate,
        execute=edit_execute,
        executePreview=edit_preview,
        inputChanged=input_changed,
        preSelect=pre_select,
        validateInputs=edit_validate,
        destroy=destroy,
    )


def edit_activate(args: adsk.core.CommandEventArgs):
    edited = _edit["feature"]
    timeline = adsk.fusion.Design.cast(app.activeProduct).timeline
    _edit["restore"] = timeline.item(timeline.markerPosition - 1) if timeline.markerPosition > 0 else None
    edited.timelineObject.rollTo(True)
    # Keep the roll-back out of the preview transaction, which is aborted on every change.
    args.command.beginStep()

    inputs = args.command.commandInputs
    floors_input: adsk.core.SelectionCommandInput = inputs.itemById("floors")
    try:
        for selected, floor in feature.resolved_floors(edited):
            floors_input.addSelection(selected)
    except geometry.BridgeError:
        pass  # the user re-selects the floors
    settings = feature.read_settings(edited)
    if settings.reference is not None:
        inputs.itemById("reference").addSelection(settings.reference)
    _update_angle_state(inputs)


def edit_validate(args: adsk.core.ValidateInputsEventArgs):
    validate(args)
    if args.areInputsValid:
        floors, settings = _read_inputs(args.inputs)
        if "body" not in _edit:
            _edit["body"] = feature.cut_body(_edit["feature"])
        target = _edit["body"]
        args.areInputsValid = target is None or all(feature.native(floor).body == target for floor in floors)


def _apply_edit(args: adsk.core.CommandEventArgs):
    floors, settings = _read_inputs(args.command.commandInputs)
    feature.update(_edit["feature"], floors, settings)


def edit_preview(args: adsk.core.CommandEventArgs):
    try:
        _apply_edit(args)
    except geometry.BridgeError:
        pass


def edit_execute(args: adsk.core.CommandEventArgs):
    try:
        _apply_edit(args)
    except geometry.BridgeError as error:
        args.executeFailed = True
        args.executeFailedMessage = tr(error.message).format(*error.values)
        return
    restore = _edit.get("restore")
    if restore is not None:
        restore.rollTo(False)
