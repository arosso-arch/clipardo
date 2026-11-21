@echo off
chcp 65001 >nul
title Clipardo - publicador
call "%~dp0..\entorno.bat"
echo Publicador de Clipardo: cada 5 minutos sube los Reels "programado" cuya hora ya llego (calendario\publicacion.csv).
echo Deja esta ventana abierta. Registro en %CLIPARDO_HOME%\publicador\publicaciones.log
:loop
"%CLIPARDO_PY%" -I "%CLIPARDO_HOME%\publicador\publicador.py" pendientes
timeout /t 300 /nobreak >nul
goto loop
