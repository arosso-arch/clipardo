import os, sys, time, glob, subprocess
# Hacer visibles las DLL de CUDA instaladas por pip (nvidia-cublas/cudnn)
site = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
for d in glob.glob(os.path.join(site, "*", "bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
R.TOOLS.mkdir(exist_ok=True)
ff = str(R.ffmpeg_bin() / "ffmpeg.exe")
wav = str(R.TOOLS / "test_tone.wav")
import numpy as np
def load_pcm(path):
    raw = subprocess.run([ff, "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=60", "-ar", "16000", "-ac", "1", wav], check=True)
t = time.time()
m = WhisperModel("large-v3-turbo", device="cuda", compute_type="int8_float16",
                 download_root=str(R.TOOLS / "models"))
print("modelo cargado en", round(time.time()-t, 1), "s")
t = time.time()
segs, info = m.transcribe(load_pcm(wav), language="es", word_timestamps=True, vad_filter=False)
list(segs)
print("60 s de audio transcriptos en", round(time.time()-t, 1), "s  -> GPU OK")
