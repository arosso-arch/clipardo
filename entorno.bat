@echo off
rem Rutas de Clipardo para los .bat. CLIPARDO_HOME = esta carpeta, salvo que ya la hayas definido en Windows.
if not defined CLIPARDO_HOME set "CLIPARDO_HOME=%~dp0"
if "%CLIPARDO_HOME:~-1%"=="\" set "CLIPARDO_HOME=%CLIPARDO_HOME:~0,-1%"
if not defined CLIPARDO_SKILLS set "CLIPARDO_SKILLS=%CLIPARDO_HOME%\.claude\skills"
set "CLIPARDO_PY=%CLIPARDO_HOME%\.venv\Scripts\python.exe"
if not defined GIT_BASH set "GIT_BASH=C:\Program Files\Git\bin\bash.exe"
set PYTHONIOENCODING=utf-8
rem temporales, modelos y cache de npm dentro de la carpeta del proyecto (elegí un disco con lugar)
set "TEMP=%CLIPARDO_HOME%\tmp"
set "TMP=%CLIPARDO_HOME%\tmp"
set "HF_HOME=%CLIPARDO_HOME%\tools\hf"
set "npm_config_cache=%CLIPARDO_HOME%\tools\npm-cache"
for %%d in (tmp inbox reportes calendario) do if not exist "%CLIPARDO_HOME%\%%d" mkdir "%CLIPARDO_HOME%\%%d"
