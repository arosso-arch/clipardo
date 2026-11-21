"""Aprender de Reels/Shorts virales de clips de streamers (corre en la PC, no gasta tokens).

Uso:
  python -I aprender.py links                      # procesa <CLIPARDO_HOME>\\referencias\\aprender\\links.txt (IG, TikTok, YouTube)
  python -I aprender.py buscar "clips streamers argentinos" [--n 15]   # busca Shorts en YouTube y toma los más vistos
  python -I aprender.py explorar "clips streamers argentinos" --n 40 --top 5   # datos+texto de 40 SIN bajar; edición solo de los 5 más vistos

Por cada video: baja (máx. 720p), transcribe, mide cortes de escena, duración, formato (cara / Discord / gaming /
apilado) y guarda vistas, likes y comentarios. Arma `<CLIPARDO_HOME>\\referencias\\aprender\\resumen.md` (lo único que
lee Claude) con la tabla ordenada por vistas y lo que tienen en común los que más funcionan. Los videos se borran
al terminar (quedan solo los datos y una hoja de 6 cuadros por video).
"""
import os
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
os.environ["HF_HOME"] = str(R.TOOLS / "hf")  # nunca bajar modelos a C
os.environ["TEMP"] = os.environ["TMP"] = str(R.TMP)
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
BASE = R.REFERENCIAS / "aprender"
YTDLP = str(R.YTDLP)
FF = R.ffmpeg_bin() / "ffmpeg.exe"
sys.path.insert(0, str(R.SKILLS / "clip-finder"))
sys.path.insert(0, str(R.SKILLS / "ig-editor"))


def bajar(url, carpeta):
    r = subprocess.run([YTDLP, "--no-playlist", "-q", "--no-warnings", "-f", "b[height<=720]/bv*[height<=720]+ba/b",
                        "--write-info-json", "-o", str(carpeta / "%(id)s.%(ext)s"), url], capture_output=True, text=True)
    return r.returncode == 0


