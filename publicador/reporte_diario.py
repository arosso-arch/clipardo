"""Reporte diario de Clipardo (sin tokens de Claude). Lo corre la tarea "Reporte Clipardo" a las 23:45.

Uso (Python de <CLIPARDO_HOME>\\.venv, con -I):
  reporte_diario.py                 -> reporte de hoy
  reporte_diario.py --dia 2026-11-19
  reporte_diario.py --sin-api       -> solo calendario y disco (no consulta Instagram)

Escribe reportes\\AAAA-MM-DD.md y una copia en estado-hoy.md (lo que se lee a la mañana).
Guarda las métricas en reportes\\historial.csv (una fila por Reel por día) y reportes\\seguidores.csv, para la
revisión semanal (sesión "Aprender"). Nunca imprime ni guarda tokens.
"""
import argparse
import csv
import datetime as dt
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import publicador as pub  # noqa: E402  (reusa cuenta(), llamar(), revision_ok() y la ruta del calendario)

R = pub.R
RAIZ = R.HOME
REP = RAIZ / "reportes"
HIST = REP / "historial.csv"
SEG = REP / "seguidores.csv"
CUENTAS = tuple(R.CUENTAS)
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
METRICAS = ["views", "reach", "likes", "comments", "shares", "saved", "ig_reels_avg_watch_time"]


def fecha(f):
    try:
        return dt.datetime.fromisoformat(f.get("fecha_publicacion", ""))
    except ValueError:
        return None


def corta(n):
    n = int(n or 0)
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def insights(c, media_id):
    """Métricas de un Reel. Si la API rechaza alguna métrica, reintenta sin el tiempo de visualización."""
    for campos in (METRICAS, METRICAS[:-1]):
        try:
            r = pub.llamar(c, "GET", f"{media_id}/insights", {"metric": ",".join(campos)})
            return {d["name"]: (d.get("values") or [{}])[0].get("value", 0) for d in r.get("data", [])}
        except RuntimeError as e:
            err = str(e)
    # sin permiso de estadísticas (instagram_manage_insights): al menos likes y comentarios del Reel
    try:
        r = pub.llamar(c, "GET", media_id, {"fields": "like_count,comments_count"})
        return {"likes": r.get("like_count", 0), "comments": r.get("comments_count", 0), "_basico": err}
    except RuntimeError:
        raise RuntimeError(err) from None


def seguidores(c):
    r = pub.llamar(c, "GET", c["id"] or "me", {"fields": "followers_count"})
    return int(r.get("followers_count", 0))


