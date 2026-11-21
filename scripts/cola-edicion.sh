# Cola de edición con autocorrección: render --capcut -> Remotion -> revisar.py --arreglar (corrige solo lo que puede)
. "$(dirname "$0")/entorno.sh"
touch tmp/cola-edicion.txt tmp/cola-hecha.txt
while true; do
  j=$(grep -vxF -f tmp/cola-hecha.txt tmp/cola-edicion.txt | head -1)
  if [ -z "$j" ]; then sleep 30; continue; fi
  log="tmp/edicion-$j.log"
  "$PY" -I "$E"/igeditor.py render "$j" --capcut > "$log" 2>&1 && "$PY" -I "$E"/remotion_final.py "$j" >> "$log" 2>&1
  ex=$?
  "$PY" -I "$E"/revisar.py "$j" --arreglar >> "$log" 2>&1; rv=$?
  echo "EDITADO $j exit=$ex revision=$([ $rv = 0 ] && echo ok || echo 'quedan problemas')" | tee -a tmp/edicion-estado.txt
  echo "$j" >> tmp/cola-hecha.txt
done
