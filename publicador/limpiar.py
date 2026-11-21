"""Libera disco (pedido del usuario 2026-11-19: "si los clips ya están subidos, liberá ese espacio").

Uso:  python -I limpiar.py [--simular]

Borra SOLO lo que ya no hace falta:
1. Reels ya PUBLICADOS (calendario/publicacion.csv): el .mp4 final, su base de edición (capcut/NN_base.mp4), la
   versión _ffmpeg, el clip en bruto (clips/raw) y la copia liviana de tmp/ig_*.mp4. Quedan los .json/.jpg (pesan poco).
2. jobs/<job>/audio.pcm de streams ya cortados (hay clips en clips/raw/<job>): la transcripción queda, así que se
   puede volver a elegir clips del mismo stream (el corte baja de nuevo solo esos tramos).
3. tmp/ig_*.mp4 y tmp/prueba*.mp4 de más de 1 día.
Nunca toca Reels programados o pendientes.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
RAIZ = R.HOME
CAL = RAIZ / "calendario" / "publicacion.csv"


def borrar(p, simular, total):
    if p.exists():
        total[0] += p.stat().st_size
        if not simular:
            p.unlink()


def limpiar(simular=False):
    total = [0]
    if CAL.exists():
        for f in csv.DictReader(CAL.open(encoding="utf-8-sig")):
            if f.get("estado") != "publicado" or not f.get("video"):
                continue
            v = Path(f["video"])
            job, stem = v.parent.name, v.stem
            for p in (v, v.parent / "capcut" / f"{stem}_base.mp4", v.with_name(f"{stem}_ffmpeg.mp4"),
                      RAIZ / "clips" / "raw" / job / f"{stem}.mp4", RAIZ / "tmp" / f"ig_{stem}.mp4"):
                borrar(p, simular, total)
    for a in (RAIZ / "jobs").glob("*/audio.pcm"):
        if any((RAIZ / "clips" / "raw" / a.parent.name).glob("*.mp4")) or (RAIZ / "clips" / "raw" / a.parent.name / "results.json").exists():
            borrar(a, simular, total)
    lim = time.time() - 86400
    for p in list((RAIZ / "tmp").glob("ig_*.mp4")) + list((RAIZ / "tmp").glob("prueba*.mp4")):
        if p.stat().st_mtime < lim:
            borrar(p, simular, total)
    print(f"{'(simulado) ' if simular else ''}liberado: {total[0] / 2**30:.1f} GB", flush=True)
    return total[0]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true")
    limpiar(ap.parse_args().simular)
