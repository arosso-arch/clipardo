"""clip-finder: encuentra momentos graciosos en VODs de Twitch / Kick / YouTube o archivos locales.

Subcomandos:
  prepare <url|archivo> [...]   descarga audio + chat, detecta candidatos y los transcribe
  prepare --inbox               procesa inbox/links.txt y los videos sueltos en inbox/
  cut <job> [--top N] [--min-score S]   corta los clips elegidos (selections.json) y arma el calendario
  status                        lista los trabajos y en qué paso está cada uno

Todo lo que escribe queda dentro de CLIPS_ROOT (CLIPARDO_HOME; ver clipardo_rutas.py).
No usa API keys ni manda datos a ningún servidor salvo las descargas de la plataforma del VOD.
"""
import argparse
import csv
import datetime as dt
import glob
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

SKILL_DIR = Path(__file__).resolve().parent
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
ROOT = Path(os.environ.get("CLIPS_ROOT") or R.HOME).resolve()
CFG = json.loads((SKILL_DIR / "config.json").read_text(encoding="utf-8"))
TOOLS = ROOT / "tools"
FFMPEG = str(next(TOOLS.glob("ffmpeg/*/bin/ffmpeg.exe"), "ffmpeg"))
TWITCHDL = TOOLS / "twitchdl" / "TwitchDownloaderCLI.exe"
YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings"]
JOBS, RAW, INBOX, CAL = ROOT / "jobs", ROOT / "clips" / "raw", ROOT / "inbox", ROOT / "calendario"
SR = 16000  # audio de trabajo: PCM 16 kHz mono int16
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- utilidades
def log(*a):
    print("[clip-finder]", *a, flush=True)


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def hms(s):
    s = max(0.0, float(s))
    return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:04.1f}"


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "stream"


def norm(s):
    """minúsculas y sin tildes, para buscar gatillos."""
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def inside_root(p):
    p = Path(p).resolve()
    if ROOT not in p.parents and p != ROOT:
        sys.exit(f"Ruta fuera de {ROOT}: {p}")
    return p


def jload(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def jsave(p, obj):
    p = inside_root(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def platform_of(src):
    if re.match(r"https?://", src):
        for key, name in (("twitch.tv", "twitch"), ("kick.com", "kick"), ("youtu", "youtube")):
            if key in src:
                return name
        return "web"
    return "local"


# ---------------------------------------------------------------- 1. ingesta
def ingest(src):
    plat = platform_of(src)
    if plat == "local":
        p = Path(src).resolve()
        if not p.exists():
            sys.exit(f"No existe el archivo {p}")
        meta = {"source": str(p), "platform": "local", "title": p.stem, "uploader": "", "id": p.stem, "duration": None}
        side = p.with_suffix(".meta.json")  # tramos del modo en vivo (envivo.py): streamer, plataforma y título reales
        if side.exists():
            meta.update({k: v for k, v in jload(side, {}).items() if k not in ("source", "platform")})
    else:
        out = subprocess.run(YTDLP + ["-J", "--skip-download", src], capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        info = json.loads(out)
        meta = {"source": src, "platform": plat, "title": info.get("title") or "",
                "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id") or "",
                "id": str(info.get("id")), "duration": info.get("duration"),
                "upload_date": info.get("upload_date")}
        if "/clip/" in src or "/clips/" in src:
            # clip de la comunidad: en Twitch "uploader" es quien hizo el clip, no el streamer → el canal sale de la URL
            meta["uploader"] = src.split("://", 1)[-1].split("/")[1].lower()
    job = JOBS / f"{slugify(meta['uploader'] or plat)}-{slugify(meta['id'])}"
    job.mkdir(parents=True, exist_ok=True)
    if not (job / "meta.json").exists():
        jsave(job / "meta.json", meta)
    log(f"Trabajo: {job.name}  ({plat}, '{meta['title'][:60]}')")
    return job


def get_audio(job):
    meta = jload(job / "meta.json")
    pcm = job / "audio.pcm"
    if pcm.exists():
        return
    if meta["platform"] == "local":
        src = meta["source"]
    else:
        log("Descargando solo el audio…")
        # bestaudio si la plataforma lo ofrece; si no, la peor calidad de video (pesa menos)
        run(YTDLP + ["-f", "bestaudio/worst", "-N", "8", "--no-part", "-o", str(job / "src.%(ext)s"), meta["source"]])
        src = str(next(f for f in job.glob("src.*")))
    log("Convirtiendo a PCM 16 kHz mono…")
    run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le",
         str(pcm) + ".tmp"])
    os.replace(str(pcm) + ".tmp", pcm)
    for f in job.glob("src.*"):
        f.unlink()
    if not meta.get("duration"):
        meta["duration"] = pcm.stat().st_size / 2 / SR
        jsave(job / "meta.json", meta)


