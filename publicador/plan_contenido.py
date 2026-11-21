"""Arma y amplía el calendario de publicación de Clipardo (calendario\\publicacion.csv).

Uso:  plan_contenido.py            -> suma los clips terminados que todavía no están en el calendario
      plan_contenido.py --aprobar  -> pasa todo lo "pendiente de ok" a "programado" (el publicador lo sube a su hora)

- Toma cada clip terminado de clips\\final\\<job>\\NN_*.mp4 (con su .json en clips\\raw) que no esté ya en el calendario.
- Valoración 0-100 = puntaje de la selección + extra por GTA VI mientras está en su pico (config abajo).
- Cuenta (clipardo.config.json): streamers de "streamers_cuenta_local" -> cuenta "arg"; el resto -> cuenta "todo".
- Ordena por valoración sin repetir streamer seguido y llena los horarios libres desde el próximo hueco.
(calendario.csv lo sigue escribiendo clip-finder como registro de cortes; este archivo es el de publicación.)
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
RAIZ = R.HOME
PUB = RAIZ / "calendario" / "publicacion.csv"
ARGENTINOS = R.STREAMERS_LOCALES
HORARIOS = {c: [f"{h:02d}:00" for h in range(10, 24)] for c in R.CUENTAS}  # uno por hora de 10:00 a 23:00 = 14 por día (pedido del usuario 2026-11-20; antes cada media hora y restringieron la cuenta general)
EXTRA_GTA = 8  # GTA VI está en su pico (lanzamiento 2026-11): esos clips van primero
CAMPOS = ["fecha_publicacion", "cuenta", "streamer", "valoracion", "titulo", "video", "caption", "estado", "media_id", "job"]


TOPGLOBALES = {"coker", "goncho", "zeko", "joaco"}


def formato_caption(cap, titulo, cuenta, streamer):
    """Estilo desde 2026-11-19 (copiado de @gonchotwm / @kickcl1pstv): TÍTULO EN MAYÚSCULAS primero y 7-10 hashtags."""
    if not cap or not titulo or cap.startswith(titulo.upper()):
        return cap
    lineas = cap.split("\n")
    tags = " ".join(l for l in lineas if l.startswith("#")).split()
    cuerpo = "\n".join(l for l in lineas if not l.startswith("#")).strip()
    extra = ["#fyp", "#parati"] + (["#topglobales"] if streamer in TOPGLOBALES else []) + (["#argentina"] if cuenta == "arg" else [])
    for e in extra:
        if e not in tags:
            tags.insert(len(tags) - 1 if tags and tags[-1] == "#clipardo" else len(tags), e)
    if "#gta6" in tags and "#gtavi" not in tags:
        tags.insert(tags.index("#gta6") + 1, "#gtavi")
    return f"{titulo.upper()}\n{cuerpo}\n{' '.join(tags)}"


def es_gta(d):
    t = " ".join(str(d.get(k, "")) for k in ("titulo", "titulo_pantalla", "hook_text", "caption", "motivo")).lower()
    return d.get("receta") == "gta" or "gta" in t


def clips_terminados():
    for carpeta in sorted((RAIZ / "clips" / "final").iterdir()):
        if not carpeta.is_dir():
            continue
        for mp4 in sorted(carpeta.glob("[0-9][0-9]_*.mp4")):
            if mp4.stem.endswith(("_ffmpeg", "_remotion")):
                continue
            meta = RAIZ / "clips" / "raw" / carpeta.name / f"{mp4.stem}.json"
            if not meta.exists():
                continue
            d = json.loads(meta.read_text(encoding="utf-8"))
            yield carpeta.name, mp4, d


def leer():
    if not PUB.exists():
        return []
    return list(csv.DictReader(PUB.open(encoding="utf-8-sig")))


def guardar(filas):
    filas.sort(key=lambda f: f["fecha_publicacion"])
    with PUB.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def huecos(cuenta, ocupados, desde):
    dia = desde.date()
    while True:
        for h in HORARIOS[cuenta]:
            t = dt.datetime.combine(dia, dt.time.fromisoformat(h))
            if t > desde and t.isoformat(timespec="minutes") not in ocupados:
                yield t
        dia += dt.timedelta(days=1)


def intercalar(items):
    """Mejor valorado primero, pero evitando el mismo streamer dos veces seguidas."""
    items = sorted(items, key=lambda x: -x["valoracion"])
    out = []
    while items:
        i = next((k for k, x in enumerate(items) if not out or x["streamer"] != out[-1]["streamer"]), 0)
        out.append(items.pop(i))
    return out


def ampliar():
    filas = leer()
    ya = {f["video"] for f in filas}
    nuevos = {c: [] for c in R.CUENTAS}
    for job, mp4, d in clips_terminados():
        if str(mp4) in ya:
            continue
        streamer = (d.get("streamer") or job.split("-")[0]).lower()
        if " " in streamer or "|" in streamer:  # títulos de canal de YouTube ("DaniRep | +6 vídeos…")
            streamer = job.split("-")[0].lower()
        cuenta = "arg" if streamer in ARGENTINOS else "todo"
        val = min(100, int(float(d.get("score") or 55)) + (EXTRA_GTA if es_gta(d) else 0))
        nuevos[cuenta].append({"cuenta": R.usuario(cuenta), "streamer": streamer, "valoracion": val,
                               "titulo": d.get("titulo_pantalla") or d.get("titulo", ""), "video": str(mp4),
                               "caption": formato_caption(d.get("caption", ""), d.get("titulo_pantalla") or d.get("titulo", ""), cuenta, streamer), "estado": "pendiente de ok", "media_id": "", "job": job})
    manana = dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time(0, 0))
    for c, items in nuevos.items():
        ocupados = {f["fecha_publicacion"] for f in filas if f["cuenta"] == R.usuario(c)}
        desde = max([manana] + [dt.datetime.fromisoformat(o) for o in ocupados])
        g = huecos(c, ocupados, desde)
        for it in intercalar(items):
            it["fecha_publicacion"] = next(g).isoformat(timespec="minutes")
            filas.append(it)
    guardar(filas)
    print(f"Agregados: {', '.join(f'{c} {len(v)}' for c, v in nuevos.items())}. Total en calendario: {len(filas)}")


def aprobar():
    filas = leer()
    n = 0
    for f in filas:
        if f["estado"] == "pendiente de ok":
            f["estado"], n = "programado", n + 1
    guardar(filas)
    print(f"Programados: {n}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    aprobar() if "--aprobar" in sys.argv else ampliar()
