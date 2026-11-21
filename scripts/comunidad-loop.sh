# cada 30 min: trae los clips de la comunidad de las últimas 3 h y prepara los 6 mejores nuevos
. "$(dirname "$0")/entorno.sh"
while true; do
  "$PY" -I "$CF"/comunidad.py --horas 3 --preparar --top 6 >> tmp/comunidad.log 2>&1
  sleep 1800
done
