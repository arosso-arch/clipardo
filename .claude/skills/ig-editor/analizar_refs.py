"""Analiza los Reels de referencia: datos técnicos, cortes, transcripción y hoja de contactos."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
sys.path.insert(0, str(R.SKILLS / "clip-finder"))
import clipfinder  # noqa: E402

REFS = R.REFERENCIAS
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
FF = R.ffmpeg_bin() / "ffmpeg.exe"

vistos = {}
res = []
model = clipfinder.load_model()
for i, v in enumerate(sorted(REFS.glob("*.mp4"))):
    h = hashlib.md5(v.read_bytes()).hexdigest()
    if h in vistos:
        res.append({"archivo": v.name, "duplicado_de": vistos[h]})
        continue
    vistos[h] = v.name
    cap = cv2.VideoCapture(str(v))
    W, H = int(cap.get(3)), int(cap.get(4))
    fps = cap.get(5) or 30
    n = int(cap.get(7))
    dur = n / fps
    # cortes de escena
    p = subprocess.run([str(FF), "-hide_banner", "-i", str(v), "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    cortes = [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", p.stderr)]
    # hoja de contactos: 1 fotograma cada dur/24 s, grilla 6x4
    k = 24
    thumbs = []
    for j in range(k):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((j + 0.5) * n / k))
        ok, fr = cap.read()
        if not ok:
            fr = np.zeros((H, W, 3), np.uint8)
        fr = cv2.resize(fr, (270, int(270 * H / W)))
        cv2.putText(fr, f"{(j + 0.5) * dur / k:.1f}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        thumbs.append(fr)
    filas = [np.hstack(thumbs[r * 6:(r + 1) * 6]) for r in range(4)]
    cv2.imwrite(str(OUT / f"{i:02d}.jpg"), np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 70])
    pcm = subprocess.run([str(FF), "-v", "error", "-i", str(v), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    audio = np.frombuffer(pcm, np.float32)
    segs, _ = model.transcribe(audio, language="es", beam_size=5, vad_filter=True)
    texto = " ".join(s.text.strip() for s in segs)
    r = {"id": i, "archivo": v.name, "res": f"{W}x{H}", "fps": round(fps, 1), "dur": round(dur, 1),
         "cortes": len(cortes), "seg_por_plano": round(dur / (len(cortes) + 1), 2), "t_cortes": cortes[:60], "texto": texto}
    res.append(r)
    print(json.dumps({k2: r[k2] for k2 in ("id", "archivo", "res", "dur", "cortes", "seg_por_plano")}, ensure_ascii=False), flush=True)
(OUT / "analisis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
