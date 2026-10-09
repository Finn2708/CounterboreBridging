"""Render the Counterbore Bridge icons in Fusion's icon style. Pure Python, no dependencies.

Fusion's solid command icons (e.g. Hole) are an oblique cube - front #D9D9D9, top
#F3F3F3, side #BBBBBB, 1 px #666666 outline - with the feature itself in blue
(#67B1E6). The 16 px icons are drawn on their own grid.

This icon: a counterbore in the front face, seen head-on. On its floor, in blue, the
first-layer bridge strip and the darker second-layer square around the through-hole,
with grey edge lines along the cuts and around the hole, like the icon's contours.
The same icon is used in Fusion's light and dark theme.

Writes 16x16, 32x32, 64x64 (+ @2x) PNGs into the command's resources folder:
    python3 dev/make_icons.py
"""

import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "commands", "counterboreBridge", "resources")
SUPERSAMPLE = 6

OUTLINE = (0x66, 0x66, 0x66, 1.0)  # contours, cut edges and the hole outline
FRONT = (0xD9, 0xD9, 0xD9, 1.0)
TOP = (0xF3, 0xF3, 0xF3, 1.0)
SIDE = (0xBB, 0xBB, 0xBB, 1.0)
FLOOR = (0xC9, 0xC9, 0xC9, 1.0)  # counterbore floor
BLUE = (0x67, 0xB1, 0xE6, 1.0)  # first cut
DARK_BLUE = (0x2F, 0x7C, 0xC0, 1.0)  # second cut
ERASE = None


# ---------------------------------------------------------------- shapes (in icon grid units)

class Shape:
    def __and__(self, other):
        return _Op(self, other, lambda a, b: a and b, self.box)

    def __sub__(self, other):
        return _Op(self, other, lambda a, b: a and not b, self.box)

    def __or__(self, other):
        box = tuple(f(a, b) for f, a, b in zip((min, min, max, max), self.box, other.box))
        return _Op(self, other, lambda a, b: a or b, box)


class _Op(Shape):
    def __init__(self, a, b, op, box):
        self.a, self.b, self.op, self.box = a, b, op, box

    def __contains__(self, p):
        return self.op(p in self.a, p in self.b)


class Circle(Shape):
    def __init__(self, cx, cy, r):
        self.cx, self.cy, self.r2 = cx, cy, r * r
        self.box = (cx - r, cy - r, cx + r, cy + r)

    def __contains__(self, p):
        return (p[0] - self.cx) ** 2 + (p[1] - self.cy) ** 2 <= self.r2


class Rect(Shape):
    def __init__(self, x0, y0, x1, y1):
        self.box = (x0, y0, x1, y1)

    def __contains__(self, p):
        x0, y0, x1, y1 = self.box
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1


class Poly(Shape):
    def __init__(self, *points):
        self.points = points
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.box = (min(xs), min(ys), max(xs), max(ys))

    def __contains__(self, p):
        inside, n = False, len(self.points)
        for i in range(n):
            (x0, y0), (x1, y1) = self.points[i], self.points[(i + 1) % n]
            if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
        return inside


def ring(cx, cy, r, width=1):
    return Circle(cx, cy, r) - Circle(cx, cy, r - width)


# ---------------------------------------------------------------- the icon

