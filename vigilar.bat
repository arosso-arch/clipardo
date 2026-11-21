@echo off
chcp 65001 >nul
title Clipardo - vigilando streams
call "%~dp0entorno.bat"
echo Vigilando streams (los canales de clip-finder\vigilar.py). Cuando uno termina, queda anotado en %CLIPARDO_HOME%\inbox\encontrados.txt
echo Dejala abierta. Despues pedile a Claude "mostrame los streams encontrados" y elegis cuales clipear.
:loop
"%CLIPARDO_PY%" -I "%CLIPARDO_SKILLS%\clip-finder\vigilar.py" --cada 600
echo.
echo (sigo vigilando a los demás...)
goto loop
