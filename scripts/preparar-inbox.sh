# prepara (baja audio + transcribe) los streams pendientes de inbox/links.txt; reanudable
. "$(dirname "$0")/entorno.sh"
echo "=== arranque $(date +%d/%m %H:%M)" >> tmp/prepare-gta6.log
"$PY" -I "$CF"/clipfinder.py prepare --inbox 2>&1 | tee -a tmp/prepare-gta6.log