def get_chat(job):
    meta = jload(job / "meta.json")
    out = job / "chat_norm.json"
    if out.exists():
        return
    msgs = []
    try:
        if meta["platform"] == "twitch" and TWITCHDL.exists():
            log("Descargando chat de Twitch…")
            m = re.search(r"/videos/(\d+)", meta["source"])
            vid = m.group(1) if m else meta["id"].lstrip("v")
            raw = job / "chat_twitch.json"
            run([TWITCHDL, "chatdownload", "--id", vid, "-o", raw], cwd=job, stdout=subprocess.DEVNULL)
            d = jload(raw, {})
            msgs = [[c["content_offset_seconds"], (c.get("message") or {}).get("body", "")]
                    for c in d.get("comments", [])]
        elif meta["platform"] == "youtube":
            log("Descargando chat de YouTube…")
            run(YTDLP + ["--skip-download", "--write-subs", "--sub-langs", "live_chat", "-o", str(job / "yt"),
                         meta["source"]])
            p = job / "yt.live_chat.json"
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    try:
                        r = json.loads(line).get("replayChatItemAction", {})
                    except json.JSONDecodeError:
                        continue
                    t = int(r.get("videoOffsetTimeMsec", 0)) / 1000
                    for a in r.get("actions", []):
                        mr = a.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer")
                        if mr:
                            txt = "".join(x.get("text") or "".join(x.get("emoji", {}).get("shortcuts", [""])[:1])
                                          for x in mr.get("message", {}).get("runs", []))
                            msgs.append([t, txt])
        elif meta["platform"] == "kick":
            log("Chat de Kick: no hay descarga confiable todavía. Sigo solo con audio + transcripción.")
    except subprocess.CalledProcessError as e:
        log(f"No pude bajar el chat ({e}). Sigo sin chat.")
    jsave(out, msgs)
    log(f"Chat: {len(msgs)} mensajes")


# ---------------------------------------------------------------- 2. señales
def load_pcm(job):
    return np.memmap(job / "audio.pcm", dtype=np.int16, mode="r")


def audio_db_per_second(x):
    """Volumen (dB) de cada medio segundo, reducido a 1 valor por segundo (el máximo). Procesa por bloques."""
    hop = SR // 2
    n = len(x) // hop
    db = np.empty(n, np.float32)
    B = 4000
    for i in range(0, n, B):
        k = min(B, n - i)
        blk = np.asarray(x[i * hop:(i + k) * hop], dtype=np.float32).reshape(k, hop) / 32768.0
        db[i:i + k] = 10 * np.log10((blk ** 2).mean(1) + 1e-10)
    n2 = n // 2
    return db[:n2 * 2].reshape(n2, 2).max(1)


