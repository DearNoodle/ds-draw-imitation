# -*- coding: utf-8 -*-
"""
一筆一筆：把 image.jpg 轉成 >100k 條帶 start/dur 的 SVG path 筆觸。
Pipeline: L/S k-means 5 層 -> 結構張量方向 -> Canny 輪廓 -> 五官/徽章密集細節。
"""
import cv2, numpy as np, json, math, random, zlib, base64, os, sys

SEED = 20240101
rng = random.Random(SEED)
np.random.seed(SEED)

SRC = "image.jpg"
OUT_JSON = "strokes.json"
OUT_HTML = "index.html"

# ---------------- load & feature maps ----------------
img = cv2.imread(SRC, cv2.IMREAD_COLOR)
H, W = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gf = gray.astype(np.float32) / 255.0

lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
L = lab[:, :, 0].astype(np.float32) / 255.0
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
S = hsv[:, :, 1].astype(np.float32) / 255.0

# local contrast (for stroke density / length)
m = cv2.blur(gf, (13, 13))
sq = cv2.blur(gf * gf, (13, 13))
local_std = np.sqrt(np.maximum(sq - m * m, 0.0))
local_std = cv2.GaussianBlur(local_std, (0, 0), 2.0)
std_n = np.clip(local_std / (np.percentile(local_std, 97) + 1e-6), 0, 1)

# structure tensor
gb = cv2.GaussianBlur(gf, (0, 0), 2.0)
Ix = cv2.Sobel(gb, cv2.CV_32F, 1, 0, ksize=3)
Iy = cv2.Sobel(gb, cv2.CV_32F, 0, 1, ksize=3)
Jxx = cv2.GaussianBlur(Ix * Ix, (0, 0), 3.6)
Jyy = cv2.GaussianBlur(Iy * Iy, (0, 0), 3.6)
Jxy = cv2.GaussianBlur(Ix * Iy, (0, 0), 3.6)
tr = Jxx + Jyy + 1e-9
coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / tr
coh = np.clip(coh, 0, 1)
theta_grad = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
theta_tan = theta_grad + np.pi / 2.0           # isophote / stroke direction

grad_mag = np.sqrt(Ix * Ix + Iy * Iy)
grad_mag = cv2.GaussianBlur(grad_mag, (0, 0), 2.0)
grad_n = np.clip(grad_mag / (np.percentile(grad_mag, 98) + 1e-6), 0, 1)

