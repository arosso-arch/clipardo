"""Paso final de cada Reel: capa de efectos con Remotion sobre la edición de ig-editor.

Uso:  <CLIPARDO_HOME>\\.venv\\Scripts\\python.exe -I remotion_final.py <job> [--solo 03]

Necesita haber corrido antes `igeditor.py render <job> --capcut` (deja en clips\\final\\<job>\\capcut\\ el video base
sin textos y el .json con subtítulos con seguimiento, colores, golpe y posición de la marca).
Remotion agrega: subtítulos con rebote que siguen la cara, zoom de golpe con desenfoque en el remate y la marca
@clipardo. El resultado REEMPLAZA a clips\\final\\<job>\\NN.mp4 (la versión FFmpeg intermedia no se guarda).
Todo en el disco D (proyecto, caché de npm y temporales): el disco C tiene poco espacio.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
PROYECTO = R.REMOTION
FINAL = R.CLIPS / "final"
CFG = json.loads((Path(__file__).resolve().parent / "config.json").read_text(encoding="utf-8"))


def lugar_tarjeta(c, inicio, dur):
    """Elige dónde poner la tarjeta "Seguir": la altura que menos tapa caras y subtítulos mientras está.
    Si ningún lugar está libre, no va tarjeta en ese clip (None)."""
    sg = CFG.get("seguir", {})
    alto = 165
    ocupado = []  # (y0, y1) que no hay que tapar en esa ventana de tiempo
    if c.get("tipo") == "gaming":
        ocupado.append((0, 760))  # la cara del streamer
    for t, b in c.get("bandas_t") or []:
        if b and inicio <= t <= inicio + dur:
            ocupado.append((b[0], b[1]))
    for s in c["subtitulos"]:
        if s["end"] > inicio and s["start"] < inicio + dur:
            for yy in (s["y"], s.get("y2", s["y"])):
                ocupado.append((yy - 60, yy + 60))
    def choque(y):
        return sum(max(0, min(y + alto, b) - max(y, a)) for a, b in ocupado) / max(1, len(ocupado))
    cands = sg.get("alturas", [236, 520, 1180, 1380])
    mejor = min(cands, key=choque)
    return mejor if choque(mejor) <= sg.get("choque_max_px", 40) else None


def sonidos(c):
    """Efectos solo cuando suman y siempre por debajo de la voz: el remate lleva whoosh+golpe solo si es fuerte."""
    v = dict(CFG.get("sfx", {}).get("volumen", {}))
    if (c.get("golpe_fuerza") or 0) < CFG.get("sfx", {}).get("golpe_min_db", 6):
        v["whoosh"] = v["golpe"] = 0  # remate flojo: un golpe ahí suena forzado
    return v


def render(cfg_path: Path):
    c = json.loads(cfg_path.read_text(encoding="utf-8"))
    stem = cfg_path.stem.replace("_capcut", "")
    outdir = cfg_path.parent.parent
    base = cfg_path.parent / c["video"]
    tmp_video = PROYECTO / "public" / f"_{stem}.mp4"
    shutil.copyfile(base, tmp_video)  # Remotion lee los videos desde public/
    mk = c.get("marca_agua") or {}
    sg = CFG.get("seguir", {})
    # título fijo arriba (estilo virales de TikTok): "titulo_pantalla" del .json del clip; si no hay, el hook en mayúsculas
    tc = CFG.get("titulo", {})
    raw_meta = (R.CLIPS / "raw") / outdir.name / f"{stem}.json"
    rm = json.loads(raw_meta.read_text(encoding="utf-8")) if raw_meta.exists() else {}
    titulo = (rm.get("titulo_pantalla") or (rm.get("hook_text") or "").upper()) if tc.get("activar", True) else ""
    ini = max(1.0, c["duracion"] - sg.get("desde_fin_s", 3.4)) if sg.get("activar", True) else None
    y_card = lugar_tarjeta(c, ini, sg.get("dur_s", 2.8)) if ini is not None else None
    seg = {"inicio": ini if y_card is not None else None, "dur": sg.get("dur_s", 2.8), "usuario": sg.get("usuario", "@clipardo"),
           "y": y_card or 236}
    print(f"{stem}: tarjeta {'y=' + str(y_card) if y_card is not None else 'NO (no hay lugar libre)'} · "
          f"sonidos {sonidos(c)} (remate {c.get('golpe_fuerza')} dB)", flush=True)
    props = {
        "video": tmp_video.name,
        "duracion": c["duracion"],
        "subtitulos": c["subtitulos"],
        "golpe": c.get("golpe") if CFG.get("remotion", {}).get("golpe", True) else None,
        "golpesExtra": c.get("golpes_extra") or [],  # clips de acción (igeditor → accion): pulsos en tiros/choques
        "marca": mk.get("texto", "@clipardo") if mk.get("mostrar", True) else "",
        "marcaPos": c.get("marca_pos") or [[0, c["duracion"], 540, 1380, "centro"]],
        "marcaAlpha": mk.get("alpha", 0.5),
        "tamSub": c.get("tam_sub", 88),
        # en gaming la mitad de arriba es la cara del streamer: el título va en el juego, debajo de los subtítulos
        "titulo": titulo, "tituloY": rm.get("titulo_y") or (((c.get("split") or 760) + 130) if c.get("tipo") == "gaming" else tc.get("y", 200)),  # titulo_y: arreglo de revisar.py
        # tarjeta "Seguir" con el logo Rec, cerca del final (cuando ya engancharon)
        "seguir": seg,
        "sfx": sonidos(c),
    }
    props_path = PROYECTO / f"_{stem}.props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    salida = outdir / f"{stem}_remotion.mp4"
    tmp_d = R.TMP / "remotion"
    tmp_d.mkdir(parents=True, exist_ok=True)
    # todo en D: el disco C tiene poco lugar (Remotion arma sus "bundles" en TEMP)
    env = dict(os.environ, npm_config_cache=str(R.TOOLS / "npm-cache"), TEMP=str(tmp_d), TMP=str(tmp_d))
    rc = CFG.get("remotion", {})
    try:
        r = subprocess.run(["npx.cmd", "remotion", "render", "ClipEfectos", str(salida), f"--props={props_path}",
                            "--codec=h264", f"--crf={rc.get('crf', 16)}", f"--jpeg-quality={rc.get('jpeg_calidad', 95)}",
                            f"--x264-preset={rc.get('x264_preset', 'slow')}", "--log=error", "--timeout=180000"], cwd=PROYECTO, env=env)
        if r.returncode != 0 or not salida.exists():
            sys.exit(f"Falló Remotion en {stem}")
    finally:
        tmp_video.unlink(missing_ok=True)
        props_path.unlink(missing_ok=True)
    final = outdir / f"{stem}.mp4"
    # la versión FFmpeg es intermedia (se puede regenerar): no se guarda, así no se acumulan archivos que no se usan
    salida.replace(final)
    (outdir / f"{stem}_ffmpeg.mp4").unlink(missing_ok=True)
    print(f"{stem}: Remotion OK -> {final}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--solo", help="prefijo del clip, ej. 03")
    a = ap.parse_args()
    d = FINAL / a.job / "capcut"
    cfgs = sorted(d.glob("*_capcut.json"))
    if a.solo:
        cfgs = [p for p in cfgs if p.name.startswith(a.solo)]
    if not cfgs:
        sys.exit(f"No hay *_capcut.json en {d}: corré antes igeditor.py render {a.job} --capcut")
    for p in cfgs:
        render(p)


if __name__ == "__main__":
    main()