def layers(grid):
    """Paint list for one design grid (16 or 32)."""
    d = 6 * grid / 32  # depth of the cube's top and side faces
    top = Poly((0, d), (d, 0), (grid, 0), (grid - d, d))
    side = Poly((grid - d, d), (grid, 0), (grid, grid - d), (grid - d, grid))
    silhouette = Poly((d, 0), (grid, 0), (grid, grid - d), (grid - d, grid), (0, grid), (0, d))
    inset = Poly((d + 0.41, 1), (grid - 1, 1), (grid - 1, grid - d - 0.41), (grid - d - 0.41, grid - 1),
                 (1, grid - 1), (1, d + 0.41))

    # The counterbore seen head-on. Its floor carries the first cut (a strip across)
    # and the second cut (a square around the through-hole), in two distinct blues.
    if grid == 16:
        cx, cy, r, strip_half, square_half, hole, line = 6.5, 9.5, 5.0, 1.5, 1.5, 0.75, 0.6
    else:
        cx, cy, r, strip_half, square_half, hole, line = 13.0, 19.0, 9.5, 3.0, 3.0, 1.0, 1.0
    bore = Circle(cx, cy, r)
    strip = bore & Rect(cx - r, cy - strip_half, cx + r, cy + strip_half)  # layer 1
    square = bore & Rect(cx - square_half, cy - square_half, cx + square_half, cy + square_half)  # layer 2
    # Edge lines: along the strip's long sides and the square's sides across it.
    edges = (strip - Rect(cx - r, cy - strip_half + line, cx + r, cy + strip_half - line)) | (
        square - Rect(cx - square_half + line, cy - square_half - 1, cx + square_half - line, cy + square_half + 1))

    paint = [
        (top, TOP),
        (side, SIDE),
        (Rect(0, d, grid - d, grid) - bore, FRONT),
        (bore, FLOOR),
        (strip, BLUE),
        (square, DARK_BLUE),
        (edges, OUTLINE),
    ]
    if grid == 16:
        paint.append((Circle(cx, cy, hole), OUTLINE))  # too small for a see-through hole
    else:
        paint += [(Circle(cx, cy, hole), ERASE), (ring(cx, cy, hole + 1), OUTLINE)]
    paint += [(ring(cx, cy, r), OUTLINE), (silhouette - inset, OUTLINE)]
    return paint


# ---------------------------------------------------------------- rendering

def render(grid, pixels):
    scale = pixels / grid
    image = [[0.0, 0.0, 0.0, 0.0] for _ in range(pixels * pixels)]  # premultiplied RGBA
    offsets = [(i + 0.5) / SUPERSAMPLE for i in range(SUPERSAMPLE)]
    for shape, colour in layers(grid):
        x0, y0, x1, y1 = shape.box
        for py in range(max(0, int(y0 * scale)), min(pixels, int(y1 * scale) + 1)):
            for px in range(max(0, int(x0 * scale)), min(pixels, int(x1 * scale) + 1)):
                hits = sum(
                    ((px + ox) / scale, (py + oy) / scale) in shape for oy in offsets for ox in offsets
                )
                if not hits:
                    continue
                coverage = hits / SUPERSAMPLE ** 2
                pixel = image[py * pixels + px]
                if colour is ERASE:
                    for c in range(4):
                        pixel[c] *= 1 - coverage
                    continue
                r, g, b, a = colour
                alpha = a * coverage
                for c, value in enumerate((r / 255, g / 255, b / 255)):
                    pixel[c] = value * alpha + pixel[c] * (1 - alpha)
                pixel[3] = alpha + pixel[3] * (1 - alpha)
    return image


def write_png(path, image, pixels):
    rows = bytearray()
    for y in range(pixels):
        rows.append(0)
        for r, g, b, a in image[y * pixels:(y + 1) * pixels]:
            if a > 0:
                rows += bytes(round(min(1, c / a) * 255) for c in (r, g, b))
            else:
                rows += b"\0\0\0"
            rows.append(round(a * 255))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", pixels, pixels, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(rows), 9)))
        f.write(chunk(b"IEND", b""))


def main():
    for filename, grid, pixels in (
        ("16x16.png", 16, 16), ("16x16@2x.png", 16, 32),
        ("32x32.png", 32, 32), ("32x32@2x.png", 32, 64),
        ("64x64.png", 32, 64), ("64x64@2x.png", 32, 128),
    ):
        write_png(os.path.join(OUT, filename), render(grid, pixels), pixels)
        print("wrote", filename)


if __name__ == "__main__":
    main()