# ---------------- 5 tone layers from L + S ----------------
feat = np.stack([L, S], -1)
# weighted: luminance dominates, saturation helps separate pastel colours
feat_w = feat.copy()
feat_w[:, :, 0] *= 1.0
feat_w[:, :, 1] *= 0.85
samp = feat_w.reshape(-1, 2)[::4]
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 80, 0.15)
_, _, cent = cv2.kmeans(samp, 5, None, crit, 6, cv2.KMEANS_PP_CENTERS)
cent = cent[np.argsort(cent[:, 0])]
flat = feat_w.reshape(-1, 2)
d2 = ((flat[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
layer_map = d2.argmin(1).reshape(H, W).astype(np.uint8)
tone_centers = cent.tolist()
layer_area = [int((layer_map == k).sum()) for k in range(5)]
print("tone layers:", layer_area, "centers:", np.round(cent, 3).tolist())

# ---------------- character / background mask ----------------
# Hand-seeded region mask (used only for pass ordering & labels, not for clipping).
fg = np.zeros((H, W), np.uint8)
poly_body = np.array([[140, 735], [610, 735], [715, H - 1], [55, H - 1]], np.int32)
poly_hat = np.array([[200, 415], [245, 305], [420, 275], [565, 325], [640, 435],
                     [605, 545], [240, 535]], np.int32)
poly_arm = np.array([[50, 292], [205, 300], [250, 610], [85, 655], [30, 500]], np.int32)
poly_hand_r = np.array([[565, 775], [690, 790], [725, 1075], [590, 1095], [548, 900]], np.int32)
cv2.fillPoly(fg, [poly_body, poly_hat, poly_arm, poly_hand_r], 1)
cv2.ellipse(fg, (385, 630), (275, 285), 0, 0, 360, 1, -1)
cv2.ellipse(fg, (405, 420), (235, 150), 0, 0, 360, 1, -1)
# fill holes
ff = fg.copy()
mask2 = np.zeros((H + 2, W + 2), np.uint8)
cv2.floodFill(ff, mask2, (0, 0), 1)
fg = (fg | (1 - ff)).astype(np.uint8)
print("fg fraction", float(fg.mean()))

# ---------------- helper ----------------
COLOR_BLUR = cv2.GaussianBlur(img, (0, 0), 2.8)
strokes = []


def bgr_hex(b, g, r):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def sample_color(x, y, blur=False, darken=0.0):
    xi = int(min(max(x, 0), W - 1))
    yi = int(min(max(y, 0), H - 1))
    if darken > 0:
        x0, x1 = max(0, xi - 3), min(W, xi + 4)
        y0, y1 = max(0, yi - 3), min(H, yi + 4)
        patch = img[y0:y1, x0:x1]
        gg = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        j = np.unravel_index(np.argmin(gg), gg.shape)
        b, g, r = patch[j]
    else:
        src = COLOR_BLUR if blur else img
        patch = src[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2].reshape(-1, 3)
        b, g, r = np.median(patch, axis=0)
    if darken > 0:
        f = 1.0 - darken
        b, g, r = b * f, g * f, r * f
    # subtle pigment variation
    jitter = 3.2
    b = min(255, max(0, b + rng.uniform(-jitter, jitter)))
    g = min(255, max(0, g + rng.uniform(-jitter, jitter)))
    r = min(255, max(0, r + rng.uniform(-jitter, jitter)))
    return bgr_hex(b, g, r)


def tangent_at(x, y, fallback=None):
    xi = int(min(max(x, 0), W - 1))
    yi = int(min(max(y, 0), H - 1))
    a = float(theta_tan[yi, xi])
    if not np.isfinite(a):
        a = fallback if fallback is not None else rng.uniform(0, math.pi)
    return a


def make_quad(x, y, ang, length, bend):
    dx, dy = math.cos(ang), math.sin(ang)
    px, py = -dy, dx
    x0 = x - dx * length * 0.5
    y0 = y - dy * length * 0.5
    x1 = x + dx * length * 0.5
    y1 = y + dy * length * 0.5
    mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    # quadratic control: midpoint offset = 0.5*(ctrl-mid)
    cx = mx + px * bend * length
    cy = my + py * bend * length
    return (x0, y0, cx, cy, x1, y1)


def add_quad(points, color, width, group, fg_flag, meta=None):
    x0, y0, cx, cy, x1, y1 = points
    # Endpoints may sit outside the canvas: Canvas/OpenCV clip them. Rejecting
    # them here left a pale, unpainted frame around the whole picture.
    d = "M%.1f %.1fQ%.1f %.1f %.1f %.1f" % (x0, y0, cx, cy, x1, y1)
    # sampled points for OpenCV preview
    ts = np.linspace(0, 1, 7)
    pts = np.stack([
        (1 - ts) ** 2 * x0 + 2 * (1 - ts) * ts * cx + ts ** 2 * x1,
        (1 - ts) ** 2 * y0 + 2 * (1 - ts) * ts * cy + ts ** 2 * y1,
    ], 1)
    strokes.append(dict(d=d, color=color, w=width, g=group, fg=int(fg_flag),
                        pts=pts, meta=meta or {}))
    return True


# ---------------- pass 1: toned colour study ----------------
# A soft, blurred colour study is laid down first, like a thin turpentine
# wash.  It is one continuous ground -- not a pile of random brush marks --
# so the first strokes refine a coherent image instead of covering it up.
BASE_SMALL = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
BASE_SMALL = cv2.GaussianBlur(BASE_SMALL, (0, 0), 5.0)
cv2.imwrite("base.jpg", BASE_SMALL, [cv2.IMWRITE_JPEG_QUALITY, 92])
n_under = 0
print("toned colour study", BASE_SMALL.shape[1], "x", BASE_SMALL.shape[0], "(no under strokes)")

# ---------------- pass 2: 5 tone layers, background then character ----------------
TONE_BG = 30000
TONE_FG = 31500


def tone_pass(k, want, fg_flag):
    yy, xx = np.where((layer_map == k) & (fg == fg_flag))
    if len(xx) == 0:
        return 0
    area = len(xx)
    spacing = max(3.2, math.sqrt(area / max(want, 1)) * 0.86)
    cand = []
    x0, x1 = int(xx.min()), int(xx.max())
    y0, y1 = int(yy.min()), int(yy.max())
    gx = np.arange(x0 + spacing * 0.5, x1, spacing)
    gy = np.arange(y0 + spacing * 0.5, y1, spacing)
    for y in gy:
        for x in gx:
            px = int(round(x + rng.uniform(-spacing * 0.45, spacing * 0.45)))
            py = int(round(y + rng.uniform(-spacing * 0.45, spacing * 0.45)))
            if 0 <= px < W and 0 <= py < H and layer_map[py, px] == k and fg[py, px] == fg_flag:
                cand.append((px, py))
    rng.shuffle(cand)
    # make sure we get the requested count by sampling jittered positions from the mask if needed
    tries = 0
    while len(cand) < want and tries < 6:
        tries += 1
        for _ in range(want - len(cand)):
            j = rng.randrange(area)
            px, py = int(xx[j]), int(yy[j])
            cand.append((px, py))
        rng.shuffle(cand)
    cand = cand[:want]
    n = 0
    for (x, y) in cand:
        c = float(coh[y, x])
        gn = float(np.clip(grad_n[y, x] * 2.2, 0, 1))
        ang = tangent_at(x, y) + rng.uniform(-0.28, 0.28) * (1 - c)
        length = rng.uniform(7.5, 17.0) * (1.0 - 0.62 * gn) * (1.0 - 0.12 * k)
        length = max(3.2, length)
        width = (rng.uniform(3.4, 7.2) - 0.42 * k) * (1.0 - 0.55 * gn)
        width = max(1.5, width)
        bend = rng.uniform(-0.16, 0.16)
        col = sample_color(x, y, blur=True)
        if add_quad(make_quad(x, y, ang, length, bend), col, width, "tone%d" % k, fg_flag):
            n += 1
    return n


for k in range(5):
    n = tone_pass(k, round(TONE_BG * layer_area[k] / sum(layer_area)), 0)
    print("tone BG", k, n)
for k in range(5):
    n = tone_pass(k, round(TONE_FG * layer_area[k] / sum(layer_area)), 1)
    print("tone FG", k, n)

# ---------------- pass 3: dense detail in hair / face / eyes / mouth / badge ----------------
DETAIL = [
    # name, x0, y0, x1, y1, count, len_lo, len_hi, w_lo, w_hi
    ("hair",   232, 425, 655, 905, 2600, 3.0, 7.0, 1.15, 2.30),
    ("face",   285, 560, 520, 855, 9500, 2.2, 5.6, 1.00, 2.00),
    ("eyeL",   290, 648, 376, 756, 5000, 1.8, 4.2, 1.00, 1.85),
    ("eyeR",   398, 644, 494, 752, 5000, 1.8, 4.2, 1.00, 1.85),
    ("mouth",  338, 746, 438, 840, 2600, 1.6, 4.0, 0.90, 1.70),
    ("badge",  344, 938, 474, 1066, 3600, 1.7, 4.2, 0.90, 1.80),
    ("flower", 425, 460, 588, 638, 1400, 2.5, 6.0, 1.10, 2.10),
    ("bow",    300, 878, 542, 1118, 1600, 2.6, 6.2, 1.10, 2.15),
    ("handL",   45, 276, 222, 548,  900, 2.5, 6.0, 1.10, 2.10),
    ("handR",  552, 773, 722, 1108,  900, 2.5, 6.0, 1.10, 2.10),
]
for (name, x0, y0, x1, y1, want, l0, l1, w0, w1) in DETAIL:
    spacing = max(1.35, math.sqrt((x1 - x0) * (y1 - y0) / want) * 0.88)
    cand = []
    for y in np.arange(y0 + spacing * 0.5, y1, spacing):
        for x in np.arange(x0 + spacing * 0.5, x1, spacing):
            px = int(round(x + rng.uniform(-spacing * 0.4, spacing * 0.4)))
            py = int(round(y + rng.uniform(-spacing * 0.4, spacing * 0.4)))
            if 0 <= px < W and 0 <= py < H:
                cand.append((px, py))
    rng.shuffle(cand)
    while len(cand) < want:
        cand.append((rng.randrange(x0, x1), rng.randrange(y0, y1)))
    cand = cand[:want]
    n = 0
    for (x, y) in cand:
        gn = float(np.clip(grad_n[y, x] * 2.0, 0, 1))
        ang = tangent_at(x, y) + rng.uniform(-0.22, 0.22) * (1 - float(coh[y, x]))
        length = rng.uniform(l0, l1) * (1.0 - 0.35 * gn)
        length = max(1.2, length)
        width = rng.uniform(w0, w1) * (1.0 - 0.18 * gn)
        width = max(0.75, width)
        bend = rng.uniform(-0.20, 0.20)
        col = sample_color(x, y)
        if add_quad(make_quad(x, y, ang, length, bend), col, width, "detail",
                    fg[int(y), int(x)], {"roi": name}):
            n += 1
    print("detail", name, n)

# ---------------- pass 4: strong ink contours ----------------
edges = np.zeros((H, W), np.uint8)
edges |= cv2.Canny(cv2.GaussianBlur(gray, (0, 0), 1.2), 55, 145)
lab8 = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
edges |= cv2.Canny(cv2.GaussianBlur(lab8[:, :, 2], (0, 0), 1.2), 40, 110)
edges |= cv2.Canny(cv2.GaussianBlur(lab8[:, :, 1], (0, 0), 1.2), 40, 110)
edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

segments = []
for c in contours:
    if len(c) < 16:
        continue
    pts = c[:, 0, :].astype(np.float32)
    seglen = np.sqrt(((np.diff(pts, axis=0)) ** 2).sum(1))
    total = float(seglen.sum())
    if total < 32:
        continue
    n = max(2, int(total / 5.0))
    idx = np.linspace(0, len(pts) - 1, n).astype(int)
    rp = pts[idx]
    for i in range(len(rp) - 1):
        a, b = rp[i], rp[i + 1]
        Ls = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        if Ls < 3.0:
            continue
        mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
        xi, yi = int(mx), int(my)
        in_fg = int(fg[yi, xi])
        in_roi = (285 <= mx <= 515 and 555 <= my <= 855) or (340 <= mx <= 475 and 935 <= my <= 1070)
        # features are painted by the dedicated detail / accent passes, not by global ink
        in_feature = ((290 <= mx <= 376 and 648 <= my <= 756) or
                      (398 <= mx <= 494 and 644 <= my <= 752) or
                      (338 <= mx <= 438 and 746 <= my <= 840) or
                      (344 <= mx <= 474 and 938 <= my <= 1066))
        if in_feature:
            continue
        segments.append((a[0], a[1], b[0], b[1], Ls, in_fg, in_roi, mx, my))

print("contour segments", len(segments))


def ink_color(mx, my, strength=0.72):
    xi = int(min(max(mx, 0), W - 1))
    yi = int(min(max(my, 0), H - 1))
    x0, x1 = max(0, xi - 2), min(W, xi + 3)
    y0, y1 = max(0, yi - 2), min(H, yi + 3)
    patch = img[y0:y1, x0:x1]
    gg = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    j = np.unravel_index(np.argmin(gg), gg.shape)
    db, dg, dr = patch[j].astype(np.float32)
    mb, mg, mr = img[yi, xi].astype(np.float32)
    b = db * strength + mb * (1 - strength) + rng.uniform(-2, 2)
    g = dg * strength + mg * (1 - strength) + rng.uniform(-2, 2)
    r = dr * strength + mr * (1 - strength) + rng.uniform(-2, 2)
    return bgr_hex(b, g, r)


# long, strong, character/face contours first
segments.sort(key=lambda s: -(s[4] * (1.0 + 0.8 * s[6]) * (1.0 + 0.10 * s[5]) + rng.uniform(0, 6)))
CONTOUR_TOTAL = 9000
chosen = segments[:CONTOUR_TOTAL]
bg_segs = [s for s in chosen if s[5] == 0]
fg_segs = [s for s in chosen if s[5] == 1]
rng.shuffle(bg_segs)
rng.shuffle(fg_segs)
print("contour chosen", len(chosen), "bg", len(bg_segs), "fg", len(fg_segs))


def add_contours(segs):
    n = 0
    for s in segs:
        x0, y0, x1, y1, Ls, in_fg, in_roi, mx, my = s
        ang = math.atan2(y1 - y0, x1 - x0)
        width = rng.uniform(0.95, 1.65) if not in_roi else rng.uniform(1.05, 1.85)
        bend = rng.uniform(-0.02, 0.02) * Ls
        col = ink_color(mx, my, strength=0.66 if not in_roi else 0.74)
        if add_quad((x0, y0, (x0 + x1) * 0.5 + (-math.sin(ang)) * bend,
                     (y0 + y1) * 0.5 + math.cos(ang) * bend, x1, y1),
                    col, width, "contour", in_fg, {"roi": in_roi}):
            n += 1
    return n


print("contour BG", add_contours(bg_segs))
print("contour FG", add_contours(fg_segs))

# ---------------- pass 5: accents for eyes / mouth / badge ----------------
acc_rois = [(290, 646, 378, 758), (396, 642, 496, 754), (336, 744, 440, 842),
            (342, 936, 476, 1070)]
acc_edges = cv2.Canny(cv2.GaussianBlur(gray, (0, 0), 1.0), 28, 78)
acc_n = 0
for (x0, y0, x1, y1) in acc_rois:
    cnts, _ = cv2.findContours(acc_edges[y0:y1, x0:x1], cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    segs = []
    for c in cnts:
        if len(c) < 6:
            continue
        p = c[:, 0, :].astype(np.float32) + np.array([x0, y0], np.float32)
        for i in range(0, len(p) - 1):
            ax, ay = p[i]
            bx, by = p[i + 1]
            ll = math.hypot(bx - ax, by - ay)
            if 1.2 <= ll <= 7.0:
                segs.append((ax, ay, bx, by, ll))
    segs.sort(key=lambda s: -s[4])
    segs = segs[:760]
    rng.shuffle(segs)
    for (ax, ay, bx, by, ll) in segs:
        midx, midy = (ax + bx) * 0.5, (ay + by) * 0.5
        col = ink_color(midx, midy, strength=0.80)
        if add_quad((ax, ay, midx, midy, bx, by), col,
                    rng.uniform(0.85, 1.55), "accent", 1, {"roi": "accent"}):
            acc_n += 1
print("accent", acc_n)

# ---------------- order + strict serial timing ----------------
# 不再加 4px 網格修正筆：密集短筆會在 480px 輸出形成可見白色格紋。
group_order = (["tone%d_bg" % k for k in range(5)] +
               ["tone%d_fg" % k for k in range(5)] + ["detail", "contour", "accent"])


def group_key(s):
    if s["g"].startswith("tone"):
        return s["g"] + ("_fg" if s["fg"] else "_bg")
    return s["g"]


ordered = []
for g in group_order:
    bucket = [s for s in strokes if group_key(s) == g]
    rng.shuffle(bucket)
    ordered.extend(bucket)

# fill in group ids for transport
gid = {g: i for i, g in enumerate(["under"] + ["bg%d" % k for k in range(5)] +
                                  ["fg%d" % k for k in range(5)] + ["detail", "contour", "accent"])}


def pack_group(s):
    g = s["g"]
    if g.startswith("tone"):
        k = int(g[4:])
        return gid["fg%d" % k] if s["fg"] else gid["bg%d" % k]
    return gid[g]


DUR = {"under": 6.4, "tone0": 3.0, "tone1": 3.0, "tone2": 3.0, "tone3": 3.0, "tone4": 3.0,
       "detail": 1.9, "contour": 2.6, "accent": 3.2}
LEAD = 900
TAIL = 7000

t = LEAD
out = []
for s in ordered:
    dur = DUR[s["g"]] * rng.uniform(0.91, 1.09)
    dur_ms = max(1, int(round(dur)))
    start = int(round(t))
    out.append((s["d"], s["color"], round(s["w"] * 10), start, dur_ms, pack_group(s)))
    t += dur_ms
total_ms = int(round(t + TAIL))
print("strokes", len(out), "duration_ms", total_ms, "min", total_ms / 60000.0)

# ---------------- save JSON ----------------
meta = dict(w=W, h=H, duration=total_ms, lead=LEAD, tail=TAIL,
            strokes=len(out), layers=[int(a) for a in layer_area],
            tone_centers=[[round(float(v), 4) for v in c] for c in tone_centers],
            groups=["under"] + ["bg%d" % k for k in range(5)] + ["fg%d" % k for k in range(5)] +
                   ["detail", "contour", "accent"])
payload = json.dumps({"meta": meta, "strokes": out}, ensure_ascii=False, separators=(",", ":"))
with open(OUT_JSON, "w", encoding="utf-8") as f:
    f.write(payload)
print("json MB", os.path.getsize(OUT_JSON) / 1e6)

# ---------------- preview render ----------------
COLORS_BGR = []
for s in ordered:
    hx = s["color"].lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    COLORS_BGR.append((b, g, r))

preview = cv2.resize(BASE_SMALL, (W, H), interpolation=cv2.INTER_LINEAR)
i20, i45, i72 = int(len(ordered) * 0.20), int(len(ordered) * 0.45), int(len(ordered) * 0.72)
for i, s in enumerate(ordered):
    cv2.polylines(preview, [np.round(s["pts"]).astype(np.int32)], False,
                  COLORS_BGR[i], max(1, int(round(s["w"]))), cv2.LINE_AA)
    if i == i20:
        cv2.imwrite("preview_20.png", preview)
    if i == i45:
        cv2.imwrite("preview_45.png", preview)
    if i == i72:
        cv2.imwrite("preview_72.png", preview)
cv2.imwrite("preview_final.png", preview)

diff = cv2.absdiff(preview, img).astype(np.float32)
print("MAE", float(diff.mean()), "PSNR", float(cv2.PSNR(preview, img)))
side = np.concatenate([img, preview], 1)
cv2.imwrite("side_by_side.png", side)

# compressed metadata for html
z = base64.b64encode(zlib.compress(payload.encode("utf-8"), 9)).decode("ascii")
with open("strokes.b64", "w", encoding="ascii") as f:
    f.write(z)
print("b64 MB", len(z) / 1e6)
