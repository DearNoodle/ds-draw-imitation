# -*- coding: utf-8 -*-
"""Prepend a coarse, tangent-following underpainting to strokes_jitter.json.

No blurred bitmap is used: every underpainting mark is a real brush stroke.
Writes strokes_under.json and strokes.json (the player input).
"""
import json, math, random, pathlib
import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
rng = random.Random(31)

d = json.loads((ROOT / "strokes_jitter.json").read_text(encoding="utf-8"))
strokes = d["strokes"]

img = cv2.imread(str(ROOT / "image.jpg"))
H, W = img.shape[:2]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
Jxx = cv2.GaussianBlur(gx * gx, (0, 0), 7)
Jyy = cv2.GaussianBlur(gy * gy, (0, 0), 7)
Jxy = cv2.GaussianBlur(gx * gy, (0, 0), 7)
theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + math.pi / 2
blur = cv2.GaussianBlur(img, (0, 0), 8)

CELL = 24
under = []
for y in range(12, H, CELL):
    for x in range(12, W, CELL):
        cx = x + rng.uniform(-5, 5)
        cy = y + rng.uniform(-5, 5)
        x0 = int(np.clip(cx, 0, W - 1))
        y0 = int(np.clip(cy, 0, H - 1))
        ang = float(theta[y0, x0]) + rng.uniform(-0.28, 0.28)
        length = rng.uniform(38, 66)
        width = rng.uniform(22, 34)
        dx = math.cos(ang) * length / 2
        dy = math.sin(ang) * length / 2
        px, py = -dy * 0.10, dx * 0.10
        b, gg, r = [int(v) for v in blur[y0, x0]]
        color = "#%02x%02x%02x" % (r, gg, b)
        path = "M%.1f %.1fQ%.1f %.1f %.1f %.1f" % (
            cx - dx, cy - dy, cx + px, cy + py, cx + dx, cy + dy)
        under.append([path, color, int(round(width * 10)), 0, 3, 0])

cur = 0
for s in under:
    s[3] = cur
    cur += s[4]
for s in strokes:
    s[3] += cur

ordered = under + strokes
d["strokes"] = ordered
d["meta"]["strokes"] = len(ordered)
d["meta"]["duration"] = max(s[3] + s[4] for s in ordered)

for name in ("strokes_under.json", "strokes.json"):
    (ROOT / name).write_text(
        json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print("under", len(under), "shift", cur, "N", len(ordered),
      "duration", d["meta"]["duration"])
