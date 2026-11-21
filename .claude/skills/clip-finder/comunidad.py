"""Clips de la COMUNIDAD en vivo: los clips que hacen los espectadores en Kick y Twitch, mientras el stream sigue.

Uso:  python -I comunidad.py [--horas 24] [--top 6] [--preparar]

Por qué: los clips que hace la gente ya marcan los mejores momentos al instante y traen cuántas vistas tienen
(selección "a dedo" de miles de espectadores). No hace falta esperar a que termine el directo ni bajar el VOD.

- Kick: API pública kick.com/api/v2/channels/<canal>/clips?sort=view&time=day
- Twitch: yt-dlp twitch.tv/<canal>/clips?filter=clips&range=24hr
Escribe <CLIPARDO_HOME>\\comunidad\\candidatos.md (los mejores de cada canal que todavía no usamos, con vistas, duración y
link). Con --preparar corre clipfinder.py prepare sobre los --top mejores nuevos (son cortos: transcribe en segundos)
y avisa "CLIP COMUNIDAD <job>" en tmp\\comunidad-estado.txt. Claude revisa y corta como siempre
(selections.json con el tramo entero o una parte).
Reglas: no se usan clips de sorteos/casino; spoilers de historia y easter eggs de GTA 6, no (pedido de Rubius).
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).parent
PY = sys.executable
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
YTDLP = str(R.YTDLP)
DIR = R.COMUNIDAD
VISTOS = DIR / "vistos.json"
ESTADO = R.TMP / "comunidad-estado.txt"
sys.path.insert(0, str(AQUI))
from vigilar import CANALES  # noqa: E402

MIN_VISTAS = {"kick": 40, "twitch": 300}   # 2026-11-19: con 15-25 vistas en Kick salían clips sin charla ni remate
MALO = ("sorteo", "casino", "codigo", "código", "stake", "slot", "bono")


def nombre(canal):
    p = canal.rstrip("/").split("/")
    return (p[-2] if p[-1] == "live" else p[-1]).lstrip("@").lower()


def kick(slug, horas):
    req = urllib.request.Request(f"https://kick.com/api/v2/channels/{slug}/clips?sort=view&time=day",
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    out = []
    for c in d.get("clips", []):
        t = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - t).total_seconds() > horas * 3600:
            continue
        out.append({"id": c["id"], "canal": slug, "plataforma": "kick", "vistas": c.get("view_count") or 0,
                    "dur": c.get("duration") or 0, "titulo": c.get("title") or "", "creado": t.isoformat(),
                    "url": f"https://kick.com/{slug}/clips/{c['id']}"})
    return out


def twitch(login, horas):
    rango = "24hr" if horas <= 24 else "7d"
    r = subprocess.run([YTDLP, "--flat-playlist", "-J", "-I", "1:20", "--no-warnings",
                        f"https://www.twitch.tv/{login}/clips?filter=clips&range={rango}"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120)
    d = json.loads(r.stdout or "{}")
    out = []
    for e in d.get("entries") or []:
        ts = e.get("timestamp") or 0
        if ts and time.time() - ts > horas * 3600:
            continue
        out.append({"id": e["url"].rsplit("/", 1)[-1], "canal": login, "plataforma": "twitch", "vistas": e.get("view_count") or 0,
                    "dur": e.get("duration") or 0, "titulo": e.get("title") or "",
                    "creado": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else "", "url": e["url"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=float, default=24)
    ap.add_argument("--top", type=int, default=6, help="cuántos preparar por vuelta (los de más vistas)")
    ap.add_argument("--preparar", action="store_true")
    ap.add_argument("--canales", help="lista separada por comas (por defecto, todos los de Kick/Twitch de vigilar.py)")
    a = ap.parse_args()
    DIR.mkdir(parents=True, exist_ok=True)
    vistos = set(json.loads(VISTOS.read_text(encoding="utf-8"))) if VISTOS.exists() else set()
    quiero = set(a.canales.split(",")) if a.canales else None
    todos = []
    for canal, _, _ in CANALES:
        n = nombre(canal)
        if quiero and n not in quiero:
            continue
        try:
            if "kick.com" in canal:
                todos += kick(n, a.horas)
            elif "twitch.tv" in canal:
                todos += twitch(n, a.horas)
        except Exception as e:  # un canal que falla no frena al resto
            print(f"{n}: {str(e)[:100]}", flush=True)
    nuevos = [c for c in todos if c["id"] not in vistos and c["vistas"] >= MIN_VISTAS[c["plataforma"]]
              and not any(m in c["titulo"].lower() for m in MALO) and 5 <= c["dur"] <= 90]
    nuevos.sort(key=lambda c: -c["vistas"] / MIN_VISTAS[c["plataforma"]])  # Kick y Twitch en la misma escala
    filas = ["| Vistas | Canal | Dur | Título | Creado (UTC) | Link |", "|---|---|---|---|---|---|"]
    filas += [f"| {c['vistas']} | {c['canal']} ({c['plataforma']}) | {c['dur']:.0f}s | {c['titulo'][:50]} | "
              f"{c['creado'][11:16]} | {c['url']} |" for c in nuevos[:40]]
    (DIR / "candidatos.md").write_text(f"# Clips de la comunidad ({datetime.now():%d/%m %H:%M})\n\n" + "\n".join(filas) + "\n",
                                       encoding="utf-8")
    print("\n".join(filas[:16]), flush=True)
    if a.preparar:
        for c in nuevos[:a.top]:
            r = subprocess.run([PY, "-I", str(AQUI / "clipfinder.py"), "prepare", c["url"]], capture_output=True,
                               text=True, encoding="utf-8", errors="ignore")
            job = next((l[4:] for l in r.stdout.splitlines() if l.startswith("JOB=")), None)
            if job:  # si falló (Kick a veces tarda en procesar el clip) se reintenta en la próxima vuelta
                vistos.add(c["id"])
            with ESTADO.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%H:%M} CLIP COMUNIDAD {job or 'FALLÓ ' + c['url']} | {c['vistas']} vistas | {c['titulo'][:40]}\n")
            print(f"preparado {c['canal']} {c['vistas']} vistas -> {job}", flush=True)
        VISTOS.write_text(json.dumps(sorted(vistos)), encoding="utf-8")


if __name__ == "__main__":
    main()
