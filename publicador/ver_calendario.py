"""Genera <CLIPARDO_HOME>\\calendario.html: calendario de Reels (programados, subidos, errores) por día y cuenta.
Uso: python -I ver_calendario.py [--loop]   (con --loop lo regenera cada 2 min; la página se recarga sola)"""
import csv, sys, time, html, datetime as dt
from pathlib import Path
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
P = R.PUBLICACION
OUT = R.HOME / "calendario.html"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
COLOR = {"publicado": "ok", "programado": "prog", "pendiente de ok": "pend", "error": "err"}

def tarjeta(x):
    v = Path(x["video"]); img = v.with_suffix(".jpg")
    est = x["estado"]; cls = COLOR.get(est, "err" if "error" in est else "prog")
    mini = f'<img src="{img.as_uri()}" loading="lazy">' if img.exists() else '<div class="noimg"></div>'
    play = f'<a href="{v.as_uri()}" target="_blank">' if v.exists() else "<a>"
    rein = f' · {x["intentos"]} reint.' if x.get("intentos") not in ("", "0", None) else ""
    return (f'<div class="card {cls}">{play}{mini}</a><div class="info"><b>{x["fecha_publicacion"][11:16]}</b> '
            f'<span class="st">{html.escape(est)}{rein}</span><div class="t">{html.escape(x["titulo"])}</div>'
            f'<div class="s">{html.escape(x["streamer"])} · {x["valoracion"]}</div></div></div>')

def generar():
    r = list(csv.DictReader(P.open(encoding="utf-8-sig")))
    hoy = dt.date.today(); desde = (hoy - dt.timedelta(days=1)).isoformat()
    r = [x for x in r if x["fecha_publicacion"][:10] >= desde]
    dias = sorted({x["fecha_publicacion"][:10] for x in r})
    tot = {e: sum(x["estado"] == e for x in r if x["fecha_publicacion"][:10] == hoy.isoformat()) for e in ("publicado", "programado")}
    cuerpo = []
    for d in dias:
        f = dt.date.fromisoformat(d); nom = f"{DIAS[f.weekday()]} {f.day}/{f.month}" + (" · HOY" if f == hoy else "")
        cols = "".join(f'<div class="col"><h3>@{c}</h3>' + "".join(tarjeta(x) for x in r if x["fecha_publicacion"][:10] == d and x["cuenta"] == c) + "</div>"
                       for c in R.CUENTAS.values())
        cuerpo.append(f'<section{" class=hoy" if f == hoy else ""} id="d{d}"><h2>{nom}</h2><div class="cols">{cols}</div></section>')
    OUT.write_text(f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta http-equiv="refresh" content="120">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Calendario Clipardo</title><style>
:root{{--bg:#111;--fg:#eee;--mut:#999;--card:#1c1c1c;--ok:#2e9d5b;--prog:#3a6fd8;--pend:#c9a227;--err:#d84a3a}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}}
header{{position:sticky;top:0;background:#000;padding:10px 16px;border-bottom:3px solid #e21d2b;z-index:2}}
header b{{color:#e21d2b}} .mut{{color:var(--mut)}} section{{padding:8px 16px}} h2{{margin:12px 0 6px}}
section.hoy h2{{color:#e21d2b}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:700px){{.cols{{grid-template-columns:1fr}}}} h3{{margin:4px 0;color:var(--mut);font-size:13px}}
.card{{display:flex;gap:8px;background:var(--card);border-left:5px solid var(--prog);margin:6px 0;padding:6px;border-radius:6px}}
.card.ok{{border-color:var(--ok)}} .card.pend{{border-color:var(--pend)}} .card.err{{border-color:var(--err)}}
.card.ok .st{{color:var(--ok)}} .card.prog .st{{color:var(--prog)}} .card.pend .st{{color:var(--pend)}} .card.err .st{{color:var(--err)}}
.card img,.noimg{{width:54px;height:96px;object-fit:cover;border-radius:4px;background:#333;flex:none}}
.t{{font-weight:600;margin:3px 0}} .s{{color:var(--mut);font-size:12px}} .st{{font-size:12px}}
</style></head><body><header><b>CLIPARDO</b> · calendario de Reels · hoy: {tot['publicado']} subidos, {tot['programado']} programados
<span class="mut"> · actualizado {dt.datetime.now():%H:%M} (se recarga solo)</span></header>{''.join(cuerpo)}
<script>document.getElementById('d{hoy.isoformat()}')?.scrollIntoView()</script></body></html>""", encoding="utf-8")

if __name__ == "__main__":
    while True:
        try: generar()
        except Exception as e: print("error:", e)
        if "--loop" not in sys.argv: break
        time.sleep(120)
