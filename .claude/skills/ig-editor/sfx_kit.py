"""Kit de efectos de sonido de Clipardo, generado con código (sin bajar nada, sin problemas de licencia).

Uso:  <CLIPARDO_HOME>\\.venv\\Scripts\\python.exe -I sfx_kit.py
Deja los .wav en <CLIPARDO_HOME>\\remotion-clipardo\\public\\sfx\\ (los usa la composición ClipEfectos).
Si algún sonido no convence, se puede reemplazar por uno CC0 de Openverse con el mismo nombre de archivo.
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
_sys_clip = __import__("sys"); _os_clip = __import__("os")
_sys_clip.path.insert(0, _os_clip.environ.get("CLIPARDO_HOME") or str(__import__("pathlib").Path(__file__).resolve().parents[3]))
import clipardo_rutas as R  # noqa: E402  (rutas y cuentas centralizadas, ver clipardo_rutas.py)
OUT = R.REMOTION / "public" / "sfx"
rng = np.random.default_rng(7)


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4))
    return e * np.exp(-t / r)


def lowpass(x, k):
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, "same")


def guardar(nombre, x):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    st = np.stack([x, x], 1)
    with wave.open(str(OUT / f"{nombre}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def whoosh(d=0.55):
    n = int(SR * d)
    t = np.linspace(0, 1, n)
    ruido = rng.standard_normal(n)
    # barrido: el ruido pasa de grave a agudo y vuelve, con volumen en campana
    out = np.zeros(n)
    for i in range(0, n, 512):
        seg = ruido[i:i + 512]
        k = 2 + 40 * (1 - np.sin(np.pi * t[i]) ** 2)
        out[i:i + len(seg)] = lowpass(seg, k)
    return out * np.sin(np.pi * t) ** 1.5


def golpe(d=0.7):
    n = int(SR * d)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 9) + 42  # bombo de cine: tono que cae
    tono = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.28)
    ataque = lowpass(rng.standard_normal(n), 6) * env(n, 0.001, 0.025) * 0.6
    return np.tanh(2.2 * (tono + ataque))


def pitido(d=0.5):
    n = int(SR * d)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 1000 * t)
    rampa = np.minimum(1, np.minimum(t, d - t) / 0.01)
    return x * rampa * 0.6


def clic(d=0.08):
    n = int(SR * d)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2800 * t) * 0.6 + rng.standard_normal(n) * 0.4) * env(n, 0.0005, 0.008)


def pop(d=0.14):
    n = int(SR * d)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 300
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.04)


def subida(d=0.9):
    """riser corto (tensión antes del remate)"""
    n = int(SR * d)
    t = np.linspace(0, 1, n)
    f = 300 + 1500 * t ** 2
    tono = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    ruido = lowpass(rng.standard_normal(n), 3) * 0.5
    return (tono + ruido) * t ** 2


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for nombre, fn in [("whoosh", whoosh), ("golpe", golpe), ("pitido", pitido), ("clic", clic), ("pop", pop),
                       ("subida", subida)]:
        guardar(nombre, fn())
        print("ok", nombre)
