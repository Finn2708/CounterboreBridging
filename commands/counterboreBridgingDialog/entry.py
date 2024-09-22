import math
import os

import adsk.core
import adsk.fusion

from ... import config
from ...lib import fusion360utils as futil

from .geometryUtil import (
    rotateVector180,
    rotateVector,
    movePointTo,
    profileHasLine,
    getExtendedIntersectionPoints,
    getAngleFromTwoPoints,
    get_curves_from_sketch,
    createVectorFrom2Points,
)


app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f"{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdDialog"
CMD_NAME = "Counterbore Bridging"
CMD_Description = (
    "A Fusion 360 Add-in Command for optimizing counterbores for 3D printing"
)

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidModifyPanel"
COMMAND_BESIDE_ID = "FusionMoveCommand"

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "")

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER
    )

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


def cutOneFace(
    face,
    layer_height_input: adsk.core.ValueCommandInput,
    angleStep=0,
    gap=0.0001,
    oldGuideLine=None,
):
    """
    performs a cut with the specified parameters
    a "gap" is left between the diameter and the line to make it easier to cut the patterns
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)

    # Create sketch on face
    sks = design.activeComponent.sketches
    sk: adsk.fusion.Sketch = sks.add(face)

    if oldGuideLine:
        # copy it into the current sketch
        # take the size of the angle

        proj = sk.project(oldGuideLine)
        oldGuideLine_proj: adsk.fusion.SketchLine = proj.item(0)
        oldGuideLine_proj.isConstruction = True

        # old fixed method
        # leg_x = oldGuideLine_proj.endSketchPoint.geometry.x - oldGuideLine_proj.startSketchPoint.geometry.x
        # leg_y = oldGuideLine_proj.endSketchPoint.geometry.y - oldGuideLine_proj.startSketchPoint.geometry.y
        # angle = math.atan2(leg_y, leg_x) * 180 /math.pi

        angleOldGuideLine = getAngleFromTwoPoints(
            oldGuideLine_proj.startSketchPoint.geometry,
            oldGuideLine_proj.endSketchPoint.geometry,
        )
        newAngle = angleOldGuideLine + angleStep
    else:
        newAngle = angleStep

    # Get inner circle
    cs = sk.sketchCurves.sketchCircles
    circles = [cs.item(i) for i in range(cs.count)]
    if len(circles) == 0:
        # it could be an arc...
        cs = sk.sketchCurves.sketchArcs
        circles = [cs.item(i) for i in range(cs.count)]
        if len(circles) == 0:
            ui.messageBox("Cannot find inner circle")
            return

    circles.sort(key=lambda c: c.radius, reverse=False)
    inner = circles[0]
    inner.isConstruction = True

    xi = inner.centerSketchPoint.geometry.x
    yi = inner.centerSketchPoint.geometry.y
    zi = inner.centerSketchPoint.geometry.z

    # I take all the existing lines in the sketch (before adding any more) and remove the inner circle
    lines = get_curves_from_sketch(sk)
    lines.remove(inner)

    # Calculate the coordinates of the end point ( create a very short line since it will only serve as a reference for orientation )
    angle_radians = math.radians(newAngle)
    x_end = math.cos(angle_radians) * 0.1
    y_end = math.sin(angle_radians) * 0.1
    start_point = adsk.core.Point3D.create(xi, yi, zi)
    end_point = adsk.core.Point3D.create(
        start_point.x + x_end, start_point.y + y_end, start_point.z
    )
    angleGuideLine = sk.sketchCurves.sketchLines.addByTwoPoints(start_point, end_point)
    angleGuideLine.isConstruction = True
    sk.geometricConstraints.addCoincident(
        angleGuideLine.startSketchPoint, inner.centerSketchPoint
    )
    if oldGuideLine:
        ad = sk.sketchDimensions.addAngularDimension(
            oldGuideLine_proj, angleGuideLine, oldGuideLine_proj.geometry.startPoint
        )
        ad.parameter.value = math.radians(angleStep)
    else:
        angleGuideLine.isFixed = True

    # create the first line with the related constraints
    # (I use a vect to move the vertex points of the lines by certain dimensions)
    line1 = sk.sketchCurves.sketchLines.addByTwoPoints(
        angleGuideLine.startSketchPoint.geometry, angleGuideLine.endSketchPoint.geometry
    )
    sk.geometricConstraints.addParallel(line1, angleGuideLine)
    vect = createVectorFrom2Points(
        angleGuideLine.startSketchPoint.geometry, angleGuideLine.endSketchPoint.geometry
    )
    rotateVector(vect, "z", 90)
    vect.normalize()
    vect.scaleBy(inner.radius + gap)
    line1.endSketchPoint.move(vect)

    # create the second line with the related constraints
    line2 = sk.sketchCurves.sketchLines.addByTwoPoints(
        angleGuideLine.startSketchPoint.geometry, angleGuideLine.endSketchPoint.geometry
    )
    sk.geometricConstraints.addParallel(line2, angleGuideLine)
    rotateVector180(vect)
    line2.endSketchPoint.move(vect)

    # create construction lines to set the distance between the line and the internal diameter
    # for line1
    distanceLine = sk.sketchCurves.sketchLines.addByTwoPoints(
        inner.centerSketchPoint.geometry, line1.endSketchPoint.geometry
    )
    distanceLine.isConstruction = True
    sk.geometricConstraints.addPerpendicular(distanceLine, line1)
    sk.geometricConstraints.addCoincident(
        inner.centerSketchPoint, distanceLine.startSketchPoint
    )
    sk.geometricConstraints.addCoincident(distanceLine.endSketchPoint, line1)
    dim = sk.sketchDimensions.addDistanceDimension(
        distanceLine.startSketchPoint,
        distanceLine.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        distanceLine.startSketchPoint.geometry,
    )
    dim.parameter.value = inner.radius + gap

    # for line2
    distanceLine = sk.sketchCurves.sketchLines.addByTwoPoints(
        inner.centerSketchPoint.geometry, line2.endSketchPoint.geometry
    )
    distanceLine.isConstruction = True
    sk.geometricConstraints.addPerpendicular(distanceLine, line2)
    sk.geometricConstraints.addCoincident(
        inner.centerSketchPoint, distanceLine.startSketchPoint
    )
    sk.geometricConstraints.addCoincident(distanceLine.endSketchPoint, line2)
    dim = sk.sketchDimensions.addDistanceDimension(
        distanceLine.startSketchPoint,
        distanceLine.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        distanceLine.startSketchPoint.geometry,
    )
    dim.parameter.value = inner.radius + gap

    # retrieve the intersections of the 2 lines with the existing profile
    startPoint1, endPoint1, interLineStart1, interLineEnd1 = (
        getExtendedIntersectionPoints(line1, lines)
    )
    startPoint2, endPoint2, interLineStart2, interLineEnd2 = (
        getExtendedIntersectionPoints(line2, lines)
    )

    # move the lines as close to the intersection points as possible
    movePointTo(line1.startSketchPoint, startPoint1)
    movePointTo(line1.endSketchPoint, endPoint1)

    movePointTo(line2.startSketchPoint, startPoint2)
    movePointTo(line2.endSketchPoint, endPoint2)

    # add the coincidence constraint (if it is not placed, it can cause problems on the splines)
    sk.geometricConstraints.addCoincident(line1.startSketchPoint, interLineStart1)
    sk.geometricConstraints.addCoincident(line1.endSketchPoint, interLineEnd1)

    sk.geometricConstraints.addCoincident(line2.startSketchPoint, interLineStart2)
    sk.geometricConstraints.addCoincident(line2.endSketchPoint, interLineEnd2)

    # Take the center profile

    # search all profiles for those that contain both line1 and line2
    # if a profile contains both it means it is the central one
    profiles = [sk.profiles.item(i) for i in range(sk.profiles.count)]

    candidateProfiles = []
    for p in profiles:
        if profileHasLine(p, line1.geometry) and profileHasLine(p, line2.geometry):
            candidateProfiles.append(p)

    # if found more "valid" profiles... exceptional case...
    if len(candidateProfiles) != 1:
        ui.messageBox("Invalid shape, cant compute the inner profile")
        return

    centerProfile = adsk.core.ObjectCollection.create()
    centerProfile.add(candidateProfiles[0])

    # make the cut
    one_lh = adsk.core.ValueInput.createByReal(-layer_height_input.value)

    extrudes = design.activeComponent.features.extrudeFeatures
    ex1 = extrudes.addSimple(
        centerProfile, one_lh, adsk.fusion.FeatureOperations.CutFeatureOperation
    )

    # If a user parameter is used as input, link extrude extent to that parameter
    if design.userParameters.itemByName(layer_height_input.expression) is not None:
        ex1_def = adsk.fusion.DistanceExtentDefinition.cast(ex1.extentOne)
        ex1_def.distance.expression = f"-{layer_height_input.expression}"

    # return the new face (for the next cut) and the guide line for orientation
    return ex1.endFaces[0], angleGuideLine


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f"{CMD_NAME} Command Created Event")

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    f_in = inputs.addSelectionInput(
        "face_input", "Counterbore Face", "Select the counterbore bottom face."
    )
    f_in.addSelectionFilter(adsk.core.SelectionCommandInput.SolidFaces)
    f_in.setSelectionLimits(1)

    inputs.addIntegerSpinnerCommandInput(
        "angle_degree_input", "Angle degree", 0, 359, 1, 0
    )
    inputs.addValueInput(
        "layer_height_input",
        "Layer height",
        app.activeProduct.unitsManager.defaultLengthUnits,
        adsk.core.ValueInput.createByString("0.2 mm"),
    )
    inputs.addIntegerSpinnerCommandInput("number_of_cut", "Number of cut", 1, 5, 1, 2)

    futil.add_handler(
        args.command.execute, command_execute, local_handlers=local_handlers
    )
    futil.add_handler(
        args.command.inputChanged, command_input_changed, local_handlers=local_handlers
    )
    futil.add_handler(
        args.command.executePreview, command_preview, local_handlers=local_handlers
    )
    futil.add_handler(
        args.command.validateInputs,
        command_validate_input,
        local_handlers=local_handlers,
    )
    futil.add_handler(
        args.command.destroy, command_destroy, local_handlers=local_handlers
    )


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f"{CMD_NAME} Command Execute Event")

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    face_input: adsk.core.SelectionCommandInput = inputs.itemById("face_input")
    angle_degree_input = inputs.itemById("angle_degree_input")
    layer_height_input: adsk.core.ValueCommandInput = inputs.itemById(
        "layer_height_input"
    )
    number_of_cut_input = inputs.itemById("number_of_cut")

    # app = adsk.core.Application.get()
    # design = adsk.fusion.Design.cast(app.activeProduct)

    # Read inputs
    faces = [face_input.selection(i) for i in range(face_input.selectionCount)]
    # layer_heigth = layer_height_input.value

    angleStep = 180.0 / number_of_cut_input.value

    for face in faces:
        currentFace = face.entity
        currentAngle = (
            angle_degree_input.value
        )  # la prima volta vale come l'angolo impostato, poi step
        oldGuideLine = None
        for i in range(number_of_cut_input.value):
            currentFace, oldGuideLine = cutOneFace(
                currentFace, layer_height_input, currentAngle, oldGuideLine=oldGuideLine
            )
            currentAngle = angleStep
            # app.activeViewport.refresh()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f"{CMD_NAME} Command Preview Event")

    command_execute(args)

    # inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    # inputs = args.inputs

    # General logging for debug.
    futil.log(
        f"{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}"
    )


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f"{CMD_NAME} Validate Input Event")

    inputs = args.inputs

    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    layer_height_input = inputs.itemById("layer_height_input")
    if layer_height_input.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f"{CMD_NAME} Command Destroy Event")

    global local_handlers
    local_handlers = []
