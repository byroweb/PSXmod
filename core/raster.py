"""
core/raster.py — numpy z-buffered triangle rasterizer for AC1mod.

Replaces the painter's-algorithm renderer for "no graphical glitches": a true
per-pixel depth buffer (no z-fighting / wrong overlaps), smooth Gouraud lighting
from per-vertex normals, and a parallel object-ID buffer so the GUI can pick the
object under the cursor. Works headless (returns a QImage + id array).

Inputs are flat arrays (build once per scene, re-render cheaply on orbit):
  V    (Nv,3) float  vertex positions (model space)
  VN   (Nv,3) float  per-vertex normals (smooth)
  F    (Nf,3) int    triangle vertex indices
  Fcol (Nf,3) uint8  per-triangle base RGB
  Fid  (Nf,)  int    object id per triangle (for picking; -1 = none)
"""
from __future__ import annotations
import numpy as np
from PyQt6.QtGui import QImage


def look_matrix(yaw, pitch):
    cy, sy = np.cos(yaw), np.sin(yaw)
    cx, sx = np.cos(pitch), np.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return Rx @ Ry


def render(V, VN, F, Fcol, Fid, w=800, h=600, yaw=0.6, pitch=0.4, zoom=1.0,
           bg=(24, 26, 32), light_dir=(0.4, 0.7, 0.6), ambient=0.35):
    """Rasterize and return (QImage, id_buffer[h,w] int32)."""
    img = np.empty((h, w, 3), np.float32)
    img[:] = np.array(bg, np.float32)
    zbuf = np.full((h, w), np.inf, np.float32)
    idbuf = np.full((h, w), -1, np.int32)
    if len(V) == 0 or len(F) == 0:
        return _to_qimage(img), idbuf

    R = look_matrix(yaw, pitch).astype(np.float32)
    # centre + fit
    c = (V.min(0) + V.max(0)) * 0.5
    extent = float(np.max(V.max(0) - V.min(0))) or 1.0
    # PS1 Y is screen-down → flip Y so models are upright
    P = (V - c) * np.array([1, -1, 1], np.float32)
    cam = P @ R.T                                  # rotate into view space
    scale = (min(w, h) * 0.42 / extent) * zoom
    sx = w * 0.5 + cam[:, 0] * scale
    sy = h * 0.5 + cam[:, 1] * scale
    depth = cam[:, 2]                              # view-space z (smaller = nearer-ish)

    # per-vertex lighting (Gouraud)
    L = np.array(light_dir, np.float32); L /= (np.linalg.norm(L) or 1)
    nrm = VN @ R.T
    nl = np.linalg.norm(nrm, axis=1, keepdims=True); nl[nl == 0] = 1
    nrm = nrm / nl
    inten = ambient + (1 - ambient) * np.clip(np.abs(nrm @ L), 0, 1)   # (Nv,)

    sv = np.stack([sx, sy], 1)
    tri = sv[F]                                    # (Nf,3,2)
    # screen-space signed area for backface cull + barycentric denom
    ax, ay = tri[:, 0, 0], tri[:, 0, 1]
    bx, by = tri[:, 1, 0], tri[:, 1, 1]
    cx2, cy2 = tri[:, 2, 0], tri[:, 2, 1]
    area = (bx - ax) * (cy2 - ay) - (cx2 - ax) * (by - ay)
    facing = area < 0                              # cull back faces (one winding)

    tz = depth[F]                                  # (Nf,3)
    tint = inten[F]                                # (Nf,3)
    order = np.argsort(-np.minimum.reduce(tz, axis=1))   # far→near helps early-out little; zbuf is exact

    for t in order:
        if not facing[t]:
            continue
        x0, y0, x1, y1, x2, y2 = ax[t], ay[t], bx[t], by[t], cx2[t], cy2[t]
        minx = max(int(np.floor(min(x0, x1, x2))), 0)
        maxx = min(int(np.ceil(max(x0, x1, x2))), w - 1)
        miny = max(int(np.floor(min(y0, y1, y2))), 0)
        maxy = min(int(np.ceil(max(y0, y1, y2))), h - 1)
        if minx > maxx or miny > maxy:
            continue
        a = area[t]
        if a == 0:
            continue
        ys, xs = np.mgrid[miny:maxy + 1, minx:maxx + 1]
        xs = xs + 0.5; ys = ys + 0.5
        # barycentric
        w0 = ((bx[t] - x0) * (ys - y0) - (by[t] - y0) * (xs - x0)) / a
        w1 = ((cx2[t] - bx[t]) * (ys - by[t]) - (cy2[t] - by[t]) * (xs - bx[t])) / a
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * tz[t, 2] + w1 * tz[t, 0] + w2 * tz[t, 1]
        sub_z = zbuf[miny:maxy + 1, minx:maxx + 1]
        win = inside & (z < sub_z)
        if not win.any():
            continue
        shade = (w0 * tint[t, 2] + w1 * tint[t, 0] + w2 * tint[t, 1])[win]
        col = Fcol[t].astype(np.float32) * shade[:, None]
        sub_img = img[miny:maxy + 1, minx:maxx + 1]
        sub_img[win] = np.clip(col, 0, 255)
        sub_z[win] = z[win]
        idbuf[miny:maxy + 1, minx:maxx + 1][win] = Fid[t]

    return _to_qimage(img), idbuf


def _to_qimage(arr):
    a = np.ascontiguousarray(np.clip(arr, 0, 255).astype(np.uint8))
    h, w, _ = a.shape
    return QImage(a.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
