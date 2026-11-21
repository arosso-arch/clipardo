@echo off
chcp 65001 >nul
title Clipardo - arranque
call "%~dp0entorno.bat"
echo Arrancando Clipardo (cada cosa en su ventana; NO cerrarlas):
echo   1. Publicador   - sube un Reel por hora (10 a 23) en cada cuenta
echo   2. Vigilante    - avisa cuando termina un stream
echo   3. Edicion      - edita y revisa los clips cortados
echo   4. Comunidad    - trae los clips mas vistos de Kick/Twitch cada 30 min
echo   5. Aprobar      - pasa al calendario lo que paso la revision
echo   6. Calendario   - regenera calendario.html cada 2 min
echo   7. Preparar     - transcribe los streams pendientes del inbox
echo.
start "Clipardo - publicador" cmd /k "%CLIPARDO_HOME%\publicador\publicar.bat"
start "Clipardo - vigilante" cmd /k "%CLIPARDO_HOME%\vigilar.bat"
start "Clipardo - edicion" "%GIT_BASH%" -c "bash '%CLIPARDO_HOME%/scripts/cola-edicion.sh'"
start "Clipardo - comunidad" "%GIT_BASH%" -c "bash '%CLIPARDO_HOME%/scripts/comunidad-loop.sh'"
start "Clipardo - aprobar" "%GIT_BASH%" -c "bash '%CLIPARDO_HOME%/scripts/auto-aprobar.sh'"
start "Clipardo - calendario" /min "%CLIPARDO_PY%" -I "%CLIPARDO_HOME%\publicador\ver_calendario.py" --loop
start "Clipardo - preparar" "%GIT_BASH%" -c "bash '%CLIPARDO_HOME%/scripts/preparar-siempre.sh'"
echo Calendario: abri %CLIPARDO_HOME%\calendario.html
echo Listo. Despues abri una sesion de Claude y pedile: "clipea los streams nuevos".
timeout /t 15
