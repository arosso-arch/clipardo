"""Clipardo de un clic: corre todo lo que se puede sin Claude (no gasta tokens).

Lo lanza clipardo.bat (raíz del proyecto). Para cada stream:
  1. inbox con links o videos nuevos  → prepara (descarga, transcribe, busca picos de chat/audio)
  2. preparado pero sin elegir clips  → avisa: elegir los clips es lo único que hace Claude
                                         ("elegí los clips de <job>": lee solo review.md, cuesta poco)
  3. clips elegidos pero sin cortar   → corta
  4. cortados pero sin editar         → edita (ig-editor) + efectos (Remotion) + hoja de revisión
Al final abre la carpeta con los Reels listos. Es reanudable: si se corta, volvé a darle doble clic.
"""
import json
import subprocess
import sys
from pathlib import Path

_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
PY = str(R.VENV_PY)
CF = str(R.SKILLS / "clip-finder" / "clipfinder.py")
IG = R.SKILLS / "ig-editor"
ROOT = R.HOME
FF = R.ffmpeg_bin() / "ffmpeg.exe"


def paso(t):
    print(f"\n=== {t} ===", flush=True)


def correr(args):
    r = subprocess.run([PY, "-I", *map(str, args)])
    if r.returncode != 0:
        sys.exit(f"\nSe cortó en: {' '.join(map(str, args[:3]))}. Volvé a darle doble clic para retomar.")


def inbox_pendiente():
    links = [l.strip() for l in (ROOT / "inbox" / "links.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")] if (ROOT / "inbox" / "links.txt").exists() else []
    videos = [p for p in (ROOT / "inbox").glob("*") if p.suffix.lower() in (".mp4", ".mkv", ".mov", ".ts")]
    return links or videos


def hoja(mp4, out):
    dur = float(subprocess.run([str(FF).replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout or 30)
    subprocess.run([str(FF), "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps=8/{dur:.2f},scale=270:480,tile=8x1",
                    "-frames:v", "1", str(out)])


def main():
    print("Clipardo: edición automática (no gasta tokens)")
    if inbox_pendiente():
        paso("1/4 Preparando streams nuevos del inbox (puede tardar bastante)")
        correr([CF, "prepare", "--inbox"])
    listos, a_elegir = [], []
    for job in sorted(p for p in (ROOT / "jobs").iterdir() if p.is_dir()):
        raw, final = ROOT / "clips" / "raw" / job.name, ROOT / "clips" / "final" / job.name
        if not (job / "selections.json").exists():
            if (job / "review.md").exists():
                a_elegir.append(job.name)
            continue
        if not json.loads((job / "selections.json").read_text(encoding="utf-8")).get("clips"):
            continue  # stream revisado sin clips buenos (ver "nota" en selections.json)
        if not (raw / "results.json").exists():
            paso(f"2/4 Cortando los clips elegidos de {job.name}")
            correr([CF, "cut", job.name])
        crudos = sorted(p.stem for p in raw.glob("*.mp4") if p.with_suffix(".json").exists())
        hechos = {p.stem for p in final.glob("*.mp4")} if final.exists() else set()
        faltan = [c for c in crudos if c not in hechos]
        if faltan:
            paso(f"3/4 Editando {len(faltan)} clip(s) de {job.name} (cámara, cortes, subtítulos)")
            for c in faltan:
                correr([IG / "igeditor.py", "render", job.name, "--estilo", "limpio", "--capcut", "--solo", c[:2]])
                paso(f"4/4 Efectos de Remotion: {c}")
                correr([IG / "remotion_final.py", job.name, "--solo", c[:2]])
            rev = final / "revision"
            rev.mkdir(exist_ok=True)
            for c in faltan:
                hoja(final / f"{c}.mp4", rev / f"{c}.jpg")
            listos.append(final)
    print("\n" + "=" * 60)
    for f in listos:
        print(f"Reels listos en: {f}  (hojas para revisar rápido en {f / 'revision'})")
    for j in a_elegir:
        print(f"Falta elegir los clips de {j}: abrí Claude (sesión nueva) y decile \"elegí los clips de {j}\".")
    if not listos and not a_elegir:
        print("No había nada nuevo. Pegá un link en inbox\\links.txt o tirá un video en la carpeta inbox.")
    for f in listos:
        subprocess.run(["explorer", str(f)])


if __name__ == "__main__":
    main()
