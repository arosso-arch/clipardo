"""Vigila streamers y avisa cuando termina un directo (para clipearlo enseguida).

Uso:  python -I vigilar.py [--cada 600]
- Revisa cada `--cada` segundos si cada canal está en vivo (yt-dlp, sin bajar nada).
- Cuando un canal que estaba EN VIVO se apaga (y cumple el filtro: siempre, o solo si el título decía GTA),
  busca el VOD, lo agrega a <CLIPARDO_HOME>\\inbox\\links.txt, imprime "TERMINO <canal> <url>" y sale
  (así Claude recibe el aviso). Volver a lanzarlo para seguir vigilando a los demás.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
YTDLP = str(R.YTDLP)
ENCONTRADOS = R.INBOX / "encontrados.txt"
INBOX = R.INBOX / "links.txt"
# (url del canal, url de sus VODs, filtro): "siempre" o "gta" (solo si el título del directo menciona GTA)
CANALES = [
    ("https://www.twitch.tv/rubius", "https://www.twitch.tv/rubius/videos?filter=archives", "siempre"),
    ("https://kick.com/rdjavi", "https://kick.com/rdjavi/videos", "siempre"),  # 2026-11-20: transmite en Kick, no en Twitch (sus clips de GTA 6 hacen 3,3 M en TikTok)
    ("https://kick.com/coker", "https://kick.com/coker/videos", "gta"),
    ("https://kick.com/goncho", "https://kick.com/goncho/videos", "gta"),
    ("https://kick.com/zeko", "https://kick.com/zeko/videos", "gta"),
    ("https://kick.com/davooxeneize", "https://kick.com/davooxeneize/videos", "gta"),
    ("https://kick.com/spreen", "https://kick.com/spreen/videos", "gta"),
    ("https://kick.com/lacobraaa", "https://kick.com/lacobraaa/videos", "gta"),
    # sumados 2026-11-19 (relevantes con GTA VI): argentinos -> .arg, resto -> .todo
    ("https://kick.com/brunenger", "https://kick.com/brunenger/videos", "gta"),
    ("https://kick.com/mernuel", "https://kick.com/mernuel/videos", "gta"),
    ("https://kick.com/robleis", "https://kick.com/robleis/videos", "gta"),
    # 2026-11-20: Momo (Gero, @gero.momo) es kick.com/momoladinastia; kick.com/momo es otra streamer (EE. UU., en inglés)
    ("https://kick.com/momoladinastia", "https://kick.com/momoladinastia/videos", "siempre"),
    ("https://kick.com/coscu", "https://kick.com/coscu/videos", "gta"),
    ("https://kick.com/westcol", "https://kick.com/westcol/videos", "gta"),
    ("https://kick.com/elxokas", "https://kick.com/elxokas/videos", "gta"),
    ("https://www.twitch.tv/auronplay", "https://www.twitch.tv/auronplay/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/ibai", "https://www.twitch.tv/ibai/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/illojuan", "https://www.twitch.tv/illojuan/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/perxitaa", "https://www.twitch.tv/perxitaa/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/elmariana", "https://www.twitch.tv/elmariana/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/thegrefg", "https://www.twitch.tv/thegrefg/videos?filter=archives", "siempre"),
    ("https://www.twitch.tv/quackity", "https://www.twitch.tv/quackity/videos?filter=archives", "siempre"),
    # YouTube (2026-11-19): la URL /live da is_live; el VOD queda primero en /streams. Chat sí se baja.
    ("https://www.youtube.com/@DjMaRiiO/live", "https://www.youtube.com/@DjMaRiiO/streams", "siempre"),
    ("https://www.youtube.com/@TheDaniRep/live", "https://www.youtube.com/@TheDaniRep/streams", "siempre"),
    ("https://www.youtube.com/@Vegetta777/live", "https://www.youtube.com/@Vegetta777/streams", "siempre"),
    ("https://www.youtube.com/@Willyrex/live", "https://www.youtube.com/@Willyrex/streams", "siempre"),
]


def en_vivo(url):
    r = subprocess.run([YTDLP, "-J", "--skip-download", "--no-warnings", url], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=90)
    try:
        d = json.loads(r.stdout)
        return bool(d and d.get("is_live")), (d or {}).get("title") or ""
    except Exception:
        return False, ""


def ultimo_vod(url):
    r = subprocess.run([YTDLP, "--flat-playlist", "-J", "-I", "1", "--no-warnings", url], capture_output=True,
                       text=True, encoding="utf-8", errors="ignore", timeout=120)
    try:
        e = json.loads(r.stdout).get("entries") or []
        return e[0].get("url") if e else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cada", type=int, default=600)
    a = ap.parse_args()
    # el usuario filtra antes de clipear: lo que termina va a ENCONTRADOS (no al inbox); el estado se guarda
    # en disco para que un reinicio de la ventana no pierda qué canales estaban en vivo
    estado = ENCONTRADOS.parent / "vivo.json"
    try:
        vivo = json.loads(estado.read_text(encoding="utf-8"))
    except Exception:
        vivo = {}
    while True:
        hora = datetime.now().strftime("%H:%M")
        for canal, vods, filtro in CANALES:
            try:
                ok, titulo = en_vivo(canal)
            except Exception:
                continue
            partes = canal.rstrip("/").split("/")
            nombre = (partes[-2] if partes[-1] == "live" else partes[-1]).lstrip("@").lower()
            if ok:
                if nombre not in vivo:
                    print(f"[{hora}] en vivo: {nombre} | {titulo[:70]}", flush=True)
                vivo[nombre] = titulo
            elif nombre in vivo:
                t = vivo.pop(nombre)
                if filtro == "gta" and "gta" not in t.lower():
                    print(f"[{hora}] terminó {nombre} (sin GTA en el título, no lo anoto)", flush=True)
                    continue
                time.sleep(120)  # que aparezca el VOD
                url = ultimo_vod(vods)
                with open(ENCONTRADOS, "a", encoding="utf-8") as f:
                    f.write("\t".join([f"{datetime.now():%Y-%m-%d %H:%M}", nombre, url or "(sin VOD todavía)", t[:120]]) + "\n")
                print(f"TERMINO {nombre} {url} | {t[:80]}", flush=True)
            estado.write_text(json.dumps(vivo, ensure_ascii=False), encoding="utf-8")
        time.sleep(a.cada)


if __name__ == "__main__":
    main()