def guardar_csv(ruta, campos, filas, clave):
    """Actualiza (o agrega) filas en un CSV usando 'clave' como identificador."""
    viejas = list(csv.DictReader(ruta.open(encoding="utf-8-sig"))) if ruta.exists() else []
    nuevas = {clave(f): f for f in filas}
    out = [nuevas.pop(clave(v), v) for v in viejas] + list(nuevas.values())
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", help="AAAA-MM-DD (por defecto hoy)")
    ap.add_argument("--sin-api", action="store_true")
    a = ap.parse_args()
    dia = dt.date.fromisoformat(a.dia) if a.dia else dt.date.today()
    ahora = dt.datetime.now()
    REP.mkdir(exist_ok=True)

    filas = list(csv.DictReader(pub.CAL.open(encoding="utf-8-sig"))) if pub.CAL.exists() else []
    alertas, L = [], []

    # ---- 1) publicación del día y cola
    L.append("## Publicación\n")
    L.append("| Cuenta | Publicados hoy | Con reintentos | Errores | En cola | Cola alcanza hasta | No pasan revisión |")
    L.append("|---|---|---|---|---|---|---|")
    for n in CUENTAS:
        mias = [f for f in filas if f.get("cuenta", "").endswith(n)]
        hoy = [f for f in mias if f.get("estado") == "publicado" and (fecha(f) or ahora).date() == dia]
        reint = [f for f in hoy if int(f.get("intentos") or 0) > 0]
        errores = [f for f in mias if f.get("estado") == "error"]
        cola = sorted((f for f in mias if f.get("estado") == "programado"), key=lambda f: f["fecha_publicacion"])
        malos = [f for f in cola if not pub.revision_ok(f["video"])]
        hasta = fecha(cola[-1]) if cola else None
        L.append(f"| clipardo.{n} | {len(hoy)} | {len(reint)} | {len(errores)} | {len(cola)} | "
                 f"{DIAS[hasta.weekday()]} {hasta:%d/%m %H:%M} | {len(malos)} |" if hasta else
                 f"| clipardo.{n} | {len(hoy)} | {len(reint)} | {len(errores)} | 0 | — | 0 |")
        if not cola or hasta < ahora + dt.timedelta(hours=24):
            alertas.append(f"clipardo.{n}: la cola se termina en menos de 24 h → clipear/aprobar una tanda.")
        if errores:
            alertas.append(f"clipardo.{n}: {len(errores)} Reel(s) en error definitivo: "
                           + ", ".join(Path(f['video']).name for f in errores[:5]))
        if malos:
            alertas.append(f"clipardo.{n}: {len(malos)} Reel(s) en cola no pasan `revisar.py` (se saltean).")

    # ---- 2) métricas de Instagram
    if not a.sin_api:
        L.append("\n## Cómo les fue\n")
        hist, seg_filas = [], []
        for n in CUENTAS:
            try:
                c = pub.cuenta(n)
            except SystemExit as e:
                alertas.append(f"clipardo.{n}: {e}")
                continue
            # seguidores y diferencia con el último registro
            try:
                s = seguidores(c)
                prev = [r for r in (csv.DictReader(SEG.open(encoding="utf-8-sig")) if SEG.exists() else [])
                        if r["cuenta"] == n and r["dia"] < dia.isoformat()]
                delta = s - int(prev[-1]["seguidores"]) if prev else None
                seg_filas.append({"dia": dia.isoformat(), "cuenta": n, "seguidores": s})
                L.append(f"**clipardo.{n}**: {s} seguidores"
                         + (f" ({delta:+d} desde el {prev[-1]['dia'][8:]}/{prev[-1]['dia'][5:7]})" if delta is not None
                            else " (primer registro)") + "\n")
            except RuntimeError as e:
                L.append(f"**clipardo.{n}**: no pude leer seguidores ({str(e)[:90]})\n")

            # Reels publicados en las últimas 72 h
            recientes = [f for f in filas if f.get("cuenta", "").endswith(n) and f.get("estado") == "publicado"
                         and f.get("media_id") and fecha(f) and ahora - fecha(f) < dt.timedelta(hours=72)]
            datos, fallo = [], None
            for f in recientes:
                try:
                    m = insights(c, f["media_id"])
                except RuntimeError as e:
                    fallo = str(e)
                    continue
                horas = (ahora - fecha(f)).total_seconds() / 3600
                d = {"dia": dia.isoformat(), "cuenta": n, "media_id": f["media_id"],
                     "publicado": f["fecha_publicacion"], "horas": round(horas), "streamer": f.get("streamer", ""),
                     "job": f.get("job", ""), "video": Path(f["video"]).name, **{k: m.get(k, 0) for k in METRICAS}}
                datos.append(d)
                hist.append(d)
            if fallo and not datos:
                L.append(f"- No pude leer estadísticas: `{fallo[:160]}`\n  (si dice permiso: falta "
                         "`instagram_manage_insights` en el token)\n")
                continue
            # sin permiso de estadísticas solo hay likes/comentarios: se ordena por likes y se avisa
            clave = "views" if any(int(d["views"] or 0) for d in datos) else "likes"
            if clave == "likes" and datos:
                L.append("- Sin permiso de estadísticas (`instagram_manage_insights`): ordeno por likes.")
            maduros = sorted((d for d in datos if d["horas"] >= 12), key=lambda d: -int(d[clave] or 0))
            ayer = [d for d in datos
                    if dt.datetime.fromisoformat(d["publicado"]).date() == dia - dt.timedelta(days=1)]
            if ayer:
                prom = sum(int(d[clave] or 0) for d in ayer) / len(ayer)
                nombre = "vistas" if clave == "views" else "likes"
                L.append(f"- Reels de ayer: {len(ayer)}, **{prom:.1f} {nombre} promedio** por Reel")

            def linea(d):
                avg = d.get("ig_reels_avg_watch_time") or 0
                if clave == "likes":
                    return (f"  - {d['likes']} likes · {d['comments']} comentarios — `{d['video']}` "
                            f"({d['streamer'] or d['job']}, hace {d['horas']} h)")
                return (f"  - {corta(d['views'])} vistas · {corta(d['reach'])} alcance · {d['shares']} compartidos · "
                        f"{d['saved']} guardados" + (f" · {avg / 1000:.1f} s promedio" if avg else "")
                        + f" — `{d['video']}` ({d['streamer'] or d['job']}, hace {d['horas']} h)")
            if maduros:
                L.append("- Mejores (con 12 h o más):")
                L += [linea(d) for d in maduros[:3]]
                if len(maduros) > 3:
                    L.append("- Peores:")
                    L += [linea(d) for d in maduros[-3:][::-1]]
            else:
                L.append("- Todavía no hay Reels con 12 h o más para comparar.")
            L.append("")
        if hist:
            guardar_csv(HIST, list(hist[0].keys()), hist, lambda r: (r["dia"], r["media_id"]))
        if seg_filas:
            guardar_csv(SEG, ["dia", "cuenta", "seguidores"], seg_filas, lambda r: (r["dia"], r["cuenta"]))

    # ---- 3) disco
    libre = shutil.disk_usage(RAIZ.anchor).free / 2**30
    if libre < 30:
        alertas.append(f"Disco D con {libre:.0f} GB libres: correr `limpiar.py` o vaciar la Papelera.")

    cab = [f"# Clipardo — {dia:%d/%m/%Y}", f"_Generado {ahora:%d/%m %H:%M}. Disco D: {libre:.0f} GB libres._\n"]
    pend = RAIZ / "pendientes.md"  # recordatorios a mano (borrar la línea cuando esté hecho)
    if pend.exists() and pend.read_text(encoding="utf-8").strip():
        cab += ["## 📌 Pendientes\n", pend.read_text(encoding="utf-8").strip(), ""]
    cab += ["## ⚠️ Para mirar\n"] + [f"- {x}" for x in alertas] + [""] if alertas else ["Sin alertas. ✅\n"]
    texto = "\n".join(cab + L) + "\n"
    (REP / f"{dia.isoformat()}.md").write_text(texto, encoding="utf-8")
    (RAIZ / "estado-hoy.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
