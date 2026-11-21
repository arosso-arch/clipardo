"""Revisor automático de Reels terminados (autocorrección, pedido del usuario 2026-11-19).

Uso:  python -I revisar.py <job> [--solo 03] [--arreglar]

Por cada Reel de clips\\final\\<job>\\ mide, sin gastar tokens:
  1. TÍTULO vs SUBTÍTULOS: si la caja del título se pisa con algún subtítulo (geometría de NN_capcut.json).
  2. CÁMARA (gaming): que en la franja de arriba haya una cara entera (no cortada) en la mayoría de los cuadros.
  3. CARA vs TEXTOS (resto): que el título no tape la cara.
Escribe clips\\final\\<job>\\revision\\revisar.json y una tabla. Sale con código 1 si algo falla.
--arreglar: corrige lo que se puede solo (título que choca → `titulo_y` en el .json del clip y vuelve a pasar
Remotion de ese clip; cámara de gaming sin cara → vuelve a renderizar ese clip con la webcam del stream).
Lo que no se puede arreglar solo queda en la tabla para que Claude mire la hoja de ese clip y decida.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
import igeditor as ig  # noqa: E402

PY = sys.executable
RAW, FINAL = ig.RAW, ig.FINAL


def caja_titulo(texto, y):
    largo = len(texto)
    tam = 62 if largo > 26 else 70 if largo > 18 else 78  # igual que Titulo.tsx (tamFinal)
    lineas = max(1, math.ceil(largo * tam * 0.62 / 728))  # maxWidth 780 en Titulo.tsx
    return y, y + lineas * tam * 1.1 + 28


def revisar_clip(cj, rm):
    c = json.loads(cj.read_text(encoding="utf-8"))
    tc = ig.CFG.get("titulo", {})
    tipo = c.get("tipo")
    split = c.get("split") or 760
    titulo = rm.get("titulo_pantalla") or (rm.get("hook_text") or "").upper()
    ty = rm.get("titulo_y") or ((split + 130) if tipo == "gaming" else tc.get("y", 200))
    t0, t1 = caja_titulo(titulo, ty) if titulo else (0, 0)
    tam = c.get("tam_sub", 72)
    problemas, arreglo = [], {}
    # 1) título vs subtítulos (el subtítulo rebota: ±0,75 del tamaño)
    choques = [s for s in c.get("subtitulos", []) if titulo and s["y"] + 0.75 * tam > t0 and s["y"] - 0.75 * tam < t1]
    if choques:
        problemas.append(f"título choca con {len(choques)} subtítulos (ej. '{choques[0]['text']}' en {choques[0]['start']:.1f}s)")
        maxy = max(s["y"] for s in choques)
        arreglo["titulo_y"] = int(maxy + 0.75 * tam + 24) if tipo == "gaming" else max(120, int(min(s["y"] for s in choques) - 0.75 * tam - (t1 - t0) - 24))
    # 2) / 3) caras en el Reel final
    mp4 = cj.parent.parent / (cj.stem.replace("_capcut", "") + ".mp4")
    caras = ig.caras_rapidas(mp4, ig.W, ig.H, n=10) if mp4.exists() else []
    if tipo == "gaming" and caras:
        ok = sum(1 for _, fs in caras if any(f[2] > 0.3 * split and f[1] + f[2] / 2 < split + 10 and f[1] - f[2] / 2 > -10 for f in fs))  # cara grande: los emojis del chat no cuentan
        abajo = sum(1 for _, fs in caras if any(f[1] > split and f[2] > 0.12 * ig.H for f in fs))
        if abajo / len(caras) >= 0.5:
            # el streamer a pantalla completa en la parte de "juego": no era gaming (ej. mirando un clip, emojis del
            # chat tomados como caras arriba) → va como cámara de una persona
            problemas.append(f"layout: el streamer aparece grande abajo en {abajo}/{len(caras)} cuadros (no es gaming)")
            arreglo.update(rerender=True, layout="cara")
        elif ok / len(caras) < 0.6:
            problemas.append(f"cámara: cara entera arriba solo en {ok}/{len(caras)} cuadros")
            arreglo["rerender"] = True
        else:
            # cámara centrada: la cara grande de arriba cerca del centro (corrección del usuario 2026-11-19: "se ve corrida")
            xs = sorted(max((f for f in fs if f[1] < split and f[2] > 0.3 * split), key=lambda f: f[2])[0]
                        for _, fs in caras if any(f[1] < split and f[2] > 0.3 * split for f in fs))
            if xs and abs(xs[len(xs) // 2] - ig.W / 2) > 0.13 * ig.W:
                problemas.append(f"cámara corrida: la cara está en x={xs[len(xs) // 2]:.0f} (centro {ig.W // 2})")
                arreglo["rerender"] = True
    elif caras and titulo:
        tapa = sum(1 for _, fs in caras if fs and any(t0 < max(fs, key=lambda f: f[2])[1] < t1 for _ in [0]))
        if tapa / len(caras) > 0.3:
            problemas.append(f"el título tapa la cara en {tapa}/{len(caras)} cuadros")
    # capa final de Remotion: si falló, el .mp4 es la versión FFmpeg sin título (pasó con la PC cargada)
    if titulo and mp4.exists() and cj.exists() and mp4.stat().st_mtime < cj.stat().st_mtime - 5:
        problemas.append("falta la capa final (sin título): Remotion no terminó")
        arreglo["remotion"] = True
    return {"clip": mp4.name, "tipo": tipo, "problemas": problemas, "arreglo": arreglo}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--solo")
    ap.add_argument("--arreglar", action="store_true")
    a = ap.parse_args()
    cdir = FINAL / a.job / "capcut"
    res = []
    for cj in sorted(cdir.glob("*_capcut.json")):
        if a.solo and not cj.name.startswith(a.solo):
            continue
        rawj = RAW / a.job / (cj.stem.replace("_capcut", "") + ".json")
        rm = json.loads(rawj.read_text(encoding="utf-8")) if rawj.exists() else {}
        r = revisar_clip(cj, rm)
        res.append(r)
        if a.arreglar and r["arreglo"]:
            pre = cj.name[:2]
            if "titulo_y" in r["arreglo"]:
                rm["titulo_y"] = r["arreglo"]["titulo_y"]
                rawj.write_text(json.dumps(rm, ensure_ascii=False), encoding="utf-8")
            if r["arreglo"].get("rerender"):
                subprocess.run([PY, "-I", str(AQUI / "igeditor.py"), "render", a.job, "--solo", pre, "--capcut"]
                               + (["--layout", r["arreglo"]["layout"]] if r["arreglo"].get("layout") else []), check=False)
            subprocess.run([PY, "-I", str(AQUI / "remotion_final.py"), a.job, "--solo", pre], check=False)
            r2 = revisar_clip(cj, json.loads(rawj.read_text(encoding="utf-8")))
            r["despues"] = r2["problemas"]
    (FINAL / a.job / "revision").mkdir(parents=True, exist_ok=True)
    (FINAL / a.job / "revision" / "revisar.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("| Clip | Tipo | Problemas | Después del arreglo |\n|---|---|---|---|")
    malos = 0
    for r in res:
        quedan = r.get("despues", r["problemas"])
        malos += bool(quedan)
        print(f"| {r['clip']} | {r['tipo']} | {'; '.join(r['problemas']) or 'ok'} | "
              f"{('; '.join(r['despues']) or 'ok') if 'despues' in r else '-'} |")
    sys.exit(1 if malos else 0)


if __name__ == "__main__":
    main()
