# -*- coding: utf-8 -*-
"""Build the single-file canvas player from strokes.json + image.jpg."""
import base64, json, zlib, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
meta = json.loads((ROOT / "strokes.json").read_text(encoding="utf-8"))
data = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
b64 = base64.b64encode(zlib.compress(data, 9)).decode("ascii")
img = base64.b64encode((ROOT / "image.jpg").read_bytes()).decode("ascii")

tpl = (ROOT / "player_template.html").read_text(encoding="utf-8")
out = (tpl.replace("__META__", json.dumps({"duration": meta["meta"]["duration"], "w": 736, "h": 1315}))
          .replace("__STROKE_B64__", b64)
          .replace("__IMG_URI__", "data:image/jpeg;base64," + img))
(ROOT / "player.html").write_text(out, encoding="utf-8")
print("player.html MB", round(len(out.encode("utf-8")) / 1048576, 2),
      "| data MB", round(len(b64) / 1048576, 2),
      "| strokes", meta["meta"]["strokes"],
      "| duration", meta["meta"]["duration"])
