"""Publicador de Reels de Clipardo con la API oficial de Instagram.

Uso (siempre con el Python de <CLIPARDO_HOME>\\.venv y -I):
  publicador.py verificar                         -> prueba los tokens leyendo el usuario de cada cuenta (no publica)
  publicador.py publicar --cuenta arg|todo --video RUTA.mp4 --caption-file RUTA.txt
  publicador.py pendientes [--simular]            -> publica las filas de calendario.csv con estado "programado"
                                                     cuya fecha_publicacion ya pasó, y las marca "publicado"

Los tokens se leen de tokens.env (al lado de este archivo). Nunca se imprimen.
Sube el video directo desde la PC (carga reanudable de Meta): no hace falta hosting.
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
CAL = R.PUBLICACION
LOG = AQUI / "publicaciones.log"
VER = "v25.0"


def cargar_env():
    env = {}
    if not (AQUI / "tokens.env").exists():
        sys.exit("Falta publicador/tokens.env: copiá tokens.env.example como tokens.env y pegá los tokens (ver README).")
    for linea in (AQUI / "tokens.env").read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def cuenta(nombre):
    env = cargar_env()
    tok = env.get(f"CLIPARDO_{nombre.upper()}_TOKEN", "")
    ig_id = env.get(f"CLIPARDO_{nombre.upper()}_ID", "")
    if not tok:
        sys.exit(f"Falta el token de {R.usuario(nombre)} (CLIPARDO_{nombre.upper()}_TOKEN) en tokens.env")
    # tokens "IG..." van por graph.instagram.com; los "EAA..." (Facebook / usuario del sistema) por graph.facebook.com
    host = "https://graph.instagram.com" if tok.startswith("IG") else "https://graph.facebook.com"
    return {"token": tok, "id": ig_id, "host": host, "nombre": nombre}


def llamar(c, metodo, ruta, datos=None):
    url = f"{c['host']}/{VER}/{ruta}"
    datos = dict(datos or {}, access_token=c["token"])
    cuerpo = urllib.parse.urlencode(datos).encode()
    if metodo == "GET":
        url += "?" + cuerpo.decode()
        cuerpo = None
    req = urllib.request.Request(url, data=cuerpo, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise RuntimeError(f"{metodo} {ruta}: HTTP {e.code} {err.replace(c['token'], '***')}") from None


def verificar():
    ok = True
    for n in R.CUENTAS:
        try:
            c = cuenta(n)
            campos = "id,username" if "instagram" in c["host"] else "id,username,followers_count,media_count"
            r = llamar(c, "GET", c["id"] or "me", {"fields": campos})
            print(f"{R.usuario(n)}: OK -> @{r.get('username')} (id {r.get('id')}) vía {c['host'].split('//')[1]}")
            if c["id"] and r.get("id") != c["id"]:
                print(f"  ¡ojo! el token es de otra cuenta (esperaba id {c['id']})")
                ok = False
        except (RuntimeError, SystemExit) as e:
            print(f"{R.usuario(n)}: ERROR {e}")
            ok = False
    return ok


def publicar(nombre, video, caption, intentos=3):
    """Instagram a veces responde "ProcessingFailedError" al subir y al rato anda (2026-11-19): reintenta con un
    contenedor nuevo antes de marcar error."""
    for i in range(intentos):
        try:
            return _publicar(nombre, video, caption)
        except RuntimeError as e:
            if i == intentos - 1 or "ProcessingFailed" not in str(e) and "processing" not in str(e).lower():
                raise
            print(f"  reintento {i + 2}/{intentos} en 30 s ({str(e)[:80]})", flush=True)
            time.sleep(30)


def liviano(video, max_mb=55):
    """Instagram rechaza seguido ("ProcessingFailedError") los archivos muy pesados (95 MB, 2026-11-19). Arriba de
    max_mb se sube una copia a ~9 Mbps (Instagram igual recomprime a menos) en yuv420p / nivel 4.2."""
    video = Path(video)
    if video.stat().st_size < max_mb * 1024 * 1024:
        return video
    R.TMP.mkdir(exist_ok=True)
    out = R.TMP / f"ig_{video.stem}.mp4"
    if not out.exists() or out.stat().st_mtime < video.stat().st_mtime:
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-c:v", "libx264", "-preset", "medium",
                        "-b:v", "9M", "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p", "-profile:v", "high",
                        "-level", "4.2", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    print(f"  subo versión liviana ({video.stat().st_size // 2**20} MB → {out.stat().st_size // 2**20} MB)", flush=True)
    return out


def _publicar(nombre, video, caption):
    c = cuenta(nombre)
    video = liviano(video)
    tam = video.stat().st_size
    # 1) contenedor de Reel con carga reanudable
    r = llamar(c, "POST", f"{c['id']}/media", {"media_type": "REELS", "upload_type": "resumable",
                                                 "caption": caption, "share_to_feed": "true"})
    cont = r["id"]
    uri = r.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VER}/{cont}"
    # 2) subir el archivo
    req = urllib.request.Request(uri, data=video.read_bytes(), method="POST", headers={
        "Authorization": f"OAuth {c['token']}", "offset": "0", "file_size": str(tam)})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"subida: HTTP {e.code} {e.read().decode(errors='replace')}") from None
    # 3) esperar a que Instagram procese el video
    for _ in range(60):
        st = llamar(c, "GET", cont, {"fields": "status_code,status"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram rechazó el video: {st.get('status')}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram tardó demasiado en procesar el video")
    # 4) publicar
    pub = llamar(c, "POST", f"{c['id']}/media_publish", {"creation_id": cont})
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M} clipardo.{nombre} {video.name} -> {pub.get('id')}\n")
    return pub.get("id")


CAMPOS_PUB = ("estado", "media_id", "fecha_publicacion", "intentos")


def guardar(filas_mias):
    """Mezcla en el calendario actual (releído del disco) los cambios de esta vuelta, fila por video."""
    mias = {f["video"]: f for f in filas_mias if f.get("_tocada")}
    actual = list(csv.DictReader(CAL.open(encoding="utf-8-sig")))
    campos = [c for c in (list(actual[0].keys()) if actual else []) if c != "_tocada"]
    for c in CAMPOS_PUB:
        if c not in campos:
            campos.append(c)
    for f in actual:
        m = mias.get(f.get("video"))
        if m:
            for c in CAMPOS_PUB:
                if c in m:
                    f[c] = m[c]
    tmp = CAL.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as out:
        w = csv.DictWriter(out, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(actual)
    tmp.replace(CAL)


def revision_ok(video):
    """True si el Reel pasó el revisor automático (clips\\final\\<job>\\revision\\revisar.json) o si no tiene revisión
    (Reels viejos). False si le quedaron problemas sin arreglar."""
    v = Path(video)
    rj = v.parent / "revision" / "revisar.json"
    if not rj.exists():
        return True
    try:
        for r in json.loads(rj.read_text(encoding="utf-8")):
            if r.get("clip") == v.name:
                return not r.get("despues", r.get("problemas"))
    except (ValueError, OSError):
        return True
    return True


def pendientes(simular=False):
    # candado: nunca dos publicadores a la vez (2026-11-19 un reintento a mano + la vuelta automática publicaron
    # el mismo Reel dos veces)
    lock = CAL.parent / "publicando.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < 15 * 60:
        return print("Ya hay otro publicador corriendo; salteo esta vuelta.")
    lock.write_text(str(os.getpid()))
    try:
        r = _pendientes(simular)
        if not simular:
            try:  # libera disco de lo ya publicado (pedido del usuario 2026-11-19)
                sys.path.insert(0, str(Path(__file__).parent))
                import limpiar
                limpiar.limpiar()
            except Exception as e:
                print(f"  limpieza: {e}")
        return r
    finally:
        lock.unlink(missing_ok=True)


def _pendientes(simular=False):
    if not CAL.exists():
        return print("Todavía no hay calendario de publicación.")
    filas = list(csv.DictReader(CAL.open(encoding="utf-8-sig")))
    campos = list(filas[0].keys()) if filas else []
    ahora = dt.datetime.now()
    hechos = 0
    for f in filas:
        if f.get("estado") != "programado" or not f.get("fecha_publicacion"):
            continue
        cuando = dt.datetime.fromisoformat(f["fecha_publicacion"])
        if cuando > ahora:
            continue
        n = R.clave_de(f.get("cuenta", ""))
        # pausa por cuenta: si existe calendario\pausa_<cuenta> no se publica en esa cuenta (2026-11-20: la cuenta general
        # restringida por Instagram, se pausa hasta que la habiliten). Borrar el archivo para reanudar.
        if (CAL.parent / f"pausa_{n}").exists():
            continue
        if not revision_ok(f["video"]):
            # no pasó la autocorrección: sale el próximo de la misma cuenta que sí la pasó y este queda en su lugar
            # (pedido del usuario 2026-11-19: "si alguno no cumple, subí otro para no demorar")
            otro = next((g for g in sorted(filas, key=lambda g: g["fecha_publicacion"])
                         if g is not f and g.get("estado") == "programado" and g.get("cuenta") == f.get("cuenta")
                         and g["fecha_publicacion"] > f["fecha_publicacion"] and revision_ok(g["video"])), None)
            print(f"{cuando:%d/%m %H:%M} clipardo.{n}: {Path(f['video']).name} no pasó la revisión → "
                  f"{'sale ' + Path(otro['video']).name if otro else 'no hay reemplazo, queda para después'}", flush=True)
            if not otro:
                continue
            f["fecha_publicacion"], otro["fecha_publicacion"] = otro["fecha_publicacion"], f["fecha_publicacion"]
            f["_tocada"] = otro["_tocada"] = True
            f = otro
        print(f"{'(simulado) ' if simular else ''}{cuando:%d/%m %H:%M} clipardo.{n}: {f.get('video')}", flush=True)
        if simular:
            continue
        try:
            mid = publicar(n, f["video"], f.get("caption", ""))
            f["estado"], f["media_id"] = "publicado", mid or ""
            f["_tocada"] = True
            hechos += 1
        except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
            # pedido del usuario 2026-11-19: "seguí subiendo aunque dé error, buscá soluciones" → no se abandona:
            # se reprograma 5 min después (hasta 4 veces; el usuario pidió reintentar rápido) y el horario lo toma el siguiente de la cola
            n_int = int(f.get("intentos") or 0) + 1
            f["intentos"] = str(n_int)
            f["_tocada"] = True
            # autogestión (pedido del usuario 2026-11-21: "autogestionate si un video no se sube"): el horario no se pierde,
            # el siguiente de la misma cuenta pasa a ahora y el que falló toma su lugar (reintenta en el próximo turno).
            # Tras 4 fallos va al final de la cola una vez más (hasta 8) antes de quedar en "error".
            prog = sorted((g for g in filas if g is not f and g.get("estado") == "programado" and g.get("cuenta") == f.get("cuenta")
                           and g["fecha_publicacion"] > f["fecha_publicacion"]), key=lambda g: g["fecha_publicacion"])
            if n_int < 8 and n_int != 4 and prog:
                sig = prog[0]
                f["fecha_publicacion"], sig["fecha_publicacion"] = sig["fecha_publicacion"], (ahora + dt.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M")
                sig["_tocada"] = True
                print(f"  ERROR ({n_int}/8): sale ahora {Path(sig['video']).name}; este reintenta a las {f['fecha_publicacion'][11:]}: {str(e)[:150]}")
            elif n_int < 8:
                ult = prog[-1]["fecha_publicacion"] if prog else ahora.strftime("%Y-%m-%dT%H:%M")
                f["fecha_publicacion"] = (dt.datetime.fromisoformat(ult) + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
                print(f"  ERROR ({n_int}/8): va al final de la cola ({f['fecha_publicacion']}): {str(e)[:150]}")
            else:
                f["estado"] = "error"
                print(f"  ERROR definitivo tras 8 intentos: {e}")
            if "intentos" not in campos:
                campos.append("intentos")
        # se guarda después de cada uno (así un corte no hace publicar dos veces). Se relee el archivo y se actualizan
        # SOLO las filas que tocó esta vuelta (2026-11-19: escribir la copia vieja pisaba aprobaciones/reordenamientos
        # hechos mientras subía un Reel)
        guardar(filas)
    print(f"Publicados: {hechos}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verificar")
    p = sub.add_parser("publicar")
    p.add_argument("--cuenta", required=True, choices=["arg", "todo"])
    p.add_argument("--video", required=True)
    p.add_argument("--caption-file", required=True)
    q = sub.add_parser("pendientes")
    q.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    if a.cmd == "verificar":
        sys.exit(0 if verificar() else 1)
    if a.cmd == "publicar":
        print("publicado:", publicar(a.cuenta, a.video, Path(a.caption_file).read_text(encoding="utf-8")))
    if a.cmd == "pendientes":
        pendientes(a.simular)


if __name__ == "__main__":
    main()
