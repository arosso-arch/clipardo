# Rutas de Clipardo para los .sh (Git Bash). Se carga con: . "$(dirname "$0")/entorno.sh"
AQUI_SH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLIPARDO_HOME="${CLIPARDO_HOME:-$(cd "$AQUI_SH/.." && (pwd -W 2>/dev/null || pwd))}"
export CLIPARDO_SKILLS="${CLIPARDO_SKILLS:-$CLIPARDO_HOME/.claude/skills}"
PY="$CLIPARDO_HOME/.venv/Scripts/python.exe"
E="$CLIPARDO_SKILLS/ig-editor"
CF="$CLIPARDO_SKILLS/clip-finder"
export TEMP="$CLIPARDO_HOME/tmp" TMP="$CLIPARDO_HOME/tmp" HF_HOME="$CLIPARDO_HOME/tools/hf" PYTHONIOENCODING=utf-8
mkdir -p "$CLIPARDO_HOME/tmp"
cd "$CLIPARDO_HOME" || exit 1
