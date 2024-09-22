import math

import adsk.core
import adsk.fusion


def rotateVector180(vect):
    """
    quickly rotate a vector by 180 degrees
    """
    vect.scaleBy(-1)


def rotateVector(vect: adsk.core.Vector3D, axis, angle_degrees):
    """
    rotates a vector by a set degree along the passed axis.

    axis: [z|x|y]

    """
    angle_radians = math.radians(angle_degrees)

    # Create a rotation matrix
    rotation_matrix = adsk.core.Matrix3D.create()
    rotation_matrix.setToIdentity()

    origin = adsk.core.Point3D.create(0, 0, 0)

    # Set rotation based on axis
    if axis == "z":
        rotation_matrix.setToRotation(
            angle_radians, adsk.core.Vector3D.create(0, 0, 1), origin
        )
    elif axis == "y":
        rotation_matrix.setToRotation(
            angle_radians, adsk.core.Vector3D.create(0, 1, 0), origin
        )
    elif axis == "x":
        rotation_matrix.setToRotation(
            angle_radians, adsk.core.Vector3D.create(1, 0, 0), origin
        )
    else:
        raise ValueError("The axis must be 'x', 'y', or 'z'.")

    # Apply rotation
    vect.transformBy(rotation_matrix)


def createVectorFrom2Points(p1: adsk.core.Point3D, p2: adsk.core.Point3D):
    return adsk.core.Vector3D.create(
        p1.x - p2.x,
        p1.y - p2.y,
        p1.z - p2.z,
    )


def movePointTo(currentPoint: adsk.fusion.SketchPoint, newPoint: adsk.core.Point3D):
    """
    allows you to move a SketchPoint (point of a line, curve) to a specified point
    """
    translationVector = adsk.core.Vector3D.create(
        newPoint.x - currentPoint.geometry.x,
        newPoint.y - currentPoint.geometry.y,
        newPoint.z - currentPoint.geometry.z,
    )
    currentPoint.move(translationVector)


"""def extendLineTo(line  : adsk.fusion.SketchLine,newPosition,start=True):
    
    if( start):
        movePointTo(line.startSketchPoint,newPosition) 
    else:
        movePointTo(line.endSketchPoint,newPosition)   


def extendLineDim(line : adsk.fusion.SketchLine,dimension,start=True):

    lineGeom :adsk.core.Line3D= line.geometry


    extensionVector = createVectorFrom2Points(lineGeom.endPoint,lineGeom.startPoint)

    extensionVector.normalize()
    extensionVector.scaleBy(dimension)
    if start:
        extensionVector.scaleBy(-1)     #se allungo l'inizio devo invertire la direzione del vettore 

    
    # Crea un nuovo punto finale per la linea estesa
    if( start):
        newEndPoint:adsk.core.Point3D = lineGeom.startPoint.copy()
        newEndPoint.translateBy(extensionVector)
        movePointTo(line.startSketchPoint,newEndPoint) 
    else:
        newEndPoint:adsk.core.Point3D = lineGeom.endPoint.copy()
        newEndPoint.translateBy(extensionVector)
        movePointTo(line.endSketchPoint,newEndPoint)  
def extendToAnotherCurve(line : adsk.fusion.SketchLine,curveArray,start=True):
    #estendo lo start 
    extendLineDim(line,100,start)
    intersections =[]
    #scorro tutte le linee e trovo le intersezioni
    for l in curveArray:
        intersectionsPoint = line.geometry.intersectWithCurve(l.geometry)
        for point in intersectionsPoint:
            intersections.append(point)

    if len(intersections)== 0:
        return False 
    
    sketchPoint = line.startSketchPoint if start==True else line.endSketchPoint
    
    intersections.sort(key=lambda point: sketchPoint.geometry.distanceTo(point),reverse=True)
    movePointTo(sketchPoint,intersections[0])        
    return True     
"""


def midpoint(line: adsk.fusion.SketchLine):
    start_point = line.startSketchPoint.geometry
    end_point = line.endSketchPoint.geometry

    mid_x = (start_point.x + end_point.x) / 2
    mid_y = (start_point.y + end_point.y) / 2
    mid_z = (start_point.z + end_point.z) / 2

    return adsk.core.Point3D.create(mid_x, mid_y, mid_z)


