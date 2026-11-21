"""Suma los Reels terminados al calendario, aprueba los de los jobs indicados (ya revisados) y reordena:
aprobados primero por valoración (sin repetir streamer seguido), pendientes al final.
Uso: python -I aprobar_y_ordenar.py <job> [<job> ...]"""
import csv, sys, datetime as dt, subprocess
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
P = R.PUBLICACION
import time
lock = P.parent / "publicando.lock"
while lock.exists() and time.time() - lock.stat().st_mtime < 15 * 60:  # no pisar al publicador mientras sube
    time.sleep(10)
subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "plan_contenido.py")], check=False)
r = list(csv.DictReader(P.open(encoding="utf-8-sig"))); f = list(r[0].keys())
jobs = sys.argv[1:]
for x in r:
    if x["estado"] == "pendiente de ok" and any(j in x["video"] for j in jobs):
        x["estado"] = "programado"
lim = (dt.datetime.now() + dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
def orden(lst):
    pend = sorted(lst, key=lambda x: -int(x["valoracion"])); out = []; last = None
    while pend:
        ok = [k for k, x in enumerate(pend) if x["streamer"] != last]; x = pend.pop(ok[0] if ok else 0); out.append(x); last = x["streamer"]
    return out
for c in R.CUENTAS.values():
    fut = [x for x in r if x["cuenta"] == c and x["estado"] in ("programado", "pendiente de ok") and x["fecha_publicacion"] > lim]
    slots = sorted(x["fecha_publicacion"] for x in fut)
    seq = orden([x for x in fut if x["estado"] == "programado"]) + orden([x for x in fut if x["estado"] != "programado"])
    for s, x in zip(slots, seq):
        x["fecha_publicacion"] = s
    print(c, sum(x["estado"] == "programado" for x in fut), "aprobados,", sum(x["estado"] != "programado" for x in fut), "pendientes")
r.sort(key=lambda x: x["fecha_publicacion"])
w = csv.DictWriter(P.open("w", encoding="utf-8-sig", newline=""), fieldnames=f); w.writeheader(); w.writerows(r)
