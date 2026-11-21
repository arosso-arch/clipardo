@echo off
chcp 65001 >nul
title Clipardo - edicion automatica
call "%~dp0entorno.bat"
"%CLIPARDO_PY%" -I "%CLIPARDO_SKILLS%\ig-editor\clipardo.py"
echo.
pause