def getExtendedIntersectionPoints(line: adsk.fusion.SketchLine, curveArray):
    """
    given a SketchLine, it is extended and the intersection points with "curves" present in the "curveArray" are returned

    """
    startIntersection = line.startSketchPoint.geometry
    endIntersection = line.endSketchPoint.geometry

    # extend the line to infinity
    copiedLine = line.geometry.copy()
    infLine = copiedLine.asInfiniteLine()

    intersections = []
    intersectionsWithLine = []
    # scroll through all the lines and find the intersections
    for l in curveArray:  # adsk.fusion.SketchLine
        intersectionsPoint = infLine.intersectWithCurve(l.geometry)
        for point in intersectionsPoint:
            intersections.append(point)
            intersectionsWithLine.append({"point": point, "line": l})

    middle = midpoint(line)

    # I find the direction in degrees of the direction of the line
    startDirection = round(getAngleFromTwoPoints(startIntersection, endIntersection), 0)

    # endDirection should be startDirection-180...
    endDirection = (startDirection + 180) % 360
    # endDirection= round(getAngleFromTwoPoints(endIntersection,startIntersection),0)

    # I find the intersections that touch the "start" / "end" side of the line
    intersectionsWithLineStart = [
        i
        for i in intersectionsWithLine
        if round(getAngleFromTwoPoints(i["point"], middle), 0) % 360 == startDirection
    ]
    intersectionsWithLineEnd = [
        i
        for i in intersectionsWithLine
        if round(getAngleFromTwoPoints(i["point"], middle), 0) % 360 == endDirection
    ]

    # I find the nearest intersections
    if len(intersectionsWithLineStart) > 0:
        intersectionsWithLineStart.sort(key=lambda i: middle.distanceTo(i["point"]))
        startIntersection = intersectionsWithLineStart[0]["point"]
        startInteractionWith = intersectionsWithLineStart[0]["line"]

    if len(intersectionsWithLineEnd) > 0:
        intersectionsWithLineEnd.sort(key=lambda i: middle.distanceTo(i["point"]))
        endIntersection = intersectionsWithLineEnd[0]["point"]
        endInteractionWith = intersectionsWithLineEnd[0]["line"]

    # return the intersections and with which lines
    return startIntersection, endIntersection, startInteractionWith, endInteractionWith


def getAngleFromTwoPoints(point1: adsk.core.Point3D, point2: adsk.core.Point3D):
    dx = point2.x - point1.x
    dy = point2.y - point1.y
    angolo_radianti = math.atan2(dy, dx)
    deg = (math.degrees(angolo_radianti) + 360) % 360
    return deg


def moveLine(line: adsk.fusion.SketchLine, vector: adsk.core.Vector3D):
    """
    BEWARE OF THE CONSTRAINTS! if the line is parallel you will end up moving it twice as much (moving the first point also moves the second)
    """
    line.endSketchPoint.move(vector)
    line.startSketchPoint.move(vector)


def get_curves_from_sketch(sketch: adsk.fusion.Sketch):
    """
    Gets all curves and lines from a sketch.

    Args:
        sketch (adsk.fusion.Sketch): The sketch from which to obtain the curves.

    Returns:
        list: A list of curves and lines from the sketch.
    """
    curves = []

    # Get all curves in the sketch
    sketchCurves = sketch.sketchCurves

    for line in sketchCurves.sketchLines:
        curves.append(line)

    for circle in sketchCurves.sketchCircles:
        curves.append(circle)

    for ellipse in sketchCurves.sketchEllipses:
        curves.append(ellipse)

    for entity in sketchCurves.sketchArcs:
        curves.append(entity)

    for entity in sketchCurves.sketchConicCurves:
        curves.append(entity)

    for entity in sketchCurves.sketchEllipticalArcs:
        curves.append(entity)
    for entity in sketchCurves.sketchFittedSplines:
        curves.append(entity)
    for entity in sketchCurves.sketchFixedSplines:
        curves.append(entity)
    for entity in sketchCurves.sketchControlPointSplines:
        curves.append(entity)

    return curves


"""def isPointInside(profile :adsk.fusion.Profile,point:adsk.core.Point3D):

    bounding_box=profile.boundingBox
    if (bounding_box.minPoint.x <= point.x <= bounding_box.maxPoint.x and
        bounding_box.minPoint.y <= point.y <= bounding_box.maxPoint.y):
        return True
    return False
"""


def profileHasLine(profile: adsk.fusion.Profile, line: adsk.core.Line3D):
    """
    identifies whether a given line is inside the passed profile; the vertices are checked to be equal with a small tolerance
    """
    for profileLine in profile.profileLoops:
        for c in profileLine.profileCurves:
            if isinstance(c.geometry, adsk.core.Line3D):
                g: adsk.core.Line3D = c.geometry

                if g.startPoint.isEqualToByTolerance(line.startPoint, 0.000000001):
                    if g.endPoint.isEqualToByTolerance(line.endPoint, 0.000000001):
                        return True

                elif g.startPoint.isEqualToByTolerance(line.endPoint, 0.000000001):
                    if g.endPoint.isEqualToByTolerance(line.startPoint, 0.000000001):
                        return True

    return False
