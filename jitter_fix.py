"""Jitter the residual-correction dabs so they don't form a visible lattice.

Input : strokes_fix.json  (151,571 strokes; gid 14 = 45,000 dabs on a 4px grid)
Output: strokes_jitter.json  (same timings; jittered gid-14 dabs)
"""
import json
import random
import re
from pathlib import Path

SRC = Path("strokes_fix.json")
DST = Path("strokes_jitter.json")
PATH_RE = re.compile(r"M([-\d.]+) ([-\d.]+)Q([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)")

d = json.loads(SRC.read_text(encoding="utf-8"))
rng = random.Random(7)
jittered = 0

for s in d["strokes"]:
    if s[5] != 14:
        continue
    m = PATH_RE.fullmatch(s[0])
    if not m:
        continue
    v = [float(x) for x in m.groups()]
    for i in range(0, 6, 2):
        v[i] += rng.uniform(-2.4, 2.4)
        v[i + 1] += rng.uniform(-2.4, 2.4)
    s[0] = "M%.1f %.1fQ%.1f %.1f %.1f %.1f" % tuple(v)
    s[2] = int(round(rng.uniform(11, 20)))  # width x10 => 1.1-2.0 px
    jittered += 1

DST.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"jittered {jittered:,} dabs, N={len(d['strokes']):,}, duration={d['meta']['duration']} ms")
