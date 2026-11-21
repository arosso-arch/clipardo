# Aprueba solo (al calendario) cada job que la cola de edición dejó con revision=ok. Aprobación delegada por el usuario ("seguí subiendo").
. "$(dirname "$0")/entorno.sh"
touch tmp/aprobados-auto.txt tmp/edicion-estado.txt
while true; do
  for j in $(grep 'revision=ok' tmp/edicion-estado.txt | awk '{print $2}' | sort -u | grep -vxF -f tmp/aprobados-auto.txt); do
    if "$PY" -I publicador/aprobar_y_ordenar.py "$j" >> tmp/auto-aprobar.log 2>&1; then
      echo "$j" >> tmp/aprobados-auto.txt; echo "$(date '+%d/%m %H:%M') APROBADO $j" | tee -a tmp/auto-aprobar.log
    fi
  done
  sleep 120
done
