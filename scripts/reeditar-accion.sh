# 2026-11-21: re-edita con el estilo de acción (sin subtítulos + pulsos) los Reels programados que son de acción
. "$(dirname "$0")/entorno.sh"
"$PY" -I - <<'PYEOF' > tmp/reeditar-accion.txt
import csv, json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["CLIPARDO_SKILLS"] + "/ig-editor"); sys.argv = ["x"]
import igeditor
for x in csv.DictReader(open(os.environ["CLIPARDO_HOME"] + "/calendario/publicacion.csv", encoding="utf-8-sig")):
    if x["estado"] not in ("programado", "pendiente de ok"): continue
    v = Path(x["video"]); job = v.parent.name; raw = Path(os.environ["CLIPARDO_HOME"]) / "clips" / "raw" / job / v.name
    cj = v.parent / "capcut" / f"{v.stem}_capcut.json"
    if not raw.exists() or not cj.exists(): continue
    c = json.loads(cj.read_text(encoding="utf-8"))
    if c.get("tipo") != "gaming" or "accion" in c or not c.get("subtitulos"): continue
    m = igeditor.movimiento(raw)
    if m >= 0.45: print(job, v.stem[:2], round(m, 2), flush=True)
PYEOF
while read job n m; do
  echo "re-edito $job $n ($m)"
  "$PY" -I "$E"/igeditor.py render "$job" --capcut --solo "$n" > "tmp/reed-$job-$n.log" 2>&1 && "$PY" -I "$E"/remotion_final.py "$job" --solo "$n" >> "tmp/reed-$job-$n.log" 2>&1
  "$PY" -I "$E"/revisar.py "$job" --arreglar >> "tmp/reed-$job-$n.log" 2>&1
done < tmp/reeditar-accion.txt
echo "FIN $(wc -l < tmp/reeditar-accion.txt) re-editados"
