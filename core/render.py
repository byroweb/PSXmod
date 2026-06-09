"""
core/render.py — tiny software 3D renderer for AC1 PS1-era meshes.

PS1 geometry is a few hundred polys, so a painter's-algorithm software rasterizer
into a QImage is plenty (mirrors the game's own average-Z OT sort) and needs no
OpenGL context — works headless (QT_QPA_PLATFORM=offscreen) for the CLI, and is
drawn straight into the ModelView3D widget in the GUI.
"""
from __future__ import annotations
import math
from PyQt6.QtGui import QImage, QPainter, QColor, QPolygonF, QPen
from PyQt6.QtCore import Qt, QPointF


def _rot(yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cx, sx = math.cos(pitch), math.sin(pitch)
    # Y-up; yaw about Y, pitch about X
    def f(p):
        x, y, z = p
        x, z = x * cy + z * sy, -x * sy + z * cy
        y, z = y * cx - z * sx, y * sx + z * cx
        return (x, y, z)
    return f


def render_mesh(mesh, w=520, h=380, yaw=0.6, pitch=0.5, zoom=1.0,
                bg=(24, 26, 32), wire=False, cull=True):
    """Render `mesh` to a QImage(w,h). yaw/pitch in radians, zoom multiplier."""
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(*bg))
    bb = mesh.bbox() if mesh else None
    if not bb or not mesh.faces:
        p = QPainter(img)
        p.setPen(QColor(150, 160, 175))
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter,
                   "no geometry" if mesh else "—")
        p.end()
        return img

    cx, cy, cz = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2
    extent = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1.0)
    rot = _rot(yaw, pitch)
    scale = (min(w, h) * 0.42 / extent) * zoom

    # PS1 Y is screen-down; flip Y so models stand upright.
    def project(v):
        x, y, z = rot((v[0] - cx, -(v[1] - cy), v[2] - cz))
        return (w / 2 + x * scale, h / 2 + y * scale, z)

    pv = [project(v) for v in mesh.vertices]
    light = (0.35, 0.55, 0.75)
    llen = math.sqrt(sum(c * c for c in light)); light = tuple(c / llen for c in light)

    faces = []
    for fc in mesh.faces:
        try:
            a, b, c = (pv[i] for i in fc.verts)
        except IndexError:
            continue
        # face normal (screen space) for flat shading + depth key
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        if cull and not wire and nz > 0:        # back-facing (screen normal away)
            continue
        shade = 0.45 + 0.55 * abs((nx * light[0] + ny * light[1] + nz * light[2]) / nl)
        zkey = (a[2] + b[2] + c[2]) / 3.0
        faces.append((zkey, fc, shade, (a, b, c)))
    faces.sort(key=lambda t: t[0], reverse=True)   # far -> near

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for _, fc, shade, tri in faces:
        r, g, bl = fc.color
        col = QColor(min(255, int(r * shade)), min(255, int(g * shade)),
                     min(255, int(bl * shade)))
        poly = QPolygonF([QPointF(t[0], t[1]) for t in tri])
        if wire:
            p.setPen(QPen(col, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
        else:
            p.setPen(QPen(col.darker(135), 1)); p.setBrush(col)
        p.drawPolygon(poly)
    p.end()
    return img
