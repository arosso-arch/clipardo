"""ig-editor: convierte los clips en bruto de clip-finder en Reels listos para publicar.

Uso:
  render <job | carpeta> [--estilo limpio|bubble|ab] [--layout auto|cara|hablante|mosaico|apilado|blur] [--solo NN]

Entrada: <CLIPARDO_HOME>\\clips\\raw\\<job>\\NN_titulo.mp4 + NN_titulo.json (palabras con tiempos, hook, caption).
Salida:  <CLIPARDO_HOME>\\clips\\final\\<job>\\NN_titulo.mp4 / .jpg (portada) / .txt (caption) / .json
         + clips\\final\\registro.csv (para la Fase 4) y el calendario pasa a "listo para subir".

Detección de caras: OpenCV YuNet (modelo MIT de opencv_zoo). Ideas de layout y recorte de silencios
inspiradas en Clip-Forge (lowdevco/Clip-Forge, licencia MIT); el código es propio.
Todo corre local: sin API keys ni conexiones de red.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

SKILL_DIR = Path(__file__).resolve().parent
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
ROOT = Path(os.environ.get("CLIPS_ROOT") or R.HOME).resolve()
CFG = json.loads((SKILL_DIR / "config.json").read_text(encoding="utf-8"))
TOOLS = ROOT / "tools"
FFMPEG = str(next(TOOLS.glob("ffmpeg/*/bin/ffmpeg.exe"), "ffmpeg"))
YUNET = TOOLS / "models" / "yunet" / "face_detection_yunet_2023mar.onnx"
RAW, FINAL, WORK = ROOT / "clips" / "raw", ROOT / "clips" / "final", ROOT / "work"
W, H, FPS = CFG["salida"]["ancho"], CFG["salida"]["alto"], CFG["salida"]["fps"]


def log(*a):
    print("[ig-editor]", *a, flush=True)


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, **kw)


def inside_root(p):
    p = Path(p).resolve()
    if ROOT not in p.parents:
        sys.exit(f"Ruta fuera de {ROOT}: {p}")
    return p


def probe(path):
    out = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return d["streams"][0]["width"], d["streams"][0]["height"], float(d["format"]["duration"])


# ------------------------------------------------------------- 1. silencios
def audio_db(path, hop=0.05):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le",
                          "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    n = int(16000 * hop)
    k = len(x) // n
    if k == 0:
        return np.zeros(1), hop
    blk = x[:k * n].reshape(k, n)
    return 10 * np.log10((blk ** 2).mean(1) + 1e-10), hop


def voice_speakers(path, words):
    """Quién habla según la voz (tono), para cuando alguien habla fuera de cámara (ej. la novia de Coker).
    Calcula el tono medio de cada palabra y separa en dos voces si están bien diferenciadas.
    Devuelve una etiqueta por palabra (0 = voz principal) o None si suena a una sola persona."""
    c = CFG["subtitulos"].get("voces", {})
    if not c.get("activar", True) or len(words) < 6:
        return None
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le",
                          "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    sr, win, hopn = 16000, 640, 160
    lo, hi = sr // 400, sr // 70  # 70-400 Hz
    f0 = []
    for s, e, _ in words:
        a, b = int(s * sr), int(e * sr)
        vals = []
        for i in range(a, max(a + 1, b - win), hopn):
            fr = x[i:i + win]
            if len(fr) < win or np.sqrt((fr ** 2).mean()) < 0.003:
                continue
            fr = fr - fr.mean()
            ac = np.correlate(fr, fr, "full")[win - 1:]
            if ac[0] <= 0:
                continue
            seg = ac[lo:hi] / ac[0]
            j = int(np.argmax(seg))
            if seg[j] > 0.45:  # tramo con voz clara
                vals.append(sr / (lo + j))
        f0.append(float(np.log2(np.median(vals))) if len(vals) >= 2 else None)
    v = np.array([q for q in f0 if q is not None])
    if len(v) < 6:
        return None
    ca, cb = np.percentile(v, 25), np.percentile(v, 75)
    for _ in range(20):  # 2-medias en escala de octavas
        m = np.abs(v - ca) <= np.abs(v - cb)
        if m.all() or (~m).all():
            return None
        ca, cb = v[m].mean(), v[~m].mean()
    lab_hi = cb > ca
    minor = min(m.sum(), (~m).sum())
    if abs(cb - ca) < c.get("separacion_octavas", 0.45) or minor < c.get("min_palabras", 3):
        return None
    lab = [None if q is None else int((abs(q - cb) < abs(q - ca)) == lab_hi) for q in f0]
    # palabras sin tono: toman la etiqueta vecina; una palabra suelta distinta entre dos iguales se corrige
    last = next((q for q in lab if q is not None), 0)
    lab = [last := (q if q is not None else last) for q in lab]
    for i in range(1, len(lab) - 1):
        if lab[i - 1] == lab[i + 1] != lab[i]:
            lab[i] = lab[i - 1]
    main = max(set(lab), key=lab.count)
    lab = [0 if q == main else 1 for q in lab]
    # control de timbre: un mismo streamer gritando o quejándose sube el tono pero el timbre no cambia.
    # Solo se acepta la segunda voz si el timbre (MFCC) de los dos grupos es claramente distinto
    # (novia de Coker: 1,56; Coker solo gritando: 0,59; Discord con varios hombres: 0,36)
    ratio = timbre_ratio(x, words, lab)
    if ratio is not None and ratio < c.get("timbre_min", 1.0):
        log(f"voces: el tono cambia pero el timbre no ({ratio:.2f}): es la misma persona")
        return None
    return lab


def _mfcc(x, sr=16000):
    win, hop, n_fft, n_mel = 400, 160, 512, 26
    n = 1 + max(0, (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    fr = x[idx]
    rms = np.sqrt((fr ** 2).mean(1))
    spec = np.abs(np.fft.rfft(fr * np.hamming(win), n_fft)) ** 2
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    pts = 700 * (10 ** (np.linspace(mel(80), mel(7600), n_mel + 2) / 2595) - 1)
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n_mel, n_fft // 2 + 1))
    for m in range(1, n_mel + 1):
        a, b, cc = bins[m - 1], bins[m], bins[m + 1]
        fb[m - 1, a:b] = (np.arange(a, b) - a) / max(1, b - a)
        fb[m - 1, b:cc] = (cc - np.arange(b, cc)) / max(1, cc - b)
    lm = np.log(spec @ fb.T + 1e-8)
    k = np.arange(n_mel)
    dct = np.cos(np.pi / n_mel * (k[None, :] + 0.5) * np.arange(n_mel)[:, None])
    return (lm @ dct.T)[:, 1:14], rms


def timbre_ratio(x, words, lab):
    """Distancia de timbre entre los dos grupos de voces / dispersión dentro del grupo principal."""
    M, rms = _mfcc(x)
    thr = np.percentile(rms, 40)
    F, L = [], []
    for (s, e, *_), l in zip(words, lab):
        sel = [j for j in range(int(s * 100), min(int(e * 100), len(M))) if rms[j] > thr]
        if len(sel) >= 8:
            F.append(M[sel].mean(0))
            L.append(l)
    F, L = np.array(F), np.array(L)
    if len(F) < 6 or (L == 1).sum() < 2 or (L == 0).sum() < 2:
        return None
    Z = (F - F.mean(0)) / (F.std(0) + 1e-6)
    a, b = Z[L == 0], Z[L == 1]
    within = float(np.mean([np.linalg.norm(z - a.mean(0)) for z in a]))
    return float(np.linalg.norm(a.mean(0) - b.mean(0)) / max(within, 1e-6))


def keep_segments(words, dur, db, hop):
    """Tramos a conservar: corta los huecos largos entre palabras SOLO si el audio ahí es bajo
    (así no se pierden risas o reacciones sin palabras)."""
    c = CFG["silencios"]
    if not c["recortar"] or not words:
        return [(0.0, dur)]
    thr = float(np.median(db)) - c["umbral_db_bajo_mediana"]
    cuts = []
    edges = [(0.0, words[0][0])] + [(words[i][1], words[i + 1][0]) for i in range(len(words) - 1)] + \
            [(words[-1][1], dur)]
    for a, b in edges:
        if b - a < c["hueco_min_s"]:
            continue
        seg = db[int(a / hop):max(int(a / hop) + 1, int(b / hop))]
        if len(seg) and np.percentile(seg, 90) < thr:
            lo = a + c["margen_s"] if a > 0 else 0.0
            hi = b - c["margen_s"] if b < dur else dur
            if hi - lo > 0.3:
                cuts.append((lo, hi))
    keep, t = [], 0.0
    for lo, hi in cuts:
        if lo > t:
            keep.append((t, lo))
        t = hi
    if t < dur:
        keep.append((t, dur))
    return [(round(a, 3), round(b, 3)) for a, b in keep if b - a > 0.05]


MULETILLAS = {"eh", "ehh", "eeh", "em", "emm", "mm", "mmm", "ehm"}


def _norm(w):
    return re.sub(r"[^\wáéíóúüñ]", "", w.lower())


def edit_cuts(words, dur, db, hop, meta):
    """Recortes de editor (además de los silencios), en tiempo del clip en bruto:
    1. Arranca en una frase completa (no a mitad de oración).
    2. Termina en la última frase completa + la reacción que sigue (risa), nunca a mitad de palabra.
    3. Saca repeticiones seguidas ("habíamos dicho habíamos dicho") y muletillas (eh, em, mmm).
    4. Recortes a mano del .json del clip: "recortes": [[ini, fin], ...] (los marca Claude leyendo la transcripción).
    Devuelve [(ini, fin)] a quitar."""
    c = CFG.get("recortes", {})
    cuts = []
    if not words or not c.get("activar", True):
        return cuts
    fin_frase = lambda w: w.rstrip().endswith((".", "?", "!", "…"))
    # Whisper pone mayúscula (o ¿ ¡) al empezar cada frase: alcanza como señal dentro de los primeros segundos
    ini_frase = lambda i: words[i][2].strip()[:1] in "¿¡" or words[i][2].strip()[:1].isupper()
    # 1. inicio
    if c.get("inicio_en_frase", True) and not ini_frase(0):
        i0 = next((i for i in range(1, len(words)) if ini_frase(i) and words[i][0] <= c.get("max_inicio_s", 3.5)), None)
        if i0:
            cuts.append((0.0, max(0.0, words[i0][0] - 0.08)))
            log(f"recorte: arranca en '{words[i0][2]}' (sacado: {' '.join(w[2] for w in words[:i0])})")
    # 2. final
    # la última frase está cortada si no tiene puntuación Y el clip termina pegado a la última palabra
    # y además termina en una palabra que deja la frase colgada ("desde el", "que saque un")
    colgada = _norm(words[-1][2]) in {"el", "la", "los", "las", "un", "una", "unos", "de", "del", "al", "a", "en", "con",
                                       "por", "para", "que", "y", "o", "pero", "mi", "tu", "su", "se", "me", "te", "lo",
                                       "le", "les", "nos", "como", "si", "porque", "cuando", "muy", "desde", "hasta"}
    cortada = not fin_frase(words[-1][2]) and dur - words[-1][1] < c.get("cola_min_s", 0.35) and colgada
    if c.get("fin_en_frase", True) and cortada:
        j = next((k for k in range(len(words) - 2, -1, -1)
                  if fin_frase(words[k][2]) or words[k + 1][0] - words[k][1] >= 0.6), None)
        if j is not None and words[-1][1] - words[j][1] <= c.get("max_final_s", 6.0):
            end = words[j][1] + 0.15
            lim = words[j + 1][0] - 0.05
            thr = float(np.median(db))
            t = end  # la reacción (risa) que sigue a la frase: se deja mientras el audio esté alto, hasta 1,5 s
            while t + hop < min(lim, words[j][1] + c.get("reaccion_max_s", 1.5)) and db[min(len(db) - 1, int(t / hop))] >= thr:
                t += hop
            end = max(end, t)
            cuts.append((end, dur))
            log(f"recorte: termina en '{words[j][2]}' (sacado: {' '.join(w[2] for w in words[j + 1:])})")
    # 3. repeticiones seguidas y muletillas
    if c.get("repeticiones", True):
        n_ = [_norm(w[2]) for w in words]
        i = 0
        while i < len(words):
            hecho = False
            for n in (4, 3, 2, 1):
                if i + 2 * n <= len(words) and n_[i:i + n] == n_[i + n:i + 2 * n] and all(n_[i:i + n]) \
                        and words[i + n][0] - words[i + n - 1][1] < 1.0:
                    cuts.append((words[i][0] - 0.03, words[i + n][0] - 0.03))
                    log(f"recorte: repetición '{' '.join(w[2] for w in words[i:i + n])}'")
                    i += n
                    hecho = True
                    break
            if not hecho:
                if n_[i] in MULETILLAS and 0 < i < len(words) - 1:
                    cuts.append((words[i][0] - 0.02, words[i + 1][0] - 0.02))
                i += 1
    # 3b. reacciones larguísimas sin palabras (risa de 20 s): queda el comienzo de la risa y la entrada a lo que sigue
    rmax = c.get("reaccion_larga_max_s", 4.0)
    for k in range(len(words) - 1):
        a, b = words[k][1], words[k + 1][0]
        if b - a > rmax:
            cuts.append((a + c.get("reaccion_deja_s", 2.8), b - 0.8))
            log(f"recorte: reacción de {b - a:.0f}s sin palabras → queda ~{c.get('reaccion_deja_s', 2.8) + 0.8:.0f}s")
    # 4. a mano
    for a, b in meta.get("recortes", []) or []:
        cuts.append((float(a), float(b)))
    return cuts


def subtract(keep, cuts):
    out = list(keep)
    for a, b in sorted(cuts):
        nxt = []
        for x, y in out:
            if b <= x or a >= y:
                nxt.append((x, y))
                continue
            if a > x:
                nxt.append((x, a))
            if b < y:
                nxt.append((b, y))
        out = nxt
    return [(round(x, 3), round(y, 3)) for x, y in out if y - x > 0.05]


def mapper(keep):
    def f(t):
        acc = 0.0
        for a, b in keep:
            if t < a:
                return acc
            if t <= b:
                return acc + (t - a)
            acc += b - a
        return acc
    return f


def between_expr(keep):
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)


# ------------------------------------------------------------- 2. caras y layout
def _region_diff(a, b, x0, y0, x1, y1):
    h, w = a.shape
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return 0.0
    return float(np.abs(a[y0:y1, x0:x1].astype(np.int16) - b[y0:y1, x0:x1].astype(np.int16)).mean())


def detect_faces(path, vw, vh, dur, probe=None):
    """Lee el video de corrido y cada 1/muestras_por_s s detecta caras (YuNet).
    Devuelve ([(t, [(cx, cy, alto, boca), ...])], extras) con hasta 8 caras por muestra (extras: lo que mida `probe`). `boca` mide cuánto se mueve
    la boca respecto de la muestra anterior, descontando el movimiento de la cabeza (sirve para saber quién habla)."""
    import cv2
    c = CFG["layout"]
    det_w = 640
    det_h = int(round(vh * det_w / vw))
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (det_w, det_h), c["score_min_cara"], 0.3, 50)
    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = 1.0 / c["muestras_por_s"]
    sc = vw / det_w
    samples, extras, prev, t_next, i = [], [], None, 0.0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / src_fps
        i += 1
        if t + 1e-6 < t_next:
            continue
        t_next += step
        small = cv2.resize(frame, (det_w, det_h))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        _, faces = det.detect(small)
        fl = []
        for f in ([] if faces is None else faces):
            if f[14] < c["score_min_cara"]:
                continue
            x, y, w, h = f[:4]
            boca = 0.0
            if prev is not None:
                mx0, mx1 = min(f[10], f[12]) - 0.1 * w, max(f[10], f[12]) + 0.1 * w
                my = (f[11] + f[13]) / 2
                d_boca = _region_diff(gray, prev, mx0, my - 0.12 * h, mx1, my + 0.22 * h)
                ey = (f[5] + f[7]) / 2
                d_cabeza = _region_diff(gray, prev, x, ey - 0.2 * h, x + w, ey + 0.05 * h)
                boca = max(0.0, d_boca - 0.8 * d_cabeza)
            fl.append((float((x + w / 2) * sc), float((y + h / 2) * sc), float(h * sc), boca))
        samples.append((t, sorted(fl, key=lambda z: -z[2])[:8]))
        ex = probe(frame) if probe else {}
        if not fl and prev is not None:
            # sin cara (se paró, se dio vuelta): dónde está el cuerpo según el movimiento en la imagen
            mov = cv2.absdiff(gray, prev) > 25
            cols = mov.sum(axis=0).astype(np.float32)
            if cols.sum() > 0.004 * mov.size:
                cum = np.cumsum(cols) / cols.sum()
                ex = dict(ex, cuerpo_x=float(np.searchsorted(cum, 0.5)) * sc)
        extras.append(ex)
        prev = gray
    cap.release()
    return samples, extras


def assign_faces(samples, centers):
    """Para cada muestra, a qué persona (índice de `centers`) corresponde cada cara detectada."""
    out = []
    for t, fs in samples:
        d = {}
        for f in fs:
            k = min(range(len(centers)), key=lambda j: (f[0] - centers[j][0]) ** 2 + (f[1] - centers[j][1]) ** 2)
            dist = ((f[0] - centers[k][0]) ** 2 + (f[1] - centers[k][1]) ** 2) ** 0.5
            if dist < 1.5 * centers[k][2] and (k not in d or f[2] > d[k][2]):
                d[k] = f
        out.append((t, d))
    return out


def speaker_turns(activity, words, n):
    """Quién habla en cada momento. `activity` = [(t, {persona: señal})] (movimiento de boca o anillo verde de
    Discord). Asigna cada palabra a la persona con más señal mientras se dice y arma turnos: solo se cambia de
    persona cuando la otra habla un tramo propio (no por una palabra suelta)."""
    c = CFG["layout"]["hablante"]
    who = []
    for s, e, _ in words:
        sc = [0.0] * n
        for t, d in activity:
            if s - 0.15 <= t <= e + 0.15:
                for k, v in d.items():
                    sc[k] += v
        best = max(range(n), key=lambda k: sc[k])
        who.append(best if sc[best] > 0 else None)
    # rellenar palabras sin dato con la anterior
    last = next((w for w in who if w is not None), 0)
    who = [last := (w if w is not None else last) for w in who]
    # tramos consecutivos del mismo hablante
    runs = []
    for (s, e, _), k in zip(words, who):
        if runs and runs[-1][0] == k:
            runs[-1][2] = e
            runs[-1][3] += 1
        else:
            runs.append([k, s, e, 1])
    turns = []  # (inicio_s, persona)
    cur = None
    for k, s, e, nw in runs:
        largo = nw >= c["min_palabras"] or e - s >= c["min_s"]
        if cur is None:
            cur = k
            turns.append((0.0, k))
        elif k != cur and largo:
            cur = k
            turns.append((max(0.0, s - c["anticipo_s"]), k))
    if len(turns) > 1 and turns[1][0] < c["min_s"]:  # no arrancar con un plano de menos de un segundo
        turns = [(0.0, turns[1][1])] + turns[2:]
    return turns or [(0.0, 0)]


def cover_time(samples, keep, default):
    """Fotograma de portada: donde la cara se ve más grande (primer plano = más expresivo), dentro de lo que queda."""
    cands = [(fs[0][2], t) for t, fs in samples if fs and any(a <= t <= b for a, b in keep)]
    return max(cands)[1] if cands else default


TIPOS = {"gaming": "gaming", "mosaico": "discord", "hablante": "dos-en-una-camara", "cara": "streamer-solo", "apilado": "dos-en-una-camara",
         "blur": "desconocido"}  # receta de cada tipo en tipos-de-clip.md


def choose_layout(samples, forced, tiles=None, vw=1920, vh=1080):
    c = CFG["layout"]
    if tiles and forced in ("auto", "mosaico"):
        return {"modo": "mosaico", "recuadros": tiles}
    samples = [fs for _, fs in samples]
    n = max(1, len(samples))
    one = [s[0] for s in samples if len(s) >= 1]
    two = [sorted(s, key=lambda z: z[0]) for s in samples if len(s) >= 2 and abs(s[0][0] - s[1][0]) > 250]
    info = {"frac_cara": round(len(one) / n, 2), "frac_dos": round(len(two) / n, 2)}
    mode = forced
    cg = c.get("gaming", {})
    # webcam del streamer en un rincón: una cara CHICA que está casi siempre en el MISMO lugar. Gana aunque el video
    # que mira tenga caras más grandes (reacciones a YouTube/TikTok, partidos): si no, se enfocaban esas caras
    es_gaming, celdas = False, {}
    for s_ in samples:
        for f in s_:
            if f[2] < cg.get("cara_max_frac", 0.15) * vh and (f[0] > 0.6 * vw or f[0] < 0.4 * vw):
                celdas.setdefault((int(f[0] / (0.06 * vw)), int(f[1] / (0.08 * vh))), []).append(f)
    if celdas:
        k_, fs_ = max(celdas.items(), key=lambda kv: len(kv[1]))
        if len(fs_) / n >= cg.get("min_frac_webcam", 0.5):
            fx, fy, fhm = (float(np.median([f[i] for f in fs_])) for i in range(3))
            es_gaming = True
    if mode == "gaming" or (mode == "auto" and es_gaming):
        # webcam chica sobre el juego (Kick/Twitch jugando): cámara arriba + juego abajo
        info.update(modo="gaming", cx=fx, cy=fy, fh=fhm)
        return info
    if mode == "auto":
        if len(two) / n >= c["min_frac_dos_caras"]:
            mode = "hablante"
        elif len(one) / n >= c["min_frac_cara"]:
            mode = "cara"
        else:
            mode = "blur"
    if mode == "cara" and one:
        info.update(cx=float(np.median([f[0] for f in one])), cy=float(np.median([f[1] for f in one])),
                    fh=float(np.median([f[2] for f in one])))
    if mode in ("apilado", "hablante"):
        if not two:
            mode = "cara" if one else "blur"
            if one:
                info.update(cx=float(np.median([f[0] for f in one])), cy=float(np.median([f[1] for f in one])),
                            fh=float(np.median([f[2] for f in one])))
        else:
            info["caras"] = [(float(np.median([p[i][0] for p in two])), float(np.median([p[i][1] for p in two])),
                              float(np.median([p[i][2] for p in two]))) for i in (0, 1)]
    info["modo"] = mode
    return info


def detect_mosaic(path, vw, vh):
    """Llamadas tipo Discord: varias cámaras en recuadros sobre fondo negro. Devuelve los recuadros (x, y, w, h)
    detectados en el fotograma mediano, o [] si no es un mosaico."""
    import cv2
    m = CFG["layout"]["mosaico"]
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for i in np.linspace(0, max(0, n - 1), 9).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, fr = cap.read()
        if ok:
            frames.append(fr)
    cap.release()
    if not frames:
        return []
    gray = cv2.cvtColor(np.median(np.stack(frames), axis=0).astype(np.uint8), cv2.COLOR_BGR2GRAY)
    mask = cv2.morphologyEx(((gray > 14) * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tiles = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 0.015 < w * h / (vw * vh) < 0.5 and 1.1 < w / h < 2.4:
            tiles.append((x, y, w, h))
    tiles.sort(key=lambda r: (r[1] // 50, r[0]))
    return tiles if len(tiles) >= m["min_recuadros"] else []


class MosaicProbe:
    """Por fotograma: si el mosaico está a la vista (los huecos entre recuadros son negros) y cuánto verde
    tiene el borde de cada recuadro (Discord marca así a quien está hablando)."""

    def __init__(self, tiles, vw, vh):
        import cv2
        self.cv2 = cv2
        self.rings = []
        for x, y, w, h in tiles:
            m = np.zeros((vh, vw), np.uint8)
            cv2.rectangle(m, (x - 2, y - 2), (x + w + 2, y + h + 2), 255, 6)
            self.rings.append(np.nonzero(m))
        inside = np.zeros((vh, vw), np.uint8)
        for x, y, w, h in tiles:
            cv2.rectangle(inside, (x - 4, y - 4), (x + w + 4, y + h + 4), 255, -1)
        xs, ys = [t[0] for t in tiles], [t[1] for t in tiles]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(t[0] + t[2] for t in tiles), max(t[1] + t[3] for t in tiles)
        gap = np.zeros((vh, vw), np.uint8)
        gap[y0:y1, x0:x1] = 255
        gap[inside > 0] = 0
        self.gap = np.nonzero(gap)

    def __call__(self, frame):
        cv2 = self.cv2
        g = frame[self.gap]
        visible = bool(len(g) == 0 or g.mean() < CFG["layout"]["mosaico"]["huecos_max_brillo"])
        ring = []
        for idx in self.rings:
            px = cv2.cvtColor(frame[idx].reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
            green = (px[:, 0] > 45) & (px[:, 0] < 85) & (px[:, 1] > 90) & (px[:, 2] > 90)
            ring.append(float(green.mean()) if len(green) else 0.0)
        return {"mosaico": visible, "ring": ring}


def _fit_rect(rect, aspect, cx=None):
    """Recorta un recuadro (x, y, w, h) a la proporción `aspect` (ancho/alto) centrado en cx."""
    x, y, w, h = rect
    nw = min(w, int(h * aspect))
    cx = x + w / 2 if cx is None else cx
    nx = int(min(max(x, cx - nw / 2), x + w - nw))
    return (nx, y, nw // 2 * 2, h // 2 * 2)


def reaction_runs(act, extras):
    """Momentos de reacción en un mosaico: dos o más recuadros con el anillo verde a la vez (se ríen o hablan
    encima). Devuelve {índice_de_muestra: [personas]} para mostrarlos en pantalla dividida."""
    c = CFG["layout"].get("reaccion", {})
    if not c.get("activar", True) or not act:
        return {}
    sps = CFG["layout"]["muestras_por_s"]
    thr = c.get("umbral", 0.08)
    multi = [len([k for k, v in d.items() if v > thr]) >= 2 and e["mosaico"] for (_, d), e in zip(act, extras)]
    # cerrar huecos cortos y descartar destellos
    gap = int(c.get("hueco_max_s", 0.3) * sps)
    idx = [i for i, m in enumerate(multi) if m]
    runs = []
    for i in idx:
        if runs and i - runs[-1][1] <= gap + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    out = {}
    for a, b in runs:
        if (b - a + 1) / sps < c.get("min_s", 0.6):
            continue
        b = max(b, a + int(c.get("dur_min_s", 1.5) * sps))  # que se llegue a ver
        b = min(b, len(act) - 1)
        tot = {}
        for i in range(a, b + 1):
            for k, v in act[i][1].items():
                tot[k] = tot.get(k, 0.0) + max(0.0, v - thr)
        people = sorted([k for k, v in sorted(tot.items(), key=lambda kv: -kv[1])[:c.get("max_paneles", 3)] if v > 0])
        if len(people) < 2:
            continue
        for i in range(a, b + 1):
            out[i] = people
    return out


def plan_mosaic(lay, samples, extras, words, vw, vh):
    """Discord, como las referencias: planos ESTABLES (no se mueve cada segundo).
    - Protagonistas = los 2 que más hablan. Si charlan entre ellos → pantalla dividida con los dos.
    - Si uno habla un tramo largo → su recuadro solo, agrandado. Alguien que no es protagonista solo
      aparece si habla un tramo largo.
    - Cada plano dura al menos `min_plano_s` y el recorte queda quieto durante todo el plano.
    - Pantalla compartida → completa."""
    c = CFG["layout"]["mosaico"]
    ct = CFG["layout"]["camara"]
    tiles = lay["recuadros"]
    dur = samples[-1][0] + 1.0 / CFG["layout"]["muestras_por_s"] if samples else 0.0
    rings = np.array([e["ring"] for e in extras])
    base = np.percentile(rings, 10, axis=0)
    act = [(t, {k: max(0.0, v - base[k] - 0.02) for k, v in enumerate(e["ring"])})
           for (t, _), e in zip(samples, extras)]
    turns = speaker_turns(act, words, len(tiles))
    # protagonistas por tiempo de habla
    def who_at(t):
        k = turns[0][1]
        for a, p in turns:
            if a <= t:
                k = p
        return k
    talk = {}
    for s, e, *_ in words:
        talk[who_at(s)] = talk.get(who_at(s), 0.0) + (e - s)
    ranked = sorted(talk, key=lambda k: -talk[k])
    tot = sum(talk.values()) or 1.0
    prot = ranked[:2] if len(ranked) > 1 and talk[ranked[1]] / tot >= c.get("min_frac_protagonista", 0.18) else ranked[:1]
    if not prot:  # sin palabras asignadas (clip casi sin habla): protagonista = el del primer turno
        prot = [turns[0][1] if turns else 0]
    solo_min = c.get("solo_min_s", 3.0)
    otro_min = c.get("otro_min_s", 2.5)
    # vistas por turno
    segs = []
    bounds = [a for a, _ in turns] + [dur]
    v_prot = ("split", tuple(sorted(prot))) if len(prot) == 2 else ("solo", prot[0])
    for (a, k), b in zip(turns, bounds[1:]):
        if b - a <= 0:
            continue
        # lo que esa persona HABLÓ de verdad en su turno (no el tiempo del turno, que incluye silencios)
        hablado = sum(e - s for s, e, *_ in words if a <= s < b)
        n_pal = sum(1 for s, *_ in words if a <= s < b)
        if k in prot:
            v = ("solo", k) if len(prot) == 1 or b - a >= solo_min else ("split", tuple(sorted(prot)))
        elif hablado >= otro_min * 0.6 and n_pal >= c.get("otro_min_palabras", 5):
            v = ("solo", k)
        else:
            v = v_prot  # alguien dijo dos palabras: no se lo muestra, sigue el protagonista
        if segs and segs[-1][2] == v:
            segs[-1][1] = b
        else:
            segs.append([a, b, v])
    # planos cortos: se pegan al anterior (o al siguiente si es el primero)
    mp = c.get("min_plano_s", 2.0)
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, (a, b, v) in enumerate(segs):
            if b - a < mp:
                j = i - 1 if i > 0 else i + 1
                es_prot = lambda vv: vv == v_prot or (vv[0] == "solo" and vv[1] in prot)
                if es_prot(v) and not es_prot(segs[j][2]):
                    # el plano corto es del protagonista: gana él (si no, Coker habla y se ve a otro)
                    segs[j][2] = v
                lo, hi = min(segs[i][0], segs[j][0]), max(segs[i][1], segs[j][1])
                segs[j][0], segs[j][1] = lo, hi
                del segs[i]
                changed = True
                break
        merged = []
        for sgm in segs:
            if merged and merged[-1][2] == sgm[2]:
                merged[-1][1] = sgm[1]
            else:
                merged.append(sgm)
        segs = merged
    # mosaico visible (si no, pantalla compartida), suavizado para que no parpadee
    vis = [e["mosaico"] for e in extras]
    k_ = int(CFG["layout"]["muestras_por_s"])
    vis = [sum(vis[max(0, i - k_):i + k_ + 1]) * 2 > len(vis[max(0, i - k_):i + k_ + 1]) for i in range(len(vis))]

    # caras "quietas" (pósters, dibujos, fotos de fondo): nunca mueven la boca → no son la persona
    def _static_bins(tile):
        tx, ty, tw, th = tile
        bins = {}
        for t, fs in samples:
            for f in fs:
                if tx <= f[0] <= tx + tw and ty <= f[1] <= ty + th:
                    bins.setdefault(int((f[0] - tx) // 40), []).append(f[3])
        return {k for k, v in bins.items() if np.mean(v) < c.get("boca_min_persona", 1.0)}
    static = {i: _static_bins(tl) for i, tl in enumerate(tiles)}

    def _persona(f, tile, ti):
        tx, ty, tw, th = tile
        return tx <= f[0] <= tx + tw and ty <= f[1] <= ty + th and int((f[0] - tx) // 40) not in static[ti]

    def face_in(tile, a, b):
        """Cara mediana (x, y, alto) de la persona dentro del recuadro durante el plano, o None."""
        ti = tiles.index(tile)
        fs_ = [f[:3] for t, fs in samples if a <= t < b for f in fs if _persona(f, tile, ti)]
        if len(fs_) < 3:  # en ese plano casi no se vio la cara: se usa dónde está en todo el clip
            fs_ = [f[:3] for t, fs in samples for f in fs if _persona(f, tile, ti)]
        return tuple(float(v_) for v_ in np.median(np.array(fs_), axis=0)) if fs_ else None

    def centered(tile, aspect, face):
        """Recorte dentro del recuadro de Discord con la persona CENTRADA (como las referencias): la cara queda
        al medio a lo ancho y un poco arriba del centro a lo alto (cabeza y hombros)."""
        m_ = 5  # sin el borde del recuadro (el anillo verde de Discord se veía como una línea arriba)
        tile = (tile[0] + m_, tile[1] + m_, tile[2] - 2 * m_, tile[3] - 2 * m_)
        tx, ty, tw, th = tile
        if face is None:
            return _fit_rect(tile, aspect)
        fx, fy, fh = face
        ch_ = min(th, max(0.6 * th, c.get("alto_en_caras", 3.6) * fh))
        cw_ = ch_ * aspect
        if cw_ > tw:
            cw_, ch_ = tw, tw / aspect
        x0 = min(max(tx, fx - cw_ / 2), tx + tw - cw_)
        y0 = min(max(ty, fy - 0.42 * ch_), ty + th - ch_)
        return (int(x0), int(y0), int(cw_) // 2 * 2, int(ch_) // 2 * 2)

    views = []
    for a, b, v in segs:
        if v[0] == "solo":
            # una persona: pantalla completa 9:16 con su cámara (como "Perdón que te pregunte")
            fc = face_in(tiles[v[1]], a, b)
            rect = centered(tiles[v[1]], W / H, fc)
            s_ = H / rect[3]
            band = ((fc[1] - rect[1]) * s_, fc[2] * s_, (fc[0] - rect[0]) * s_) if fc else None
            views.append((a, b, ("fill",) + rect, band))
        else:
            ph = H // len(v[1])
            rects = tuple(centered(tiles[p], W / ph, face_in(tiles[p], a, b)) for p in v[1])
            views.append((a, b, ("stack", rects), None))
    full = ("fit", 0, 0, vw // 2 * 2, vh // 2 * 2)
    keys, prev, j = [], None, 0
    for i, (t, _) in enumerate(samples):
        while j + 1 < len(views) and views[j + 1][0] <= t:
            j += 1
        view, band = (views[j][2], views[j][3]) if vis[i] else (full, None)
        if band:
            band = (band[0] - band[1] / 2 - 0.35 * band[1], band[0] + band[1] / 2 + 0.25 * band[1],
                    band[2] if len(band) > 2 else W / 2)  # (arriba, abajo, x de la cara)
        keys.append((t, view, prev is not None and view != prev, band))
        prev = view
    log(f"Discord: protagonistas {prot}, {len(segs)} planos: " +
        ", ".join(f"{a:.1f}-{b:.1f} {v[0]}{list(v[1]) if v[0] == 'split' else v[1]}" for a, b, v in segs))
    return keys, [(round(a, 2), int(b)) for a, b in turns]


def second_person(samples, assigned, words, vlab):
    """Streamer solo + otra persona que entra a cámara y habla (ej. la novia de Coker en el 04).
    Devuelve, por muestra, la x de su cara mientras haya que enfocarla (desde que habla hasta que se va
    de cuadro) o None. Necesita las etiquetas de voz (vlab): sin segunda voz no hace nada."""
    if not vlab or 1 not in vlab:
        return None
    c = CFG["layout"].get("segunda_persona", {})
    if not c.get("activar", True):
        return None
    habla = [(s, e) for (s, e, *_), l in zip(words, vlab) if l == 1]
    sps = CFG["layout"]["muestras_por_s"]
    otra = []
    for (t, fs), (_, d) in zip(samples, assigned):
        main = d.get(0)
        cands = [f for f in fs if main is None or (abs(f[0] - main[0]) > 0.6 * main[2] and f[2] >= 0.45 * main[2])]
        otra.append(max(cands, key=lambda f: f[2])[0] if cands and main is not None else None)
    out, activo, falta, lastx = [None] * len(samples), False, 0, None
    for i, (t, _) in enumerate(samples):
        if not activo and otra[i] is not None and any(s - 0.3 <= t <= e + 0.3 for s, e in habla):
            activo = True
        if activo:
            if otra[i] is not None:
                lastx, falta = otra[i], 0
            else:
                falta += 1
                if falta > c.get("se_fue_s", 1.0) * sps:  # se fue de cuadro
                    activo, lastx = False, None
            out[i] = lastx if activo else None
    n = sum(1 for v in out if v is not None)
    if n:
        log(f"segunda persona en cámara: enfocada {n / sps:.1f}s")
    return out if n else None


def plan_gaming(lay, samples, vw, vh):
    """Gaming (receta A, la más viral para streamers): arriba la webcam con la cara grande y centrada, abajo el
    juego recortado al centro (sin pisar la webcam), línea divisoria; los subtítulos van sobre la línea."""
    cg = CFG["layout"].get("gaming", {})
    split = int(lay.get("alto_camara") or cg.get("alto_camara", 760)) // 2 * 2
    cx, cy, fh = lay["cx"], lay["cy"], lay["fh"]
    tj = lay.get("tarjeta")  # 2026-11-20 (estilo @elcokismo): webcam como tarjeta redondeada sobre el juego
    cw = min(vw, (tj or cg).get("ancho_en_caras", cg.get("ancho_en_caras", 3.4)) * fh)
    ch = cw / (tj["aspecto"] if tj else W / split)
    x0 = min(max(0, cx - cw / 2), vw - cw)
    y0 = min(max(0, cy - 0.42 * ch), vh - ch)
    cam = (int(x0), int(y0), int(cw) // 2 * 2, int(ch) // 2 * 2)
    gw = min(vw, vh * W / (H - split))
    borde = cg.get("margen_webcam_en_caras", 2.4) * fh
    if cx > vw / 2:  # webcam a la derecha: el juego termina antes de la webcam
        gx = max(0.0, min((vw - gw) / 2, cx - borde - gw))
    else:
        gx = min(vw - gw, max((vw - gw) / 2, cx + borde))
    game = (int(gx), 0, int(gw) // 2 * 2, vh // 2 * 2)
    if tj:
        tw = int(W * tj["ancho_frac"]) // 2 * 2
        th = int(tw / tj["aspecto"]) // 2 * 2
        ty = split + int(th * tj.get("solape_frac", 0.22)) - th  # la tarjeta pisa un poco el borde del juego
        tj = dict(tj, rect=((W - tw) // 2, max(16, ty), tw, th))
        abajo = max(16, ty) + th
    else:
        abajo = split
    lay["bandas"] = [(0, abajo)]  # la mitad de arriba es la cara: la marca y los textos la esquivan
    lay["split"] = abajo
    lay["y_sub"] = abajo  # subtítulos sobre la línea que separa cámara y juego (o debajo de la tarjeta)
    view = ("gaming", cam, game, split, tj)
    return [(t, view, i == 0, None) for i, (t, _) in enumerate(samples)], [(0.0, 0)]


def plan_camera(lay, samples, extras, words, vw, vh, vlab=None):
    if lay["modo"] == "gaming":
        return plan_gaming(lay, samples, vw, vh)
    if lay["modo"] == "mosaico":
        return plan_mosaic(lay, samples, extras, words, vw, vh)
    """Plan de la cámara virtual, una entrada por muestra: (t, vista, corte, banda_cara).
    vista = ('fill', x, y, w, h): recorte 9:16 a pantalla completa (sigue a la persona).
    vista = ('fit', x, y, w, h): recuadro agrandado arriba, sobre fondo desenfocado (mosaico / pantalla compartida).
    banda_cara = (y0, y1) donde queda la cara en el lienzo final (para no taparla con texto), o None."""
    ct = CFG["layout"]["camara"]
    mode = lay["modo"]
    top = ct["fit_top_frac"] * H
    keys, prev_rect, turns, stack = [], None, [(0.0, 0)], {}
    if mode == "mosaico":
        tiles = lay["recuadros"]
        rings = np.array([e["ring"] for e in extras])
        base = np.percentile(rings, 10, axis=0)
        act = [(t, {k: max(0.0, v - base[k] - 0.02) for k, v in enumerate(e["ring"])})
               for (t, _), e in zip(samples, extras)]
        turns = speaker_turns(act, words, len(tiles))
        # en Discord la cámara queda fija con la llamada entera (corrección del usuario); el seguimiento es solo
        # para cámaras propias. Los turnos se siguen usando para el color de subtítulo de cada persona.
        seguir = CFG["layout"]["mosaico"].get("seguir_hablante", False)
        stack = reaction_runs(act, extras) if seguir else {}
    elif mode == "hablante":
        centers = lay["caras"]
        assigned = assign_faces(samples, centers)
        turns = speaker_turns([(t, {k: f[3] for k, f in d.items()}) for t, d in assigned], words, len(centers))
    else:
        centers = [(lay["cx"], lay["cy"], lay["fh"])]
        assigned = assign_faces(samples, centers)
        visita = second_person(samples, assigned, words, vlab)
    if mode in ("cara", "hablante"):
        ch = vh // 2 * 2
        cw = min(vw, int(ch * W / H)) // 2 * 2
        dz, al = ct["zona_muerta"] * cw, ct["suavizado"]
        last = {k: (c[0], c[1], c[2]) for k, c in enumerate(centers)}
    if mode != "cara":
        visita = None
    sin_cara = 0
    siguiendo_cuerpo = False
    abierto_x, abierto_prev = None, False
    # posición del cuerpo suavizada (mediana de ~1 s): el movimiento cuadro a cuadro es ruidoso y hacía vibrar la cámara
    cuerpo = None
    if mode == "cara" and extras:
        raw_c = [e.get("cuerpo_x") for e in extras]
        cuerpo = []
        for i_ in range(len(raw_c)):
            ven = [v for v in raw_c[max(0, i_ - 4):i_ + 5] if v is not None]
            cuerpo.append(float(np.median(ven)) if len(ven) >= 3 and raw_c[i_] is not None else None)
    ti, cur, posx = 0, None, None
    for i, (t, fs) in enumerate(samples):
        while ti + 1 < len(turns) and turns[ti + 1][0] <= t:
            ti += 1
        k = turns[ti][1]
        band = None
        if mode == "mosaico" and i in stack:
            # reacción: varios hablando/riéndose a la vez → pantalla dividida con cada uno en su panel
            people = stack[i]
            ph = H // len(people)
            rects = []
            for p in people:
                tx, ty, tw, th = lay["recuadros"][p]
                face = max((f for f in fs if tx <= f[0] <= tx + tw and ty <= f[1] <= ty + th),
                           key=lambda f: f[2], default=None)
                rects.append(_fit_rect((tx, ty, tw, th), W / ph, face[0] if face else None))
            view = ("stack", tuple(rects))
            cut = prev_rect != view
            prev_rect, cur = view, k
            keys.append((t, view, cut, None))
            continue
        if mode == "mosaico":
            if seguir and extras[i]["mosaico"]:
                tx, ty, tw, th = lay["recuadros"][k]
                face = max((f for f in fs if tx <= f[0] <= tx + tw and ty <= f[1] <= ty + th),
                           key=lambda f: f[2], default=None)
                asp = CFG["layout"]["mosaico"].get("aspecto_zoom", ct["aspecto_recuadro"])
                rect = _fit_rect((tx, ty, tw, th), asp, face[0] if face else None)
                if prev_rect and prev_rect[0] != "stack" and prev_rect[1] == ty and abs(prev_rect[0] - rect[0]) < 0.15 * tw and cur == k:
                    rect = prev_rect  # mismo recuadro: no mover por un cambio chico de la cara
            elif extras[i]["mosaico"]:
                # cámara fija: la llamada entera, recortada al mosaico para que se vea más grande
                tl = lay["recuadros"]
                x0, y0 = min(r[0] for r in tl) - 6, min(r[1] for r in tl) - 6
                x1, y1 = max(r[0] + r[2] for r in tl) + 6, max(r[1] + r[3] for r in tl) + 6
                x0, y0 = max(0, x0), max(0, y0)
                face, rect = None, (x0, y0, (min(vw, x1) - x0) // 2 * 2, (min(vh, y1) - y0) // 2 * 2)
            else:
                face, rect = None, (0, 0, vw // 2 * 2, vh // 2 * 2)
            s = W / rect[2]
            if face:
                band = (top + (face[1] - rect[1]) * s, face[2] * s)
            view = ("fit",) + rect
            cut = prev_rect is not None and rect != prev_rect and (prev_rect[0] == "stack" or cur != k or rect[2] != prev_rect[2])
            prev_rect = rect
        else:
            d = assigned[i][1]
            if k in d:
                last[k] = d[k][:3]
                sin_cara = 0
            else:
                sin_cara += 1
            target = last[k][0]
            cx_ = cuerpo[i] if cuerpo else None
            siguiendo_cuerpo = cx_ is not None and k not in d and sin_cara >= 3
            if siguiendo_cuerpo:
                # no se ve la cara hace un rato: el encuadre sigue al cuerpo (lo que se mueve), ya suavizado
                target = cx_
                last[k] = (cx_, last[k][1], last[k][2])
            if visita and visita[i] is not None:
                # otra persona en cámara que ya habló: PLANO ABIERTO con los dos enteros (cuadrado sobre fondo
                # desenfocado) hasta que se va, así se ven los gestos y las manos (corrección del usuario)
                vx = visita[i]
                lado = min(vh, vw) // 2 * 2
                centro = (vx + last[k][0]) / 2
                abierto_x = centro if abierto_x is None else abierto_x + 0.15 * (centro - abierto_x)
                x0 = int(min(max(0.0, abierto_x - lado / 2), vw - lado))
                y0 = (vh - lado) // 2
                view = ("fit", x0, y0, lado, lado)
                s = W / lado
                top_ = CFG["layout"]["camara"]["fit_top_frac"] * H
                band = (top_ + (last[k][1] - y0) * s, last[k][2] * s, (last[k][0] - x0) * s)
                cut = not abierto_prev
                abierto_prev, posx = True, None
                cur = k
                band = (band[0] - band[1] / 2 - 0.35 * band[1], band[0] + band[1] / 2 + 0.25 * band[1], band[2])
                keys.append((t, view, cut, band))
                continue
            if abierto_prev:
                abierto_prev, abierto_x = False, None
            cut = cur is not None and k != cur
            if posx is None or cut:
                posx = target
            elif siguiendo_cuerpo:
                # el cuerpo da una señal más nerviosa: zona muerta grande y movimiento lento (sin vibrar)
                if abs(target - posx) > 2.5 * dz:
                    posx += 0.5 * al * (target - posx)
            elif abs(target - posx) > dz:
                posx += al * (target - posx)
            x = int(min(max(0.0, posx - cw / 2), vw - cw))
            view = ("fill", x, 0, cw, ch)
            s = H / ch
            band = (last[k][1] * s, last[k][2] * s, (last[k][0] - x) * s)
        cur = k
        if band:
            band = (band[0] - band[1] / 2 - 0.35 * band[1], band[0] + band[1] / 2 + 0.25 * band[1],
                    band[2] if len(band) > 2 else W / 2)  # (arriba, abajo, x de la cara)
        keys.append((t, view, cut, band))
    return keys, [(round(a, 2), int(b)) for a, b in turns]


def _nitido(img, escala):
    """Al agrandar mucho una cámara chica (Discord) queda blanda: un poco de enfoque (unsharp mask)."""
    import cv2
    if escala < 2.0:
        return img
    k = min(1.0, 0.25 * (escala - 1.5))
    return cv2.addWeighted(img, 1 + k, cv2.GaussianBlur(img, (0, 0), 2.0), -k, 0)


def render_camera(raw, keys, out_path):
    """Genera el video vertical de la cámara virtual (misma línea de tiempo que el clip en bruto, sin audio)."""
    import cv2
    ct = CFG["layout"]["camara"]
    cap = cv2.VideoCapture(str(raw))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    proc = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                             "-r", f"{fps:.5f}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12",
                             "-pix_fmt", "yuv420p", str(out_path)], stdin=subprocess.PIPE)
    top = int(ct["fit_top_frac"] * H)
    j = i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        t = i / fps
        i += 1
        while j + 1 < len(keys) and keys[j + 1][0] <= t:
            j += 1
        tk, view = keys[j][0], keys[j][1]
        if view[0] == "gaming":
            (ax, ay, aw, ah), (bx, by, bw, bh), sp = view[1], view[2], view[3]
            tj = view[4] if len(view) > 4 else None
            if tj:  # tarjeta: fondo = juego desenfocado y oscuro, webcam redondeada encima, juego abajo
                out = np.empty((H, W, 3), np.uint8)
                g = fr[by:by + bh, bx:bx + bw]
                fondo = cv2.resize(cv2.resize(g, (W // 12, max(1, sp // 12))), (W, sp), interpolation=cv2.INTER_LINEAR)
                out[:sp] = (cv2.GaussianBlur(fondo, (0, 0), 6) * tj.get("oscuro", 0.55)).astype(np.uint8)
                out[sp:] = cv2.resize(g, (W, H - sp), interpolation=cv2.INTER_CUBIC)
                tx, ty, tw, th = tj["rect"]
                if "_mask" not in tj:
                    m = np.zeros((th, tw), np.uint8)
                    r = int(tj.get("radio", 40))
                    cv2.rectangle(m, (r, 0), (tw - r, th), 255, -1)
                    cv2.rectangle(m, (0, r), (tw, th - r), 255, -1)
                    for qx, qy in ((r, r), (tw - r - 1, r), (r, th - r - 1), (tw - r - 1, th - r - 1)):
                        cv2.circle(m, (qx, qy), r, 255, -1, cv2.LINE_AA)
                    tj["_mask"] = (cv2.GaussianBlur(m, (3, 3), 0).astype(np.float32) / 255)[..., None]
                card = _nitido(cv2.resize(fr[ay:ay + ah, ax:ax + aw], (tw, th), interpolation=cv2.INTER_CUBIC), tw / aw)
                zona = out[ty:ty + th, tx:tx + tw].astype(np.float32)
                out[ty:ty + th, tx:tx + tw] = (card * tj["_mask"] + zona * (1 - tj["_mask"])).astype(np.uint8)
                proc.stdin.write(out.tobytes())
                continue
            out = np.zeros((H, W, 3), np.uint8)
            out[:sp] = _nitido(cv2.resize(fr[ay:ay + ah, ax:ax + aw], (W, sp), interpolation=cv2.INTER_CUBIC), W / aw)
            out[sp:] = cv2.resize(fr[by:by + bh, bx:bx + bw], (W, H - sp), interpolation=cv2.INTER_CUBIC)
            out[sp - 3:sp + 3] = 0  # línea divisoria
            proc.stdin.write(out.tobytes())
            continue
        if view[0] == "stack":
            rects = view[1]
            ph = H // len(rects)
            out = np.zeros((H, W, 3), np.uint8)
            for n, (x, y, w, h) in enumerate(rects):
                y1 = (n + 1) * ph if n + 1 < len(rects) else H
                out[n * ph:y1] = _nitido(cv2.resize(fr[y:y + h, x:x + w], (W, y1 - n * ph),
                                                    interpolation=cv2.INTER_CUBIC), W / w)
                if n:
                    out[n * ph - 2:n * ph + 2] = 0  # línea divisoria fina
            proc.stdin.write(out.tobytes())
            continue
        kind, x, y, w, h = view
        if kind == "fill" and j + 1 < len(keys) and not keys[j + 1][2] and keys[j + 1][1][0] == "fill" and t >= tk:
            r = (t - tk) / max(1e-6, keys[j + 1][0] - tk)
            x = x + (keys[j + 1][1][1] - x) * min(1.0, r)
        x = int(round(x))
        crop = fr[y:y + h, x:x + w]
        if kind == "fill":
            out = _nitido(cv2.resize(crop, (W, H), interpolation=cv2.INTER_CUBIC), W / w)
        else:
            cw2 = int(h * W / H)
            c2 = crop[:, (w - cw2) // 2:(w - cw2) // 2 + cw2] if cw2 <= w else crop
            bg = cv2.resize(c2, (W // 12, H // 12), interpolation=cv2.INTER_AREA)
            bg = cv2.GaussianBlur(bg, (0, 0), 2.5)
            out = (cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR) * 0.55).astype(np.uint8)
            fh = int(round(h * W / w)) // 2 * 2
            fg = cv2.resize(crop, (W, fh), interpolation=cv2.INTER_CUBIC)
            y0 = top if top + fh <= H else (H - fh) // 2
            out[y0:y0 + fh] = fg
        proc.stdin.write(out.tobytes())
    cap.release()
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("Falló el render de la cámara virtual")


def crop_box(cx, cy, cw, ch, vw, vh):
    cw, ch = min(cw, vw), min(ch, vh)
    x = min(max(0, cx - cw / 2), vw - cw)
    y = min(max(0, cy - ch / 2), vh - ch)
    return int(cw) // 2 * 2, int(ch) // 2 * 2, int(x), int(y)


def face_bands_out(lay, vw, vh):
    """Franjas verticales (y0, y1) que ocupan las caras en el lienzo 1080x1920, con margen para pelo y mentón."""
    if "bandas" in lay:
        return list(lay["bandas"])
    boxes = []
    if lay["modo"] == "cara" and "cy" in lay:
        s = H / vh
        boxes.append((lay["cy"] * s, lay["fh"] * s))
    elif lay["modo"] == "apilado":
        ph = H // 2
        for i, (cx, cy, fh) in enumerate(lay["caras"]):
            ch = min(vh, fh * CFG["layout"]["alto_panel_en_caras"])
            cw, ch, x, y = crop_box(cx, cy, ch * W / ph, ch, vw, vh)
            s = ph / ch
            boxes.append((i * ph + (cy - y) * s, fh * s))
    return [(c - h / 2 - 0.35 * h, c + h / 2 + 0.25 * h) for c, h in boxes]


def place_text(h, pref_top, lo, hi, avoid):
    """Elige el y superior de un bloque de alto h dentro de [lo, hi] que no pise las franjas de `avoid`.
    Prioriza la posición más cercana a pref_top; si no hay lugar libre, la de menor superposición."""
    best = None
    for top in range(int(lo), int(hi - h) + 1, 10):
        over = sum(max(0, min(top + h, b) - max(top, a)) for a, b in avoid)
        key = (over, abs(top - pref_top))
        if best is None or key < best[0]:
            best = (key, top)
    return best[1] if best else int(pref_top)


def layout_filter(lay, vw, vh, src, out):
    """Devuelve el filtro que lleva [src] (video horizontal) a [out] 1080x1920.
    Con cámara virtual el video ya viene vertical (render_camera) y pasa directo."""
    if lay.get("camara"):
        return f"[{src}]setsar=1[{out}]"
    if lay["modo"] == "cara":
        cw, ch, x, y = crop_box(lay["cx"], vh / 2, vh * W / H, vh, vw, vh)  # alto completo, centrado en la cara
        return f"[{src}]crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1[{out}]"
    if lay["modo"] == "apilado":
        ph = H // 2
        parts = [f"[{src}]split=2[pa][pb]"]
        for i, (cx, cy, fh) in enumerate(lay["caras"]):
            ch = min(vh, fh * CFG["layout"]["alto_panel_en_caras"])
            cw, ch, x, y = crop_box(cx, cy, ch * W / ph, ch, vw, vh)
            parts.append(f"[p{'ab'[i]}]crop={cw}:{ch}:{x}:{y},scale={W}:{ph}:flags=lanczos,setsar=1[q{i}]")
        parts.append(f"[q0][q1]vstack=2[{out}]")
        return ";".join(parts)
    # blur: fondo desenfocado que cubre + video completo centrado
    return (f"[{src}]split=2[ba][bb];[ba]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=24:2,eq=brightness=-0.08[bg];[bb]scale={W}:-2:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[{out}]")


# ------------------------------------------------------------- 3. subtítulos ASS
def ass_color(alpha=0, rgb="FFFFFF"):
    return f"&H{alpha:02X}{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}"


def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def clean_word(w, upper=False):
    w = re.sub(r"[^\wáéíóúüñÁÉÍÓÚÜÑ¿?¡!]", "", w).strip("¿?¡!").strip()
    return w.upper() if upper else w.lower()


def censor(w):
    """Palabras fuertes con símbolos (como las cuentas de referencia: 'g#rd0'), para que IG no baje el alcance."""
    lista = CFG["subtitulos"].get("censura", [])
    base = w.lower()
    if not any(base == p or (base.startswith(p) and len(p) >= 5) for p in lista):
        return w
    tr = str.maketrans({"a": "@", "e": "3", "i": "1", "o": "0", "á": "@", "é": "3", "í": "1", "ó": "0"})
    return w[0] + w[1:-1].translate(tr).replace("u", "#") + w[-1] if len(w) > 2 else w


def chunk_words(words, upper):
    c = CFG["subtitulos"]
    out, cur = [], []
    for w in words:
        txt = censor(clean_word(w[2], upper))
        if not txt:
            continue
        who = w[3] if len(w) > 3 else 0
        if cur and cur[-1][3] != who:  # otra persona: bloque nuevo (y otro color)
            out.append(cur)
            cur = []
        if cur and (len(cur) >= c["max_palabras"] or w[0] - cur[-1][1] > 0.4):
            short3 = len(cur) == 2 and sum(len(x[2]) for x in cur) + len(txt) <= c["max_chars_3_palabras"] \
                and w[0] - cur[-1][1] <= 0.4
            if not short3:
                out.append(cur)
                cur = []
        cur.append((w[0], w[1], txt, who))
    if cur:
        out.append(cur)
    return out


def wrap(text, n):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > n:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return r"\N".join(lines)


def sub_events(words, lay, style_name):
    """Subtítulos ya armados (tiempo final): los usa el .ass y el borrador de CapCut, así salen iguales."""
    s = CFG["subtitulos"]["estilos"][style_name]
    y = int(lay.get("y_sub") or H * CFG["subtitulos"]["y_frac"][lay["modo"]])
    cols = lay.get("colores") or CFG["subtitulos"].get("colores_hablantes", ["FFFFFF"])
    chunks = chunk_words(words, s["mayusculas"])
    tam = s["tam"]
    # SEGUIMIENTO (como "subtítulos con seguimiento" de CapCut): el subtítulo va pegado debajo de la cara y la
    # acompaña suave; no salta de lugar en cada bloque. Sin cara a la vista: altura fija al medio.
    track_t, track_xy = [], []
    sc = CFG["subtitulos"].get("seguimiento", {})
    if sc.get("activar", True):
        px = py = None
        for t_, b_ in (lay.get("bandas_t") or []):
            if b_:
                ty_ = b_[1] + sc.get("debajo", 0.45) * tam
                if ty_ > sc.get("y_max", 0.72) * H:  # no entra debajo (zona de la UI de IG): arriba de la cabeza
                    arriba = b_[0] - 0.55 * tam
                    # cara enorme (primer plano): arriba tampoco entra y quedaría sobre la frente → al pecho, abajo de todo
                    ty_ = arriba if arriba >= sc.get("y_min", 0.42) * H else sc.get("y_max", 0.72) * H
                ty_ = min(max(ty_, sc.get("y_min", 0.42) * H), sc.get("y_max", 0.72) * H)
                # a lo ancho siempre centrado (si sigue la cara en x, los bloques largos se salen de la pantalla)
                tx_ = min(max(b_[2], 0.32 * W), 0.68 * W) if sc.get("seguir_x", False) and len(b_) > 2 else W / 2
            else:
                tx_, ty_ = W / 2, y
            if px is None or abs(ty_ - py) > 0.22 * H:  # corte de plano: se reubica de una
                px, py = tx_, ty_
            elif abs(ty_ - py) > sc.get("zona_quieta_px", 90):
                # solo acompaña si la persona se movió bastante: casi quieto, sin "bailar"
                a_ = sc.get("suavizado", 0.2)
                py = py + a_ * (ty_ - py)
            track_t.append(t_)
            track_xy.append((px, py))

    def pos_at(t):
        if not track_t:
            return W / 2, y
        j = max(0, min(len(track_t) - 1, int(np.searchsorted(track_t, t, side="right")) - 1))
        return track_xy[j]

    out = []
    for i, ch in enumerate(chunks):
        st = ch[0][0]
        en = ch[-1][1] + 0.25
        if i + 1 < len(chunks):
            en = min(en, chunks[i + 1][0][0])
        en = max(en, st + 0.25)
        dividido = None
        for a, b, n in lay.get("divididos", []):
            if a - 0.05 <= st < b:
                dividido = H // 2 if n == 2 else H * (n - 1) // n  # sobre la línea divisoria
        if dividido is not None:
            (x1, y1), (x2, y2) = (W / 2, dividido), (W / 2, dividido)
        else:
            (x1, y1), (x2, y2) = pos_at(st), pos_at(en)
        ev = {"start": round(st, 3), "end": round(en, 3), "text": " ".join(x[2] for x in ch),
              "color": cols[ch[0][3] % len(cols)], "hablante": ch[0][3], "x": int(x1), "y": int(y1)}
        if abs(x2 - x1) > 4 or abs(y2 - y1) > 4:
            ev["x2"], ev["y2"] = int(x2), int(y2)
        out.append(ev)
    return out


def _mov(e):
    """Posición del subtítulo: fija (\\pos) o acompañando a la cara durante el bloque (\\move)."""
    if "x2" in e:
        return f"\\move({e['x']},{e['y']},{e['x2']},{e['y2']},0,{int((e['end'] - e['start']) * 1000)})"
    return f"\\pos({e.get('x', W // 2)},{e['y']})"


def build_ass(path, words, dur, lay, style_name, hook, credit, cover=False):
    s = CFG["subtitulos"]["estilos"][style_name]
    hk, cr, pc = CFG["hook"], CFG["credito"], CFG["portada"]
    mk = CFG.get("marca_agua", {"mostrar": False, "fuente": "Poppins ExtraBold", "tam": 40, "alpha": 0.8})
    y = int(lay.get("y_sub") or H * CFG["subtitulos"]["y_frac"][lay["modo"]])
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{s['fuente']},{s['tam']},{ass_color()},{ass_color()},{ass_color(0, '000000')},{ass_color(s.get('sombra_alpha', 0x60), '000000')},0,0,0,0,100,100,{s.get('espaciado', 0)},0,1,{s['borde']},{s['sombra']},5,60,60,0,1
Style: Hook,{hk['fuente']},{hk['tam']},{ass_color(0, hk.get('color', 'FFFFFF'))},{ass_color()},{ass_color(0x30, '000000')},{ass_color(0xFF, '000000')},0,0,0,0,100,100,0,0,3,16,0,8,80,80,0,1
Style: Cred,{cr['fuente']},{cr['tam']},{ass_color(0x50)},{ass_color()},{ass_color(0x80, '000000')},{ass_color(0xFF, '000000')},0,0,0,0,100,100,0,0,1,2,0,5,60,60,0,1
Style: Marca,{mk['fuente']},{mk['tam']},{ass_color(int(255 * (1 - mk['alpha'])))},{ass_color()},{ass_color(0x40, '000000')},{ass_color(0xFF, '000000')},0,0,0,0,100,100,0,0,1,3,0,7,0,0,0,1
Style: Cover,{CFG['hook']['fuente']},{pc['tam']},{ass_color(0, pc.get('color', 'FFFFFF'))},{ass_color()},{ass_color(0, '000000')},{ass_color(0x60, '000000')},0,0,0,0,100,100,0,0,1,7,4,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    faces = lay.get("caras_out", [])
    if cover:
        if hook:
            txt = wrap(hook.upper(), 16)
            th = txt.count(r"\N") * pc["tam"] * 1.15 + pc["tam"] * 1.3
            # dentro del recorte 4:5 de la grilla (y 285-1635) y fuera de las caras; pc['y'] es el centro preferido
            top = place_text(th, pc["y"] - th / 2, 305, 1615, faces)
            ev.append(f"Dialogue: 0,0:00:00.00,0:00:10.00,Cover,,0,0,0,,{{\\pos({W // 2},{int(top + th / 2)})}}{txt}")
    else:
        blur = f"\\blur{s['blur']}" if s["blur"] else ""
        pp = CFG["subtitulos"].get("pop", {})
        if pp.get("activar"):  # pop out: entra chico, se pasa de tamaño y se asienta (como las referencias)
            a_, b_ = pp["subida_ms"], pp["subida_ms"] + pp["asiento_ms"]
            pop = (f"\\fscx{pp['desde']}\\fscy{pp['desde']}\\t(0,{a_},\\fscx{pp['pico']}\\fscy{pp['pico']})"
                   f"\\t({a_},{b_},\\fscx100\\fscy100)")
        else:
            pop = "\\fscx104\\fscy104\\t(0,80,\\fscx100\\fscy100)"
        for e in sub_events(words, lay, style_name):
            rgb = e["color"]
            col = f"\\c&H{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&" if rgb.upper() != "FFFFFF" else ""
            ev.append(f"Dialogue: 1,{ass_time(e['start'])},{ass_time(e['end'])},Cap,,0,0,0,,"
                      f"{{{_mov(e)}{col}{blur}{pop}}}{e['text']}")
        if hook and hk["mostrar"]:
            txt = wrap(hook, hk["chars_por_linea"])
            th = (txt.count(r"\N") + 1) * hk["tam"] * 1.2 + 2 * 16
            sub_tam = s["tam"]
            avoid = faces + [(y - sub_tam, y + sub_tam)]  # caras + renglón de subtítulos
            # zona segura de IG: 12% de arriba y 25% de abajo libres
            top = place_text(th, hk["y"], int(H * 0.12), int(H * 0.75), avoid)
            ev.append(f"Dialogue: 2,0:00:00.00,{ass_time(hk['duracion_s'])},Hook,,0,0,0,,"
                      f"{{\\pos({W // 2},{top})\\fad(0,200)}}{txt}")
        # zona libre de pantalla dividida (ahí el panel de abajo ocupa la parte baja: no se tapa la cara)
        libres, divs, t0 = [], [], 0.0
        for a, b, _ in sorted(lay.get("divididos", [])):
            if a > t0:
                libres.append((t0, a))
            divs.append((max(a, t0), b))
            t0 = max(t0, b)
        if t0 < dur:
            libres.append((t0, dur))
        # bloque de abajo: @clipardo con brillo y, debajo, el crédito del streamer (donde iba "@coker · kick")
        mk_h = mk["tam"] * 1.3 if mk.get("mostrar") else 0
        cr_h = cr["tam"] * 1.3 if credit and cr["mostrar"] else 0
        # la marca esquiva la zona por donde pasan los subtítulos (con seguimiento se mueven): no se tocan
        sys_ = [e_["y"] for e_ in sub_events(words, lay, style_name)] + \
               [e_.get("y2", e_["y"]) for e_ in sub_events(words, lay, style_name)]
        sub_band = (float(np.percentile(sys_, 5)) - 0.75 * s["tam"], float(np.percentile(sys_, 95)) + 0.75 * s["tam"]) \
            if sys_ else (y - s["tam"], y + s["tam"])
        avoid = faces + [sub_band]
        top = place_text(mk_h + cr_h, cr["y"] - (mk_h + cr_h) / 2, int(H * 0.12), int(H * 0.85), avoid)
        if mk.get("mostrar"):
            t_ = mk["texto"]
            ca = mk.get("color_arroba")
            if ca and t_.startswith("@"):
                t_ = f"{{\\c&H{ca[4:6]}{ca[2:4]}{ca[0:2]}&}}@{{\\c&HFFFFFF&}}{t_[1:]}"
            br = mk.get("brillo", {})
            g = br.get("color", "53FC18")
            glow = (f"\\1a&HFF&\\3c&H{g[4:6]}{g[2:4]}{g[0:2]}&\\3a&H{int(255 * (1 - br.get('alpha', 0.5))):02X}&"
                    f"\\bord{br.get('borde', 7)}\\blur{br.get('blur', 12)}")
            spots = [(a, b, f"\\an5\\pos({W // 2},{int(top + mk_h / 2)})") for a, b in libres] + \
                    [(a, b, f"\\an7\\pos({mk['x']},{mk['y']})") for a, b in divs]  # en dividida: arriba a la izq.
            # dónde quedó la marca (para Remotion y CapCut): [inicio, fin, x, y, "centro" | "izq"]
            lay["marca_pos"] = sorted([[round(a, 2), round(b, 2), W // 2, int(top + mk_h / 2), "centro"] for a, b in libres] +
                                      [[round(a, 2), round(b, 2), mk["x"], mk["y"], "izq"] for a, b in divs])
            for a, b, pos in spots:
                if br.get("activar"):  # halo de luz detrás: texto invisible con borde ancho difuminado
                    ev.append(f"Dialogue: 2,{ass_time(a)},{ass_time(b)},Marca,,0,0,0,,{{{pos}{glow}}}{mk['texto']}")
                ev.append(f"Dialogue: 3,{ass_time(a)},{ass_time(b)},Marca,,0,0,0,,{{{pos}}}{t_}")
        if credit and cr["mostrar"]:
            for a, b in libres:
                ev.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Cred,,0,0,0,,"
                          f"{{\\pos({W // 2},{int(top + mk_h + cr_h / 2)})}}{credit}")
    Path(path).write_text(head + "\n".join(ev) + "\n", encoding="utf-8")


# ------------------------------------------------------------- 4. punch-in y audio
def movimiento(video):
    """Qué parte del clip tiene imagen en movimiento fuerte (0-1): tiros, persecuciones, choques. 2026-11-21: calibrado
    con 18 clips: acción (Spreen "se me va", Bigfoot, Rubius vs Tesla, Zeko y la paloma) 0,5-0,8; charla/reacción < 0,36."""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(video), "-vf", "fps=4,scale=64:36,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8)
    if a.size < 64 * 36 * 3:
        return 0.0
    a = a[: a.size // (64 * 36) * 64 * 36].reshape(-1, 36, 64).astype(np.float32)
    return float((np.abs(np.diff(a, axis=0)).mean(axis=(1, 2)) / 255 > 0.06).mean())


def picos_accion(db, hop, keep, f, t_punch, n=4, sep=2.5):
    """Picos de audio (tiros, choques, gritos) para los pulsos de zoom de los clips de acción."""
    k = max(1, int(0.3 / hop))
    sm = np.convolve(db, np.ones(k) / k, "same")
    umbral = float(np.median(sm)) + CFG["subtitulos"].get("gta_accion", {}).get("pico_db", 8)
    cand = []
    for a, b in keep:
        for i in range(max(1, int(a / hop)), min(len(sm) - 1, int(b / hop))):
            if sm[i] > umbral and sm[i] >= sm[i - 1] and sm[i] >= sm[i + 1]:
                cand.append((sm[i], f(i * hop)))
    out = []
    for v, tn in sorted(cand, reverse=True):
        if tn is None or tn < 0.8 or (t_punch is not None and abs(tn - t_punch) < 1.5) or any(abs(tn - x) < sep for x in out):
            continue
        out.append(round(tn, 2))
        if len(out) >= n:
            break
    return sorted(out)


def golpe_fuerza(db, hop, keep, f, t_final):
    """Cuánto se despega el remate (dB sobre la mediana del clip): si es flojo, no lleva whoosh ni golpe."""
    if t_final is None:
        return 0.0
    src = None
    for a, b in keep:  # tiempo final → tiempo del clip en bruto
        if f(a) <= t_final <= f(b):
            src = a + (t_final - f(a))
            break
    if src is None:
        return 0.0
    seg = db[int(max(0, src - 0.2) / hop):int((src + 0.8) / hop)]
    # contra los picos normales de voz del clip (p90), no contra la mediana (que incluye silencios y siempre daba alto)
    kept = np.concatenate([db[int(a / hop):int(b / hop)] for a, b in keep]) if keep else db
    return round(float(np.percentile(seg, 90) - np.percentile(kept, 90)), 1) if len(seg) else 0.0


def punch_time(db, hop, keep, f, override=None):
    if override is not None:
        return f(override)
    c = CFG["punch_in"]
    total = f(keep[-1][1])
    k = max(1, int(0.5 / hop))
    sm = np.convolve(db, np.ones(k) / k, "same")
    best, best_t = -1e9, None
    for a, b in keep:
        for i in range(int(a / hop), min(len(sm), int(b / hop))):
            tn = f(i * hop)
            if tn >= total * (1 - c["buscar_en_ultimo_frac"]) and tn <= total - 0.6 and sm[i] > best:
                best, best_t = sm[i], tn
    return best_t


def zoom_filter(t0, src, out):
    c = CFG["punch_in"]
    if t0 is None or not c["activar"]:
        return f"[{src}]null[{out}]"
    a, r, d, z = max(0.0, t0 - 0.1), c["rampa_s"], c["duracion_s"], c["zoom"] - 1
    zexpr = f"(1+{z}*between(t,{a:.2f},{a + d:.2f})*min(1,(t-{a:.2f})/{r}))"
    return (f"[{src}]scale=w='trunc({W}*{zexpr}/2)*2':h='trunc({H}*{zexpr}/2)*2':eval=frame:flags=bicubic,"
            f"crop={W}:{H}[{out}]")


def loudnorm_measure(path, aexpr):
    a = CFG["audio"]
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-filter_complex",
                        f"[0:a]aselect='{aexpr}',asetpts=N/SR/TB,loudnorm=I={a['lufs']}:TP={a['true_peak']}:"
                        f"LRA={a['lra']}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    return json.loads(m.group(0)) if m else None


# ------------------------------------------------------------- render
WEBCAM_JOB = None  # (cx, cy, fh) de la webcam del streamer, igual en todos los clips de un stream (webcam_del_job)


def caras_rapidas(path, vw, vh, n=10):
    """Como detect_faces pero saltando a n momentos del clip (segundos en vez de minutos): para la webcam del stream
    y para el revisor automático (revisar.py)."""
    import cv2
    c = CFG["layout"]
    det_w = 640
    det_h = int(round(vh * det_w / vw))
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (det_w, det_h), c["score_min_cara"], 0.3, 50)
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or fps * 30
    sc = vw / det_w
    out = []
    for k in range(n):
        fr = int(total * (k + 0.5) / n)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, frame = cap.read()
        if not ok:
            continue
        _, faces = det.detect(cv2.resize(frame, (det_w, det_h)))
        fs = [((f[0] + f[2] / 2) * sc, (f[1] + f[3] / 2) * sc, f[3] * sc, 0.0) for f in (faces if faces is not None else [])]
        out.append((fr / fps, fs))
    cap.release()
    return out


def webcam_del_job(pre, vw, vh):
    """La webcam no se mueve en todo el stream: se toma la cara chica a un costado que más se repite en TODOS los
    clips. Así un clip oscuro o una cinemática con caras del juego no elige mal el recorte (corrección 2026-11-19)."""
    cg = CFG["layout"].get("gaming", {})
    celdas, clips_con = {}, {}
    for k, (samples, _) in pre.items():
        for _, fs in samples:
            for f in fs:
                if f[2] < cg.get("cara_max_frac", 0.15) * vh and (f[0] > 0.6 * vw or f[0] < 0.4 * vw):
                    c_ = int(f[0] / (0.06 * vw))  # solo la COLUMNA: en un stream largo la cara sube y baja
                    celdas.setdefault(c_, []).append(f)
                    clips_con.setdefault(c_, set()).add(k)
    if not celdas:
        return None
    c_, fs_ = max(celdas.items(), key=lambda kv: len(kv[1]))
    if len(clips_con[c_]) < max(2, 0.5 * len(pre)):
        return None
    return tuple(float(np.median([f[i] for f in fs_])) for i in range(3))


def render_clip(raw_mp4, outdir, style_name, forced_layout, capcut=False, pre=None):
    meta = json.loads(raw_mp4.with_suffix(".json").read_text(encoding="utf-8"))
    vw, vh, dur = probe(raw_mp4)
    fixes = {k.lower(): v for k, v in (meta.get("correcciones") or {}).items()}
    words = [(w[0], w[1], fixes.get(clean_word(w[2]), w[2])) for w in meta.get("words", [])]
    db, hop = audio_db(raw_mp4)
    keep = subtract(keep_segments(words, dur, db, hop), edit_cuts(words, dur, db, hop, meta))
    largo = sum(b - a for a, b in keep)
    if largo > CFG.get("recortes", {}).get("objetivo_max_s", 40):
        log(f"{raw_mp4.stem}: dura {largo:.0f}s (objetivo 25-40 s): marcar 'recortes' en el .json leyendo la transcripción")
    f = mapper(keep)
    new_dur = f(dur)
    mwords = [(f(s), f(e), w) for s, e, w in words if any(a - 0.05 <= s and e <= b + 0.05 for a, b in keep)]
    tiles = detect_mosaic(raw_mp4, vw, vh) if forced_layout in ("auto", "mosaico") else []
    samples, extras = (pre or {}).get(raw_mp4.name) or detect_faces(raw_mp4, vw, vh, dur, MosaicProbe(tiles, vw, vh) if tiles else None)
    lay = choose_layout(samples, forced_layout, tiles, vw, vh)
    if WEBCAM_JOB and not tiles and (lay["modo"] == "gaming" or meta.get("receta") == "gta"):
        # la webcam está siempre en la misma COLUMNA del stream, pero en 10 h el streamer se para, se acomoda: la
        # altura se toma de las caras de ESTE clip que caen en esa columna (si no hay, la del stream)
        cg_ = CFG["layout"].get("gaming", {})
        en_col = [f for _, fs in samples for f in fs
                  if abs(f[0] - WEBCAM_JOB[0]) < 0.08 * vw and f[2] < cg_.get("cara_max_frac", 0.15) * vh * 1.5]
        # solo se corrige si ESTE clip tiene caras en la columna de la webcam; si no (videos editados de YouTube,
        # donde la cámara cambia de lugar) se respeta lo que detectó el clip
        if len(en_col) >= 0.3 * max(1, len(samples)):
            cx_, cy_, fh_ = (float(np.median([f[i] for f in en_col])) for i in range(3))
            if lay["modo"] != "gaming" or abs(lay["cx"] - cx_) > 0.05 * vw or abs(lay["cy"] - cy_) > 0.06 * vh:
                log(f"{raw_mp4.stem}: webcam corregida a ({cx_:.0f}, {cy_:.0f}, {fh_:.0f})")
            lay.update(modo="gaming", cx=cx_, cy=cy_, fh=fh_)
    if meta.get("webcam"):
        # webcam a mano por clip ([cx, cy, fh] en píxeles del stream): cuando una escena del juego con caras tira la
        # mediana para un costado y la cámara queda corrida (thegrefg 02, 2026-11-20)
        cx_, cy_, fh_ = (float(v) for v in meta["webcam"])
        lay.update(modo="gaming", cx=cx_, cy=cy_, fh=fh_)
        log(f"{raw_mp4.stem}: webcam a mano ({cx_:.0f}, {cy_:.0f}, {fh_:.0f})")
    if meta.get("receta") == "gta" and lay["modo"] == "gaming":  # GTA: más gameplay, cámara más chica
        lay["alto_camara"] = CFG["layout"].get("gta", {}).get("alto_camara", 560)
        tj = CFG["layout"].get("gta", {}).get("tarjeta") or {}
        if meta.get("camara", "tarjeta" if tj.get("activo") else "") == "tarjeta" and tj:
            lay["tarjeta"] = dict(tj)
    WORK.mkdir(parents=True, exist_ok=True)
    stem = raw_mp4.stem
    video_in = raw_mp4
    # voces (una sola cámara): quién habla fuera o dentro de plano además del streamer
    vs = voice_speakers(raw_mp4, words) if lay["modo"] in ("cara", "blur", "gaming") else None
    if lay["modo"] in ("mosaico", "gaming") or (lay["modo"] in ("cara", "hablante") and ("cx" in lay or "caras" in lay)):
        keys, turns = plan_camera(lay, samples, extras, words, vw, vh, vs)
        # banda de la cara en cada momento (tiempo final): el subtítulo se corre para no tapar la cara
        lay["bandas_t"] = [(round(f(k[0]), 2), [round(v_) for v_ in k[3]] if k[3] else None)
                           for k in keys if any(a <= k[0] <= b for a, b in keep)]
        bands = [k[3] for k in keys if k[3] and any(a <= k[0] <= b for a, b in keep)]
        if bands:
            lay["bandas"] = [(float(np.percentile([b[0] for b in bands], 10)),
                              float(np.percentile([b[1] for b in bands], 90)))]
        lay.update(camara=True, turnos=turns)
        # tramos en pantalla dividida, en tiempo final (los subtítulos van sobre la línea divisoria)
        div, run0 = [], None
        for i, (t, view, _, _) in enumerate(keys + [(dur, ("fin",), True, None)]):
            n = len(view[1]) if view[0] == "stack" else 0
            if run0 and (n != run0[1] or view[0] != "stack"):
                div.append((round(f(run0[0]), 2), round(f(t), 2), run0[1]))
                run0 = None
            if n and not run0:
                run0 = (t, n)
        lay["divididos"] = [d for d in div if d[1] - d[0] > 0.2]
        video_in = WORK / f"{stem}_cam.mp4"
        render_camera(raw_mp4, keys, video_in)
    # quién dice cada palabra (para el color del subtítulo): el principal en blanco, los demás en colores
    turns = lay.get("turnos") or [(0.0, 0)]
    def speaker_at(t):
        k = turns[0][1]
        for a, p in turns:
            if a <= t:
                k = p
        return k
    spk = [speaker_at(s) for s, e, w in words]
    if len(set(spk)) == 1 and vs:  # una sola cámara: separar por voz a quien habla fuera de plano
        spk = vs
        log(f"{stem}: {vs.count(1)} palabras de otra voz (subtítulo en otro color)")
    order = [p for p, _ in sorted(((p, spk.count(p)) for p in set(spk)), key=lambda x: -x[1])]
    rank = {p: i for i, p in enumerate(order)}
    # color fijo por voz: si habla uno solo, blanco; si hablan varios, cada uno un color llamativo distinto,
    # elegido al azar por clip (siempre el mismo para la misma persona dentro del clip)
    if len(order) <= 1:
        lay["colores"] = ["FFFFFF"]
    else:
        pal = list(CFG["subtitulos"].get("paleta_voces", ["FFE81F", "FF5FD2", "3FD0FF", "FF9A1F", "B884FF"]))
        # la paleta está ordenada para que dos colores seguidos contrasten (amarillo, celeste, rosa, verde...):
        # se elige al azar por dónde empezar, así varía entre clips sin que salgan dos parecidos (rosa/violeta)
        import random
        k0 = random.Random(stem).randrange(len(pal))
        lay["colores"] = pal[k0:] + pal[:k0]
    log(f"{stem}: {len(order)} voz/voces → colores {lay['colores'][:len(order)]}")
    mwords = [(f(s), f(e), w, rank[k]) for (s, e, w), k in zip(words, spk)
              if any(a - 0.05 <= s and e <= b + 0.05 for a, b in keep)]
    ga = CFG["subtitulos"].get("gta_accion", {})
    juego = meta.get("receta") == "gta" or TIPOS.get(lay["modo"]) == "gaming"
    mov = movimiento(raw_mp4) if juego else 0.0
    accion = juego and mov >= ga.get("movimiento_min", 0.45)
    if accion and meta.get("subtitulos") is None:
        # 2026-11-21 ("si son momentos de acción no le pongas subtítulos, autoanalizalo"): imagen en movimiento fuerte
        log(f"{stem}: acción ({mov:.0%} del clip con movimiento fuerte) → sin subtítulos + pulsos de zoom")
        meta["subtitulos"] = False
    if meta.get("subtitulos") is None and juego and mwords:
        # 2026-11-20 (estilo @elcokismo, "sí, solo en acción"): GTA de acción = poca charla o puros gritos repetidos
        txt = [re.sub(r"\W", "", w[2].lower()) for w in mwords]
        txt = [x for x in txt if x]
        dens = len(txt) / max(1.0, mwords[-1][1] - mwords[0][0])
        unicas = len(set(txt)) / max(1, len(txt))
        if dens < ga.get("palabras_seg_max", 1.2) or unicas < ga.get("unicas_max", 0.45):
            log(f"{stem}: GTA de acción ({dens:.1f} pal/s, {unicas:.0%} únicas) → sin subtítulos")
            meta["subtitulos"] = False
    if meta.get("subtitulos") is False:  # clip de acción: sin subtítulos, que se luzca el gameplay
        mwords = []
    lay["caras_out"] = [(round(a), round(b)) for a, b in face_bands_out(lay, vw, vh)]
    t_punch = punch_time(db, hop, keep, f, meta.get("remate_t"))
    golpes_extra = picos_accion(db, hop, keep, f, t_punch) if accion and ga.get("pulsos", True) else []
    credit = f"@{meta.get('streamer', '').lower()} · {meta.get('plataforma', '')}".strip(" ·@")
    credit = f"@{credit}" if credit and not credit.startswith("@") else credit
    ass_rel = f"work/{stem}.ass"
    build_ass(ROOT / ass_rel, mwords, new_dur, lay, style_name, meta.get("hook_text", ""), credit)
    vexpr = between_expr(keep)
    # remate en blanco y negro: si los últimos segundos son risa (audio alto, casi sin palabras)
    bn = CFG.get("cierre_bn", {})
    t_bn = None
    if bn.get("activar", True):
        d = bn.get("dur_s", 1.8)
        end_src = keep[-1][1]
        tail = db[int(max(0, end_src - d) / hop):int(end_src / hop)]
        few = sum(1 for w in mwords if w[0] >= new_dur - d) <= bn.get("max_palabras", 3)
        if len(tail) and few and float(np.mean(tail)) >= float(np.median(db)) - bn.get("tolerancia_db", 3):
            t_bn = max(0.0, new_dur - d)
    bn_f = f",hue=s=0:enable='gte(t,{t_bn:.2f})'" if t_bn is not None else ""
    graph = ";".join([
        f"[0:v]fps={FPS},select='{vexpr}',setpts=N/{FPS}/TB[v0]",
        layout_filter(lay, vw, vh, "v0", "v1"),
        zoom_filter(t_punch, "v1", "v2"),
        f"[v2]ass={ass_rel}:fontsdir=tools/fonts{bn_f},format=yuv420p[v]",
    ])
    ln = loudnorm_measure(raw_mp4, vexpr)
    if ln and "inf" in str(ln.get("input_i")):
        # tramo silenciado (p. ej. Twitch mutea partes del VOD por música): sin voz no hay clip
        raise RuntimeError(f"{raw_mp4}: audio silenciado en el VOD, se saltea")
    a = CFG["audio"]
    lnf = f"loudnorm=I={a['lufs']}:TP={a['true_peak']}:LRA={a['lra']}"
    if ln:
        lnf += (f":measured_I={ln['input_i']}:measured_TP={ln['input_tp']}:measured_LRA={ln['input_lra']}:"
                f"measured_thresh={ln['input_thresh']}:offset={ln['target_offset']}:linear=true")
    graph += f";[1:a]aselect='{vexpr}',asetpts=N/SR/TB,{lnf},aresample=48000[a]"
    out = outdir / f"{stem}.mp4"
    s = CFG["salida"]
    log(f"{stem}: layout {lay['modo']}, estilo {style_name}, {dur:.1f}s → {new_dur:.1f}s"
        + (f", punch-in en {t_punch:.1f}s" if t_punch is not None else ""))
    run([FFMPEG, "-y", "-v", "error", "-i", video_in, "-i", raw_mp4, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", s["preset"], "-crf", s["crf"], "-profile:v", "high", "-level", "4.1",
         "-maxrate", s["maxrate"], "-bufsize", s["bufsize"], "-r", FPS, "-c:a", "aac", "-b:a", s["audio_bitrate"],
         "-movflags", "+faststart", out])
    if capcut:
        # base para CapCut: misma edición (cámara, cortes, zoom, B/N, audio) pero SIN textos quemados;
        # los subtítulos van como capas editables en el borrador (capcut-editor)
        cdir = outdir / "capcut"
        cdir.mkdir(exist_ok=True)
        gbase = graph.replace(f"[v2]ass={ass_rel}:fontsdir=tools/fonts{bn_f},format=yuv420p[v]",
                              f"[v2]null{bn_f},format=yuv420p[v]")
        run([FFMPEG, "-y", "-v", "error", "-i", video_in, "-i", raw_mp4, "-filter_complex", gbase, "-map", "[v]",
             "-map", "[a]", "-c:v", "libx264", "-preset", s["preset"], "-crf", str(s.get("crf_base", 12)), "-profile:v", "high",
             "-level", "4.1", "-r", FPS, "-c:a", "aac", "-b:a", s["audio_bitrate"], "-movflags", "+faststart",
             cdir / f"{stem}_base.mp4"])
        st_ = CFG["subtitulos"]["estilos"][style_name]
        (cdir / f"{stem}_capcut.json").write_text(json.dumps({
            "video": f"{stem}_base.mp4", "duracion": round(new_dur, 3), "ancho": W, "alto": H,
            "subtitulos": sub_events(mwords, lay, style_name),
            "estilo": {k: st_.get(k) for k in ("fuente", "tam", "borde", "sombra")},
            "credito": credit if CFG["credito"]["mostrar"] else "", "hook": meta.get("hook_text", ""),
            "hook_mostrar": CFG["hook"]["mostrar"], "hook_color": CFG["hook"].get("color", "53FC18"),
            "hook_dur": CFG["hook"]["duracion_s"], "caption": meta.get("caption", ""),
            "marca_agua": CFG.get("marca_agua", {}), "pop": CFG["subtitulos"].get("pop", {}).get("activar", False),
            "tipo": TIPOS.get(lay["modo"], "desconocido"), "divididos": lay.get("divididos", []),
            "split": lay.get("split"),
            "marca_pos": lay.get("marca_pos", []), "golpe": t_punch, "golpes_extra": golpes_extra, "accion": accion, "movimiento": round(mov, 2),
            "tam_sub": st_.get("tam", 88),
            # para que Remotion decida: dónde hay caras (tarjeta Seguir) y si el remate es fuerte (efectos de sonido)
            "bandas_t": lay.get("bandas_t", []), "golpe_fuerza": golpe_fuerza(db, hop, keep, f, t_punch),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{stem}: base para CapCut en {cdir}")
    # portada: el primer plano más grande de la cara + hook grande dentro del recorte 4:5 de la grilla
    src_t = cover_time(samples, keep, dur / 2)
    cover_rel = f"work/{stem}_cover.ass"
    build_ass(ROOT / cover_rel, [], 10, lay, style_name, meta.get("hook_text", ""), None, cover=True)
    run([FFMPEG, "-y", "-v", "error", "-ss", f"{src_t:.2f}", "-i", video_in, "-frames:v", "1", "-filter_complex",
         layout_filter(lay, vw, vh, "0:v", "c1") + f";[c1]ass={cover_rel}:fontsdir=tools/fonts[c]", "-map", "[c]",
         "-q:v", "2", outdir / f"{stem}.jpg"])
    (outdir / f"{stem}.txt").write_text(meta.get("caption", "").strip() + "\n", encoding="utf-8")
    info = {k: meta.get(k) for k in ("id", "score", "breakdown", "tipo", "hook_text", "caption", "streamer",
                                     "plataforma", "fuente", "start", "end")}
    info.update(tipo_clip=TIPOS.get(lay["modo"], "desconocido"), archivo=out.name, duracion_final=round(new_dur, 1), layout=lay, estilo=style_name,
                punch_in_s=t_punch, cierre_bn_s=t_bn, tramos=keep, ln_medicion=ln)
    (outdir / f"{stem}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def update_records(job, results):
    reg = FINAL / "registro.csv"
    new = not reg.exists()
    with open(reg, "a", encoding="utf-8-sig", newline="") as fh:
        wr = csv.writer(fh)
        if new:
            wr.writerow(["render", "job", "clip", "streamer", "tipo", "puntaje", "duracion_final", "layout",
                         "estilo", "hook"])
        for r in results:
            wr.writerow([dt.datetime.now().isoformat(timespec="minutes"), job, r["archivo"], r["streamer"],
                         r["tipo"], r["score"], r["duracion_final"], r["layout"]["modo"], r["estilo"],
                         r["hook_text"]])
    cal = ROOT / "calendario" / "calendario.csv"
    if cal.exists():
        with open(cal, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        names = {r["archivo"] for r in results}
        for row in rows:
            if row["job"] == job and row["clip"] in names:
                row["estado"] = "listo para subir"
        with open(cal, "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["fecha"])
            wr.writeheader()
            wr.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("job")
    r.add_argument("--estilo", default=CFG["subtitulos"]["estilo"], choices=["limpio", "bubble", "ab"])
    r.add_argument("--layout", default=CFG["layout"]["modo"], choices=["auto", "cara", "hablante", "mosaico", "apilado", "blur"])
    r.add_argument("--solo", help="prefijo del clip, ej. 01")
    r.add_argument("--capcut", action="store_true", help="además arma la base sin textos para el borrador de CapCut")
    a = ap.parse_args()
    src = inside_root(a.job if Path(a.job).is_absolute() else RAW / a.job)
    clips = sorted(p for p in src.glob("*.mp4") if p.with_suffix(".json").exists())
    if a.solo:
        clips = [p for p in clips if p.name.startswith(a.solo)]
    if not clips:
        sys.exit(f"No hay clips con su .json en {src}")
    outdir = FINAL / src.name
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    # caras de TODOS los clips del stream (también con --solo) para fijar la webcam una sola vez; se reusan al renderizar
    global WEBCAM_JOB
    todos = sorted(p for p in src.glob("*.mp4") if p.with_suffix(".json").exists() and not p.stem.endswith("_ffmpeg"))
    pre = {}
    if a.layout in ("auto", "gaming"):
        for p in todos:
            vw_, vh_, d_ = probe(p)
            pre[p.name] = (caras_rapidas(p, vw_, vh_), None)
        WEBCAM_JOB = webcam_del_job(pre, vw_, vh_) if pre else None
        if WEBCAM_JOB:
            log(f"webcam del stream: {tuple(round(v) for v in WEBCAM_JOB)}")
    for i, p in enumerate(clips):
        style = a.estilo if a.estilo != "ab" else ("limpio", "bubble")[i % 2]
        try:
            results.append(render_clip(p, outdir, style, a.layout, a.capcut))
        except RuntimeError as e:  # un clip roto no frena al resto
            print(f"SALTEADO: {e}", flush=True)
    update_records(src.name, results)
    print("\n| Clip | Tipo | Layout | Estilo | Duración | Punch-in |\n|---|---|---|---|---|---|")
    for r_ in results:
        print(f"| {r_['archivo']} | {r_['tipo_clip']} | {r_['layout']['modo']} | {r_['estilo']} | {r_['duracion_final']}s | "
              f"{'-' if r_['punch_in_s'] is None else round(r_['punch_in_s'], 1)} |")
    print(f"\nReels en: {outdir}")


if __name__ == "__main__":
    main()
