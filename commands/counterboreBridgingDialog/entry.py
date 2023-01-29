import adsk.core, adsk.fusion
import math
import os
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_cmdDialog'
CMD_NAME = 'Counterbore Bridging'
CMD_Description = 'A Fusion 360 Add-in Command for optimizing counterbores for 3D printing'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidModifyPanel'
COMMAND_BESIDE_ID = 'FusionMoveCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

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


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    f_in = inputs.addSelectionInput('face_input', 'Counterbore Face', 'Select the counterbore bottom face.')
    f_in.addSelectionFilter(adsk.core.SelectionCommandInput.SolidFaces)
    f_in.setSelectionLimits(1)
    d_in = inputs.addSelectionInput('direction_input', 'Direction', 'Select the direction of the primary bridge.')
    d_in.addSelectionFilter(adsk.core.SelectionCommandInput.LinearEdges)
    d_in.setSelectionLimits(1, 1)
    inputs.addValueInput('layer_height_input', 'Layer height', app.activeProduct.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByString('0.2 mm'))

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    face_input: adsk.core.SelectionCommandInput = inputs.itemById('face_input')
    dir_input: adsk.core.SelectionCommandInput = inputs.itemById('direction_input')
    layer_height_input: adsk.core.ValueCommandInput = inputs.itemById('layer_height_input')

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    
    # Read inputs
    faces = [face_input.selection(i) for i in range(face_input.selectionCount)]
    primary_direction = dir_input.selection(0)
    layer_heigth = layer_height_input.value

    for face in faces:
        # Create sketch on face
        sks = design.activeComponent.sketches
        sk: adsk.fusion.Sketch = sks.add(face.entity)

        # Project primary bridge direction to sketch and get its angle
        proj = sk.project(primary_direction.entity)
        dir_proj: adsk.fusion.SketchLine = proj.item(0)
        dir_proj.isConstruction = True
        
        leg_x = dir_proj.endSketchPoint.geometry.x - dir_proj.startSketchPoint.geometry.x
        leg_y = dir_proj.endSketchPoint.geometry.y - dir_proj.startSketchPoint.geometry.y
        hypotenuse  = math.sqrt(leg_x ** 2 + leg_y ** 2)
        alpha = math.acos(leg_x / hypotenuse)

        # Get circles
        cs = sk.sketchCurves.sketchCircles
        circles = [cs.item(i) for i in range(cs.count)]
        outer = cs.item(0)
        def get_radius(c: adsk.fusion.SketchCircle) -> float:
            return c.radius
        
        circles.sort(key=get_radius, reverse=True)
        outer = circles[0]
        inner = circles[1]
        
        xo = outer.centerSketchPoint.geometry.x
        yo = outer.centerSketchPoint.geometry.y
        zo = outer.centerSketchPoint.geometry.z

        # Draw primary bridges
        ls = sk.sketchCurves.sketchLines
        ps = sk.sketchPoints
        p1 = ps.add(adsk.core.Point3D.create(
            xo + inner.radius * math.sin(alpha) + math.sqrt(outer.radius**2 + inner.radius**2) * math.cos(alpha),
            yo + inner.radius * math.cos(alpha) + math.sqrt(outer.radius**2 + inner.radius**2) * math.sin(alpha),
            zo))
        sk.geometricConstraints.addCoincident(p1, outer)
        p2 = ps.add(adsk.core.Point3D.create(
            xo + inner.radius * math.sin(alpha) - math.sqrt(outer.radius**2 + inner.radius**2) * math.cos(alpha),
            yo + inner.radius * math.cos(alpha) - math.sqrt(outer.radius**2 + inner.radius**2) * math.sin(alpha),
            zo))
        sk.geometricConstraints.addCoincident(p2, outer)
        p3 = ps.add(adsk.core.Point3D.create(
            xo - inner.radius * math.sin(alpha) + math.sqrt(outer.radius**2 + inner.radius**2) * math.cos(alpha),
            yo - inner.radius * math.cos(alpha) + math.sqrt(outer.radius**2 + inner.radius**2) * math.sin(alpha),
            zo))
        sk.geometricConstraints.addCoincident(p3, outer)
        p4 = ps.add(adsk.core.Point3D.create(
            xo - inner.radius * math.sin(alpha) - math.sqrt(outer.radius**2 + inner.radius**2) * math.cos(alpha),
            yo - inner.radius * math.cos(alpha) - math.sqrt(outer.radius**2 + inner.radius**2) * math.sin(alpha),
            zo))
        sk.geometricConstraints.addCoincident(p4, outer)

        l1 = ls.addByTwoPoints(p1, p2)
        sk.geometricConstraints.addParallel(l1, proj.item(0))
        sk.geometricConstraints.addTangent(l1, inner)
        l2 = ls.addByTwoPoints(p3, p4)
        sk.geometricConstraints.addParallel(l2, proj.item(0))
        sk.geometricConstraints.addTangent(l2, inner)

        # Draw secondary bridges
        xi = inner.centerSketchPoint.geometry.x
        yi = inner.centerSketchPoint.geometry.y
        zi = inner.centerSketchPoint.geometry.z

        p5 = ps.add(adsk.core.Point3D.create(
            xi + math.sqrt(inner.radius**2 + inner.radius**2) * math.cos(alpha + math.radians(45)),
            yi + math.sqrt(inner.radius**2 + inner.radius**2) * math.sin(alpha + math.radians(45)),
            zi))
        sk.geometricConstraints.addCoincident(p5, l1)
        p6 = ps.add(adsk.core.Point3D.create(
            xi + math.sqrt(inner.radius**2 + inner.radius**2) * math.cos(alpha - math.radians(45)),
            yi + math.sqrt(inner.radius**2 + inner.radius**2) * math.sin(alpha - math.radians(45)),
            zi))
        sk.geometricConstraints.addCoincident(p6, l2)
        p7 = ps.add(adsk.core.Point3D.create(
            xi - math.sqrt(inner.radius**2 + inner.radius**2) * math.cos(alpha + math.radians(45)),
            yi - math.sqrt(inner.radius**2 + inner.radius**2) * math.sin(alpha + math.radians(45)),
            zi))
        sk.geometricConstraints.addCoincident(p7, l1)
        p8 = ps.add(adsk.core.Point3D.create(
            xi - math.sqrt(inner.radius**2 + inner.radius**2) * math.cos(alpha - math.radians(45)),
            yi - math.sqrt(inner.radius**2 + inner.radius**2) * math.sin(alpha - math.radians(45)),
            zi))
        sk.geometricConstraints.addCoincident(p8, l2)

        l3 = ls.addByTwoPoints(p5, p6)
        sk.geometricConstraints.addPerpendicular(l3, proj.item(0))
        sk.geometricConstraints.addTangent(l3, inner)
        l4 = ls.addByTwoPoints(p7, p8)
        sk.geometricConstraints.addPerpendicular(l4, proj.item(0))
        sk.geometricConstraints.addTangent(l4, inner)

        inner.isConstruction = True

        # Select profiles by area
        profiles = [sk.profiles.item(i) for i in range(sk.profiles.count)]
        def get_area(p: adsk.fusion.Profile) -> float:
            return p.areaProperties().area
        profiles.sort(key=get_area, reverse=True)
        
        secondary_profiles = adsk.core.ObjectCollection.create()
        secondary_profiles.add(profiles[3])
        secondary_profiles.add(profiles[4])
        
        tertiary_profiles = adsk.core.ObjectCollection.create()
        if round(profiles[0].areaProperties().area, 8) == round((2 * inner.radius) ** 2, 8):
            tertiary_profiles.add(profiles[0])
        else:
            tertiary_profiles.add(profiles[2])
        
        # Extrude profiles
        one_lh = adsk.core.ValueInput.createByReal(-layer_height_input.value)
        two_lh = adsk.core.ValueInput.createByReal(-2 * layer_height_input.value)

        extrudes = design.activeComponent.features.extrudeFeatures
        extrudes.addSimple(secondary_profiles, one_lh, adsk.fusion.FeatureOperations.CutFeatureOperation)
        extrudes.addSimple(tertiary_profiles, two_lh, adsk.fusion.FeatureOperations.CutFeatureOperation)


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    layer_height_input = inputs.itemById('layer_height_input')
    if layer_height_input.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []
