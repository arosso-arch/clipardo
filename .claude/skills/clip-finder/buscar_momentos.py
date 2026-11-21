"""Busca momentos clipeables en la transcripción COMPLETA de un stream (además de los 30 candidatos).

Uso:  python -I buscar_momentos.py <job> [--n 18]
Puntúa ventanas de 40 s por señales de lo que pega en TikTok/IG para streamers argentinos
(ver <CLIPARDO_HOME>\\referencias\\aprender\\lo-que-funciona.md) y muestra las mejores con un pedacito de texto.
Después leé en detalle solo las que valgan la pena.
"""
import argparse
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
PESOS = {
    r"coscu|chilena|davo|spreen|cobra|djmario|dj mario|momo|duki|bauleti|robleis|mazza|alonso|westcol|zeko|goncho|coker|joaco": 2,
    r"\bjuli\b|novia|mi vieja|mi mam|mi viejo|mi pap|mi hijo|mi perr|mi gat": 3,
    r"adivin|apuesta|apostamos|reto|desaf[ií]o|te juego|si gano|si perd[eé]s": 3,
    r"tiktok|reel|video de|mir[aá] (este|esto)|reaccion": 3,
    # 2026-11-20 (canales de referencia): reacciones a noticias/videos y la radio de GTA 6 son lo más visto
    r"noticia|telediario|telecinco|la sexta|antena 3|tn\b|cr[oó]nica|periodista|sal[ií] en la tele|me sacaron en": 3,
    r"\bradio\b|esta canci[oó]n|este tema|bad bunny|anuel|cocoteo": 2,
    r"\bnpc\b|me secuestr|me rob[oó]|peaje|cocodrilo|caim[aá]n|la vida real": 2,
    r"una vez|me pas[oó]|te cuento|les cuento|anécdota|historia|cuando era": 2,
    r"para m[ií]|opino|no estoy de acuerdo|es un robo|la verdad que": 1,
    r"ja ?ja|jaja|me muero|no puede ser|no lo puedo creer|qu[eé] hac[eé]s|est[aá]s loco|enfermo": 2,
    r"\bgta\b|gta 6|gta seis": 3,
}
MALO = r"c[oó]digo|apuesta en|casino|bono|ruleta|stake|slot"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--n", type=int, default=18)
    a = ap.parse_args()
    J = str(R.JOBS / a.job)
    d = json.load(open(J + r"\full_transcript.json", encoding="utf-8"))
    segs = [s for k in sorted(d, key=int) for s in d[k]]
    usados = []
    try:
        for f in ("selections.json", "selections_2.json", "selections_3.json", "selections_4.json"):
            for c in json.load(open(fr"{J}\{f}", encoding="utf-8")).get("clips", []):
                usados.append((c["start"], c["end"]))
    except FileNotFoundError:
        pass
    res, t, fin = [], 0.0, segs[-1]["end"]
    while t < fin:
        txt = " ".join(s["text"] for s in segs if t <= s["start"] < t + 40)
        if txt and not any(x - 30 < t < y for x, y in usados):
            low = txt.lower()
            sc = sum(w * len(re.findall(p, low)) for p, w in PESOS.items()) - (6 if re.search(MALO, low) else 0)
            res.append((sc, t, txt))
        t += 20.0
    res.sort(key=lambda x: -x[0])
    vistos = []
    for sc, t, txt in res:
        if any(abs(t - v) < 60 for v in vistos):
            continue
        vistos.append(t)
        print(f"[{sc}] {t:.0f}s ({int(t // 3600)}:{int(t % 3600 // 60):02d}) {txt[:200]}")
        if len(vistos) >= a.n:
            break


if __name__ == "__main__":
    main()