def cortes(mp4):
    p = subprocess.run([str(FF), "-hide_banner", "-i", str(mp4), "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f",
                        "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return len(re.findall(r"pts_time:", p.stderr))


def formato(mp4, dur):
    import igeditor as g
    vw, vh, _ = g.probe(mp4)
    tiles = g.detect_mosaic(mp4, vw, vh)
    if tiles:
        return "discord"
    samples, _ = g.detect_faces(mp4, vw, vh, dur)
    lay = g.choose_layout(samples, "auto", None, vw, vh)
    return {"cara": "una cara", "hablante": "dos caras", "gaming": "gaming", "blur": "sin cara / otro"}.get(lay["modo"], lay["modo"])


def hoja(mp4, dur, out):
    subprocess.run([str(FF), "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps=6/{max(dur, 1):.2f},scale=180:320,tile=6x1",
                    "-frames:v", "1", str(out)])


def buscar_youtube(consulta, n):
    """Busca Shorts en YouTube SIN bajar videos: solo la lista con vistas y duración."""
    r = subprocess.run([YTDLP, "--flat-playlist", "-J", f"ytsearch{n * 3}:{consulta} shorts"], capture_output=True,
                       text=True, encoding="utf-8")
    ents = [e for e in json.loads(r.stdout or "{}").get("entries", []) if (e.get("duration") or 999) <= 90]
    ents.sort(key=lambda e: -(e.get("view_count") or 0))
    return ents[:n]


def vtt_a_texto(vtt):
    out = []
    for l in vtt.splitlines():
        l = re.sub(r"<[^>]+>", "", l).strip()
        if not l or "-->" in l or l.startswith(("WEBVTT", "Kind:", "Language:")) or l.isdigit():
            continue
        if not out or out[-1] != l:
            out.append(l)
    return " ".join(out)


def subtitulos(url, tmp):
    """Solo los subtítulos automáticos (texto): no baja el video."""
    for v in tmp.glob("*"):
        v.unlink()
    subprocess.run([YTDLP, "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "es.*,es",
                    "--sub-format", "vtt", "-q", "--no-warnings", "-o", str(tmp / "%(id)s"), url], capture_output=True)
    f = next(tmp.glob("*.vtt"), None)
    return vtt_a_texto(f.read_text(encoding="utf-8", errors="ignore")) if f else ""


def analizar(url, tmp, model, datos):
    """Análisis de edición completo (baja el video, lo mide y lo borra)."""
    for v in tmp.glob("*"):
        v.unlink()
    if not bajar(url, tmp):
        print("   no se pudo bajar")
        return
    mp4 = next((v for v in tmp.glob("*") if v.suffix in (".mp4", ".webm", ".mkv")), None)
    if not mp4:
        return
    info = json.loads(next(tmp.glob("*.info.json")).read_text(encoding="utf-8"))
    dur = float(info.get("duration") or 30)
    pcm = subprocess.run([str(FF), "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    segs, _ = model.transcribe(np.frombuffer(pcm, np.float32), language="es", beam_size=5, vad_filter=True)
    texto = " ".join(s.text.strip() for s in segs)
    n_cortes = cortes(mp4)
    idv = info.get("id", mp4.stem)
    hoja(mp4, dur, BASE / f"{idv}.jpg")
    datos[url] = {"id": idv, "cuenta": info.get("uploader") or info.get("channel"), "titulo": (info.get("title") or "")[:90],
                  "vistas": info.get("view_count"), "likes": info.get("like_count"), "comentarios": info.get("comment_count"),
                  "dur": round(dur, 1), "seg_por_plano": round(dur / (n_cortes + 1), 2), "formato": formato(mp4, dur),
                  "primeras_palabras": " ".join(texto.split()[:14]), "texto": texto[:600]}
    for v in tmp.glob("*"):
        v.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=["links", "buscar", "explorar", "lista"])
    ap.add_argument("consulta", nargs="?")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--top", type=int, default=5, help="explorar: cuántos de los más vistos se analizan con video")
    a = ap.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    tmp = BASE / "_videos"
    tmp.mkdir(exist_ok=True)
    datos_path = BASE / "datos.json"
    datos = json.loads(datos_path.read_text(encoding="utf-8")) if datos_path.exists() else {}
    explor_path = BASE / "explorar.json"
    explor = json.loads(explor_path.read_text(encoding="utf-8")) if explor_path.exists() else {}
    if a.modo == "explorar":
        # 1) muchos videos, SIN bajarlos: vistas + duración + lo que dicen (subtítulos automáticos)
        ents = buscar_youtube(a.consulta, a.n)
        for e in ents:
            u = e["url"]
            if u in explor:
                continue
            print("· datos:", e.get("title", "")[:60], flush=True)
            explor[u] = {"titulo": (e.get("title") or "")[:90], "cuenta": e.get("channel") or e.get("uploader"),
                         "vistas": e.get("view_count"), "dur": e.get("duration"), "texto": subtitulos(u, tmp)[:500]}
            explor_path.write_text(json.dumps(explor, ensure_ascii=False, indent=1), encoding="utf-8")
        urls = [e["url"] for e in ents[:a.top]]  # 2) solo los más vistos se bajan para estudiar la edición
    elif a.modo == "lista":
        # links juntados del navegador (ej. hashtags de TikTok): datos de todos SIN bajar, edición de los más vistos
        f = Path(a.consulta) if a.consulta else BASE / "lista.txt"
        todos = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")]
        for u in todos:
            if u in explor:
                continue
            r = subprocess.run([YTDLP, "-J", "--skip-download", "--no-warnings", u], capture_output=True, text=True,
                               encoding="utf-8", errors="ignore")
            try:
                i_ = json.loads(r.stdout)
            except Exception:
                continue
            if not i_:  # TikTok suele bloquear a yt-dlp (2026-11): sin datos, se saltea
                continue
            explor[u] = {"titulo": (i_.get("description") or i_.get("title") or "")[:90], "cuenta": i_.get("uploader"),
                         "vistas": i_.get("view_count"), "likes": i_.get("like_count"), "dur": i_.get("duration"),
                         "texto": ""}
            print("·", explor[u]["vistas"], explor[u]["cuenta"], flush=True)
            explor_path.write_text(json.dumps(explor, ensure_ascii=False, indent=1), encoding="utf-8")
        orden = sorted([u for u in todos if u in explor], key=lambda u: -(explor[u].get("vistas") or 0))
        urls = orden[:a.top]
    elif a.modo == "links":
        f = BASE / "links.txt"
        urls = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if f.exists() else []
    else:
        urls = [e["url"] for e in buscar_youtube(a.consulta, a.n)]
    pend = [u for u in urls if u not in datos]
    if pend:
        import clipfinder
        model = clipfinder.load_model()
        for url in pend:
            print("→ edición:", url, flush=True)
            analizar(url, tmp, model, datos)
            datos_path.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    # resumen para Claude (lo único que lee)
    md = ["# Lo que funciona (Reels/Shorts analizados)", ""]
    if explor:
        md += ["## Temas y ganchos (sin bajar videos, por vistas)", "", "| Vistas | Dur | Cuenta | Título | Arranca con |", "|---|---|---|---|---|"]
        for d in sorted(explor.values(), key=lambda d: -(d.get("vistas") or 0)):
            md.append(f"| {d.get('vistas') or '-'} | {d.get('dur') or '-'}s | {d.get('cuenta')} | {d['titulo']} | "
                      f"{' '.join((d.get('texto') or '').split()[:14])} |")
    filas = sorted(datos.values(), key=lambda d: -(d.get("vistas") or 0))
    if filas:
        md += ["", "## Edición de los más vistos (bajados y borrados)", "",
               "| Vistas | Likes | Cuenta | Dur | s/plano | Formato | Arranca con |", "|---|---|---|---|---|---|---|"]
        for d in filas:
            md.append(f"| {d.get('vistas') or '-'} | {d.get('likes') or '-'} | {d.get('cuenta')} | {d['dur']}s | "
                      f"{d['seg_por_plano']} | {d['formato']} | {d['primeras_palabras']} |")
        md += ["", f"- Duración mediana: {np.median([d['dur'] for d in filas]):.0f} s · segundos por plano (mediana): "
                   f"{np.median([d['seg_por_plano'] for d in filas]):.1f} · formatos: {', '.join(sorted({d['formato'] for d in filas}))}",
               "- Hojas de cuadros: `referencias/aprender/<id>.jpg`"]
    (BASE / "resumen.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for v in tmp.glob("*"):
        v.unlink()
    print(f"\nListo → {BASE / 'resumen.md'}")


if __name__ == "__main__":
    main()