def robust_z(v, block=120):
    """Cuánto se despega cada punto de su entorno: (valor - mediana local) / dispersión global."""
    v = np.asarray(v, np.float32)
    if len(v) == 0:
        return v
    nb = max(1, len(v) // block)
    centers, meds = [], []
    for b in range(nb):
        seg = v[b * block:(b + 1) * block] if b < nb - 1 else v[b * block:]
        centers.append(b * block + len(seg) / 2)
        meds.append(np.median(seg))
    base = np.interp(np.arange(len(v)), centers, meds)
    dev = v - base
    mad = np.median(np.abs(dev - np.median(dev))) * 1.4826 + 1e-6
    return dev / mad


def smooth_max(v, w):
    if w <= 1 or len(v) == 0:
        return v
    pad = np.pad(v, (w // 2, w - w // 2 - 1), mode="edge")
    return np.lib.stride_tricks.sliding_window_view(pad, w).max(1)


def chat_curves(msgs, n):
    count = np.zeros(n, np.float32)
    emo = np.zeros(n, np.float32)
    delay = CFG["chat_delay_s"]
    emote_re = re.compile(r"\b(" + "|".join(map(re.escape, CFG["emotes"])) + r")\b", re.I)
    laugh_re = re.compile(r"\b(?:j[aeiou]?(?:j[aeiou]){2,}j?|js(?:js)+|x+d+)\b", re.I)
    for t, txt in msgs:
        i = int(t - delay)  # el chat reacciona unos segundos después del momento
        if 0 <= i < n:
            count[i] += 1
            emo[i] += len(emote_re.findall(txt)) + len(laugh_re.findall(txt))
    k = np.ones(5, np.float32)  # suma móvil de 5 s
    return np.convolve(count, k, "same"), np.convolve(emo, k, "same")


def find_candidates(job):
    out = job / "candidates.json"
    if out.exists():
        return
    log("Analizando volumen y chat…")
    x = load_pcm(job)
    db = audio_db_per_second(x)
    n = len(db)
    w = CFG["pesos_prefiltro"]
    az = smooth_max(np.clip(robust_z(db), 0, 8), 3)
    hype = w["audio"] * az
    msgs = jload(job / "chat_norm.json", [])
    has_chat = len(msgs) > 50
    if has_chat:
        cc, ce = chat_curves(msgs, n)
        cz = np.clip(robust_z(cc), 0, 8)
        ez = np.clip(robust_z(ce), 0, 8)
        hype = hype + w["chat"] * cz + w["emotes"] * ez
    else:
        hype = hype * w.get("audio_sin_chat", 0.6)  # sin chat, el volumen solo se confunde con gritos de gaming
    segs = full_segments(job)
    has_text = bool(segs)
    if has_text:
        tv = text_curve(segs, n)
        nz = tv[tv > 0]
        # señal dispersa (casi todo es 0): se escala contra el percentil 90 de los segundos con señal
        scale = float(np.percentile(nz, 90)) if len(nz) else 1.0
        tz = np.clip(3.0 * tv / (scale or 1.0), 0, 8)
    c = CFG["candidatos"]
    # Dos rankings separados (audio/chat y texto) que se reparten los cupos: así una señal no tapa a la otra.
    curves = [hype] + ([hype * 0.3 + w["texto"] * tz] if has_text else [])
    quota = [c["cantidad"] // len(curves)] * len(curves)
    quota[0] += c["cantidad"] - sum(quota)
    blocked = np.zeros(n, bool)
    picks, per_hour = [], {}
    for curve, q in zip(curves, quota):
        h = np.where(blocked, 0, curve)
        got = 0
        while got < q and h.max() > 0.5:
            p = int(h.argmax())
            lo, hi = max(0, p - c["separacion_min_s"]), p + c["separacion_min_s"]
            h[lo:hi] = 0
            if per_hour.get(p // 3600, 0) >= c["max_por_hora"]:
                continue  # reparte los candidatos a lo largo del stream
            per_hour[p // 3600] = per_hour.get(p // 3600, 0) + 1
            picks.append(p)
            blocked[lo:hi] = True
            got += 1
    hype = np.maximum.reduce(curves)
    top = float(hype.max()) or 1.0
    cands = []
    for i, p in enumerate(sorted(picks)):
        s, e = max(0, p - c["pre_s"]), min(n, p + c["post_s"])
        info = {"id": f"C{i + 1:02d}", "peak": p, "start": float(s), "end": float(e),
                "pre_score": round(100 * float(hype[p]) / top), "audio_z": round(float(az[p]), 1)}
        if has_chat:
            info.update(chat_z=round(float(cz[p]), 1), emote_z=round(float(ez[p]), 1),
                        msgs_5s=int(cc[p]), emotes_5s=int(ce[p]))
        if has_text:
            info["texto_z"] = round(float(tz[p]), 1)
        cands.append(info)
    jsave(out, {"has_chat": has_chat, "duration_s": n, "candidates": cands})
    log(f"{len(cands)} candidatos (chat: {'sí' if has_chat else 'no'})")


# ---------------------------------------------------------------- 3. transcripción de candidatos
def setup_cuda_dlls():
    for d in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


_MODEL = None


def load_model():
    global _MODEL
    if _MODEL is None:
        setup_cuda_dlls()
        os.environ.setdefault("HF_HOME", str(TOOLS / "hf"))
        from faster_whisper import WhisperModel
        wc = CFG["whisper"]
        try:
            _MODEL = WhisperModel(wc["model"], device="cuda", compute_type=wc["compute_type"],
                                  download_root=str(TOOLS / "models"))
        except Exception as e:  # sin GPU utilizable: CPU (mucho más lento)
            log(f"GPU no disponible ({e}); uso CPU.")
            _MODEL = WhisperModel(wc["model"], device="cpu", compute_type="int8",
                                  download_root=str(TOOLS / "models"))
    return _MODEL


def transcribe_full(job):
    """Transcribe el VOD entero en partes de N minutos. Reanudable: guarda cada parte apenas termina."""
    fpath = job / "full_transcript.json"
    done = jload(fpath, {})
    x = load_pcm(job)
    total = len(x) / SR
    step = CFG["transcripcion"]["parte_s"]
    parts = [i for i in range(int(math.ceil(total / step))) if str(i) not in done]
    if not parts:
        return
    model, wc = load_model(), CFG["whisper"]
    for k, i in enumerate(parts, 1):
        s0 = i * step
        log(f"Transcripción completa: parte {k}/{len(parts)} ({hms(s0)}–{hms(min(total, s0 + step))})")
        a = np.asarray(x[int(s0 * SR):int(min(total, s0 + step) * SR)], dtype=np.float32) / 32768.0
        segs, _ = model.transcribe(a, language=wc["language"], beam_size=wc["beam_size"], word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=True,
                                   vad_parameters={"min_silence_duration_ms": 700})
        done[str(i)] = [{"start": round(s0 + s.start, 2), "end": round(s0 + s.end, 2), "text": s.text.strip(),
                         "words": [[round(s0 + w.start, 2), round(s0 + w.end, 2), w.word.strip()]
                                   for w in (s.words or [])]} for s in segs]
        jsave(fpath, done)


def full_segments(job):
    d = jload(job / "full_transcript.json", {})
    return sorted((s for segs in d.values() for s in segs), key=lambda s: s["start"])


def text_curve(segs, n):
    """Señal de humor desde el texto: risas transcriptas, frases gatillo y exclamaciones, por segundo."""
    laugh_re = re.compile(r"\b(?:j[aeiou]?(?:j[aeiou]){1,}j?|js(?:js)+)\b", re.I)
    trig = [norm(t) for t in CFG["gatillos"]]
    tc = CFG["transcripcion"]
    v = np.zeros(n, np.float32)
    for s in segs:
        t = norm(s["text"])
        score = tc["peso_risa"] * len(laugh_re.findall(t)) + tc["peso_gatillo"] * sum(t.count(g) for g in trig) \
            + tc["peso_exclamacion"] * s["text"].count("!") / 2
        if score:
            a, b = int(s["start"]), max(int(s["start"]) + 1, int(s["end"]))
            v[a:min(n, b)] += score / (b - a)
    return np.convolve(v, np.ones(20, np.float32), "same")  # densidad en 20 s


def transcribe_candidates(job):
    data = jload(job / "candidates.json")
    tpath = job / "transcripts.json"
    done = jload(tpath, {})
    if (job / "full_transcript.json").exists():  # ya está todo transcripto: solo recortar
        segs = full_segments(job)
        for c in data["candidates"]:
            done[c["id"]] = [s for s in segs if s["end"] > c["start"] and s["start"] < c["end"]]
        jsave(tpath, done)
    todo = [c for c in data["candidates"] if c["id"] not in done]
    if todo:
        model, wc = load_model(), CFG["whisper"]
        x = load_pcm(job)
        for k, c in enumerate(todo, 1):
            log(f"Transcribiendo {c['id']} ({k}/{len(todo)}) {hms(c['start'])}–{hms(c['end'])}")
            a = np.asarray(x[int(c["start"] * SR):int(c["end"] * SR)], dtype=np.float32) / 32768.0
            segs, _ = model.transcribe(a, language=wc["language"], beam_size=wc["beam_size"],
                                       word_timestamps=True, condition_on_previous_text=False)
            out = []
            for s in segs:
                out.append({"start": round(c["start"] + s.start, 2), "end": round(c["start"] + s.end, 2),
                            "text": s.text.strip(),
                            "words": [[round(c["start"] + w.start, 2), round(c["start"] + w.end, 2), w.word.strip()]
                                      for w in (s.words or [])]})
            done[c["id"]] = out
            jsave(tpath, done)  # guardado incremental: si se corta, retoma desde acá
    write_review(job)


def write_review(job):
    meta = jload(job / "meta.json")
    data = jload(job / "candidates.json")
    tr = jload(job / "transcripts.json", {})
    trig = [norm(t) for t in CFG["gatillos"]]
    bad = [norm(t) for t in CFG["descartar_si_menciona"]]
    w = CFG["pesos_prefiltro"]["gatillos"]
    for c in data["candidates"]:
        txt = norm(" ".join(s["text"] for s in tr.get(c["id"], [])))
        c["gatillos"] = [t for t in trig if t in txt]
        c["alerta_casino"] = [t for t in bad if re.search(r"\b" + re.escape(t), txt)]
        c["score_prefiltro"] = round(c["pre_score"] + w * 10 * len(c["gatillos"]))
    jsave(job / "candidates.json", data)
    lines = [f"# Revisión: {meta['title']}", f"Streamer: {meta['uploader']} · {meta['platform']} · "
             f"chat: {'sí' if data['has_chat'] else 'no'} · {len(data['candidates'])} candidatos", ""]
    for c in sorted(data["candidates"], key=lambda c: -c["score_prefiltro"]):
        sig = f"audio {c['audio_z']}σ" + (f", texto {c['texto_z']}σ" if "texto_z" in c else "")
        if data["has_chat"]:
            sig += f", chat {c['chat_z']}σ ({c['msgs_5s']} msj/5s), emotes/risas {c['emotes_5s']}"
        extra = (f" · gatillos: {', '.join(c['gatillos'])}" if c["gatillos"] else "") + \
                (f" · ⚠️ casino: {', '.join(c['alerta_casino'])}" if c["alerta_casino"] else "")
        lines.append(f"## {c['id']}  {hms(c['start'])} → {hms(c['end'])}  pico {hms(c['peak'])}  "
                     f"(prefiltro {c['score_prefiltro']}: {sig}{extra})")
        for s in tr.get(c["id"], []):
            lines.append(f"[{s['start']:.1f}] {s['text']}")
        lines.append("")
    (job / "review.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"Listo para revisar: {job / 'review.md'}")


def prepare(sources):
    for src in sources:
        job = ingest(src)
        get_audio(job)
        get_chat(job)
        if CFG["transcripcion"]["completa"]:
            transcribe_full(job)
        find_candidates(job)
        transcribe_candidates(job)
        print(f"JOB={job}")


def inbox_sources():
    INBOX.mkdir(parents=True, exist_ok=True)
    done_f = INBOX / "procesados.txt"
    done = set(done_f.read_text(encoding="utf-8").split("\n")) if done_f.exists() else set()
    srcs = []
    lf = INBOX / "links.txt"
    if lf.exists():
        srcs += [l.strip() for l in lf.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    srcs += [str(p) for p in INBOX.iterdir() if p.suffix.lower() in (".mp4", ".mkv", ".mov", ".ts", ".flv")]
    srcs = [s for s in srcs if s not in done]
    return srcs, done_f


# ---------------------------------------------------------------- 4. corte
def words_of(job):
    # transcripción completa si existe (clips elegidos fuera de los 30 candidatos); si no, la de los candidatos
    tr = jload(job / "full_transcript.json", {}) or jload(job / "transcripts.json", {})
    ws = [w for segs in tr.values() for s in segs for w in s["words"]]
    return sorted({(w[0], w[1], w[2]) for w in ws})


def snap(sel, words, dmin, dmax):
    s, e = float(sel["start"]), float(sel["end"])
    first = next((w for w in words if w[0] >= s - 0.3), None)
    if first and first[0] - s < 1.5:
        s = max(0.0, first[0] - 0.25)  # arranca justo antes de la primera palabra (sin aire muerto)
    inside = [w for w in words if s <= w[1] <= e + 0.3]
    if inside:
        e = max(e, inside[-1][1] + 0.3)  # nunca corta una palabra a la mitad
    if e - s < dmin:
        e = s + dmin
    if e - s > dmax:
        e = s + dmax
    return round(s, 2), round(e, 2)


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path, words):
    out, chunk, n = [], [], 1
    for w in words + [None]:
        if w is not None:
            chunk.append(w)
        if chunk and (w is None or len(chunk) >= 5 or chunk[-1][1] - chunk[0][0] > 2.5):
            out.append(f"{n}\n{srt_time(chunk[0][0])} --> {srt_time(chunk[-1][1])}\n"
                       f"{' '.join(c[2] for c in chunk)}\n")
            n, chunk = n + 1, []
    Path(path).write_text("\n".join(out), encoding="utf-8")


def stream_urls(src):
    out = subprocess.run(YTDLP + ["-g", "-f", "bv*[height<=2160]+ba/b", "-S", "res,fps,tbr", src],  # la versión de más bitrate (YouTube: 15-30 Mbps en vez de 2,7)
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [u for u in out.splitlines() if u.strip()]


def cut_video(meta, s, e, out, urls):
    # fuente 1440p/4K (YouTube) -> 1080p con lanczos: más nítido que el 1080p de YouTube y el editor sigue recibiendo 1080p
    enc = ["-vf", "scale=-2:'min(1080,ih)':flags=lanczos", "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart"]
    if meta["platform"] == "local":
        inputs, maps = ["-ss", s, "-i", meta["source"]], ["-map", "0:v:0", "-map", "0:a:0?"]
    else:
        inputs = []
        for u in urls:
            inputs += ["-ss", s, "-i", u]
        maps = ["-map", "0:v:0", "-map", "1:a:0"] if len(urls) > 1 else ["-map", "0:v:0", "-map", "0:a:0?"]
    run([FFMPEG, "-y", "-loglevel", "error", *inputs, "-t", round(e - s, 2), *maps, *enc, out])


def cut(job_name, top=None, min_score=None, sel="selections.json", desde=1):
    job = inside_root(JOBS / job_name if not Path(job_name).is_absolute() else job_name)
    meta = jload(job / "meta.json")
    sels = jload(job / sel)  # otra tanda del mismo stream: --sel selections_2.json --desde 5 (no pisa los clips ya hechos)
    if not sels:
        sys.exit(f"Falta {job / 'selections.json'} (lo escribe Claude después de leer review.md)")
    cfg = CFG["seleccion"]
    top = top or cfg["top_n"]
    min_score = cfg["puntaje_min"] if min_score is None else min_score
    clips = sorted([c for c in sels["clips"] if c.get("score", 0) >= min_score], key=lambda c: -c["score"])[:top]
    if not clips:
        sys.exit("Ningún clip supera el puntaje mínimo.")
    words = words_of(job)
    outdir = RAW / job.name
    outdir.mkdir(parents=True, exist_ok=True)
    urls = [] if meta["platform"] == "local" else stream_urls(meta["source"])
    results = []
    for i, c in enumerate(clips, desde):
        s, e = snap(c, words, cfg["dur_min_s"], cfg["dur_max_s"])
        name = f"{i:02d}_{slugify(c.get('titulo') or c.get('hook_text') or c['id'])[:40]}"
        mp4 = outdir / f"{name}.mp4"
        log(f"Cortando {name}  {hms(s)}–{hms(e)}  ({e - s:.1f}s, puntaje {c['score']})")
        try:
            cut_video(meta, s, e, mp4, urls)
        except subprocess.CalledProcessError:
            log("Falló el corte; renuevo las URLs y reintento una vez…")
            urls = [] if meta["platform"] == "local" else stream_urls(meta["source"])
            cut_video(meta, s, e, mp4, urls)
        rel = [[round(w[0] - s, 2), round(w[1] - s, 2), w[2]] for w in words if s <= w[0] and w[1] <= e]
        write_srt(outdir / f"{name}.srt", rel)
        info = {**c, "start": s, "end": e, "duracion": round(e - s, 1), "archivo": mp4.name,
                "streamer": meta["uploader"], "plataforma": meta["platform"], "fuente": meta["source"],
                "words": rel}
        jsave(outdir / f"{name}.json", info)
        results.append(info)
    previos = (jload(outdir / "results.json") or []) if desde > 1 else []
    previos = [r for r in previos if r.get("archivo") not in {x["archivo"] for x in results}]
    jsave(outdir / "results.json", previos + [{k: v for k, v in r.items() if k != "words"} for r in results])
    table = ["| # | Archivo | Inicio | Fin | Dur | Puntaje | Desglose | Tipo | Hook |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results, desde):
        b = r.get("breakdown", {})
        table.append(f"| {i} | {r['archivo']} | {hms(r['start'])} | {hms(r['end'])} | {r['duracion']}s | "
                     f"{r['score']} | {'/'.join(str(b.get(k, '-')) for k in CFG['puntaje_pesos'])} | "
                     f"{r.get('tipo', '')} | {r.get('hook_text', '')} |")
    (outdir / "results.md").write_text("\n".join(table), encoding="utf-8")
    add_to_calendar(results, job.name)
    print("\n".join(table))
    print(f"\nClips en: {outdir}")


# ---------------------------------------------------------------- 5. calendario
CAL_COLS = ["fecha", "hora", "streamer", "job", "clip", "puntaje", "tipo", "hook", "caption", "estado"]


def add_to_calendar(results, job_name):
    CAL.mkdir(parents=True, exist_ok=True)
    path = CAL / "calendario.csv"
    rows = []
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    known = {(r["job"], r["clip"]) for r in rows}
    taken = {(r["fecha"], r["hora"]) for r in rows}
    by_day = {}
    for r in rows:
        by_day.setdefault(r["fecha"], []).append(r["streamer"])
    cc = CFG["calendario"]
    day = max(dt.date.today() + dt.timedelta(days=1), dt.date.fromisoformat(cc["inicio"]))
    switch = dt.date.fromisoformat(cc["cambio_2_por_dia"])
    pending = [r for r in results if (job_name, r["archivo"]) not in known]
    guard = 0
    while pending and guard < 3650:
        hours = cc["horas_2_por_dia"] if day >= switch else cc["horas_1_por_dia"]
        for h in hours:
            if not pending or (day.isoformat(), h) in taken:
                continue
            # evita el mismo streamer dos veces el mismo día si hay alternativa
            r = next((p for p in pending if p["streamer"] not in by_day.get(day.isoformat(), [])), pending[0])
            pending.remove(r)
            rows.append({"fecha": day.isoformat(), "hora": h, "streamer": r["streamer"], "job": job_name,
                         "clip": r["archivo"], "puntaje": r["score"], "tipo": r.get("tipo", ""),
                         "hook": r.get("hook_text", ""), "caption": r.get("caption", "").replace("\n", " / "),
                         "estado": "a editar"})
            taken.add((day.isoformat(), h))
            by_day.setdefault(day.isoformat(), []).append(r["streamer"])
        day += dt.timedelta(days=1)
        guard += 1
    rows.sort(key=lambda r: (r["fecha"], r["hora"]))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: Excel abre bien las tildes
        wr = csv.DictWriter(f, fieldnames=CAL_COLS)
        wr.writeheader()
        wr.writerows(rows)
    log(f"Calendario actualizado: {path}")


# ---------------------------------------------------------------- CLI
def status():
    for job in sorted(JOBS.glob("*")):
        steps = [n for n, f in (("audio", "audio.pcm"), ("chat", "chat_norm.json"), ("candidatos", "candidates.json"),
                                ("review", "review.md"), ("selección", "selections.json")) if (job / f).exists()]
        cut_done = (RAW / job.name / "results.json").exists()
        print(f"{job.name:45s} {', '.join(steps)}{', cortado' if cut_done else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("sources", nargs="*")
    p.add_argument("--inbox", action="store_true")
    c = sub.add_parser("cut")
    c.add_argument("job")
    c.add_argument("--top", type=int)
    c.add_argument("--min-score", type=int)
    c.add_argument("--sel", default="selections.json", help="archivo de selecciones (otra tanda: selections_2.json)")
    c.add_argument("--desde", type=int, default=1, help="número del primer clip (para no pisar una tanda anterior)")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "prepare":
        srcs = list(a.sources)
        done_f = None
        if a.inbox:
            extra, done_f = inbox_sources()
            srcs += extra
        if not srcs:
            sys.exit("No hay nada para procesar.")
        for s in srcs:
            prepare([s])
            if done_f:
                with open(done_f, "a", encoding="utf-8") as f:
                    f.write(s + "\n")
    elif a.cmd == "cut":
        cut(a.job, a.top, a.min_score, a.sel, a.desde)
    else:
        status()


if __name__ == "__main__":
    main()
