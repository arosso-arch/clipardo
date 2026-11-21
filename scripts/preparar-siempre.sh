# Prepara (baja + transcribe) lo nuevo del inbox una y otra vez: lo que el vigilante o Claude suman mientras corre
# entra en la vuelta siguiente. Nunca corre dos a la vez (la GTX 1650 no aguanta dos Whisper).
. "$(dirname "$0")/entorno.sh"
corriendo() { powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ? { \$_.CommandLine -match 'clipfinder.py.+prepare' }).Count" | tr -d '\r'; }
while true; do
  while [ "$(corriendo)" != "0" ]; do sleep 60; done
  echo "=== vuelta $(date '+%d/%m %H:%M')" >> tmp/prepare-gta6.log
  "$PY" -I "$CF"/clipfinder.py prepare --inbox >> tmp/prepare-gta6.log 2>&1
  sleep 600
done
