"""Rutas y cuentas de Clipardo en un solo lugar.

Todo el sistema vive en una carpeta raíz (CLIPARDO_HOME). Por defecto es la carpeta donde está este archivo
(la raíz del repo); si querés los datos en otro lado, definí la variable de entorno CLIPARDO_HOME.
Las skills de Claude se buscan en CLIPARDO_HOME\\.claude\\skills salvo que definas CLIPARDO_SKILLS.

Las cuentas de Instagram se configuran en clipardo.config.json (al lado de este archivo).

Uso desde cualquier script:
    import os, sys
    from pathlib import Path
    sys.path.insert(0, os.environ.get("CLIPARDO_HOME") or str(Path(__file__).resolve().parents[N]))
    import clipardo_rutas as R
"""
import json
import os
import shutil
from pathlib import Path

HOME = Path(os.environ.get("CLIPARDO_HOME") or Path(__file__).resolve().parent).resolve()
SKILLS = Path(os.environ.get("CLIPARDO_SKILLS") or HOME / ".claude" / "skills").resolve()

VENV_PY = HOME / ".venv" / "Scripts" / "python.exe"
YTDLP = HOME / ".venv" / "Scripts" / "yt-dlp.exe"
TOOLS = HOME / "tools"
TMP = HOME / "tmp"
INBOX = HOME / "inbox"
JOBS = HOME / "jobs"
CLIPS = HOME / "clips"
CALENDARIO = HOME / "calendario"
PUBLICACION = CALENDARIO / "publicacion.csv"
REPORTES = HOME / "reportes"
REFERENCIAS = HOME / "referencias"
COMUNIDAD = HOME / "comunidad"
REMOTION = HOME / "remotion-clipardo"


def ffmpeg_bin():
    """Carpeta bin de ffmpeg: la de tools\\ffmpeg\\<versión>\\bin si existe; si no, la del PATH."""
    for b in sorted((TOOLS / "ffmpeg").glob("*/bin")):
        return b
    exe = shutil.which("ffmpeg")
    if exe:
        return Path(exe).parent
    raise FileNotFoundError("No encuentro ffmpeg: ponelo en tools\\ffmpeg\\<version>\\bin o en el PATH")


def _cfg():
    p = HOME / "clipardo.config.json"
    if not p.exists():
        p = Path(__file__).resolve().parent / "clipardo.config.json"
    return json.loads(p.read_text(encoding="utf-8-sig"))


CONFIG = _cfg()
# clave interna ("arg", "todo") -> usuario de Instagram sin @ (ej. "micuenta.arg")
CUENTAS = {k: v["usuario"].lstrip("@") for k, v in CONFIG["cuentas"].items()}
STREAMERS_LOCALES = set(CONFIG.get("streamers_cuenta_local", []))


def usuario(clave):
    """'arg' -> 'micuenta.arg'"""
    return CUENTAS[clave]


def clave_de(usuario_o_clave):
    """'micuenta.arg' / '@micuenta.arg' / 'arg' -> 'arg'"""
    u = (usuario_o_clave or "").lstrip("@")
    if u in CUENTAS:
        return u
    for k, v in CUENTAS.items():
        if v == u:
            return k
    return u
