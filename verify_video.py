# -*- coding: utf-8 -*-
"""Verify the rendered MP4: probe, canvas crops, contact sheet, quality metrics."""
import cv2, numpy as np, subprocess, json, os, sys

FFMPEG = r"tools\ffmpeg\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
SRC = sys.argv[1] if len(sys.argv) > 1 else "painting_process.mp4"
RECT = (797, 132, 480, 858)  # x,y,w,h

def grab(t, out):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
                    "-i", SRC, "-frames:v", "1", "-update", "1", out], check=True)
    return cv2.imread(out)

meta = json.loads(subprocess.check_output([
    r"tools\ffmpeg\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe",
    "-v", "error", "-select_streams", "v:0", "-show_entries",
    "stream=width,height,r_frame_rate,nb_frames,codec_name,profile,pix_fmt,bit_rate",
    "-show_entries", "format=duration,size,bit_rate", "-of", "json", SRC]))
print(json.dumps(meta, indent=2))
DUR = float(meta["format"]["duration"])
NFRAMES = int(meta["streams"][0].get("nb_frames") or round(DUR * 30))

def grab_last(out):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", SRC,
                    "-vf", f"select=eq(n\\,{NFRAMES-1})", "-frames:v", "1",
                    "-fps_mode", "passthrough", out], check=True)
    return cv2.imread(out)

orig = cv2.imread("image.jpg")
x, y, w, h = RECT
shots = []
for frac in (0.0, 0.20, 0.45, 0.72, 1.0):
    t = min(DUR - 0.05, DUR * frac)
    full = grab_last(f"verify_{int(frac*100)}.png") if frac == 1.0 else grab(t, f"verify_{int(frac*100)}.png")
    crop = full[y:y+h, x:x+w]
    cv2.imwrite(f"verify_canvas_{int(frac*100)}.png", crop)
    shots.append((frac, crop))
    print("frame", frac, "mean", round(float(crop.mean()), 2))

# contact sheet: original + 5 stages
th = 520
def fit(im):
    s = th / im.shape[0]
    return cv2.resize(im, (int(im.shape[1]*s), th), interpolation=cv2.INTER_AREA)
tiles = [fit(orig)] + [fit(c) for _, c in shots]
pad = 12
sheet = np.full((th + 2*pad, sum(t.shape[1] for t in tiles) + pad*(len(tiles)+1), 3), 18, np.uint8)
xx = pad
for t in tiles:
    sheet[pad:pad+th, xx:xx+t.shape[1]] = t
    xx += t.shape[1] + pad
cv2.imwrite("video_contact_sheet.png", sheet)

# final-frame fidelity vs offline preview / original
final = shots[-1][1]
big = cv2.resize(final, (orig.shape[1], orig.shape[0]), interpolation=cv2.INTER_CUBIC)
ref = cv2.imread("preview_final.png")
print("final vs preview MAE", float(np.abs(big.astype(np.float32)-ref).mean()),
      "PSNR", float(cv2.PSNR(big, ref)))
print("final vs original MAE", float(np.abs(big.astype(np.float32)-orig).mean()),
      "PSNR", float(cv2.PSNR(big, orig)))
src480 = cv2.imread("src_final_canvas.png")
if src480 is not None and src480.shape == final.shape:
    print("final vs browser@480 MAE", float(np.abs(final.astype(np.float32)-src480.astype(np.float32)).mean()),
          "PSNR", float(cv2.PSNR(final, src480)))
print("output", os.path.getsize(SRC), "bytes")
