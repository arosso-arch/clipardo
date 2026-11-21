@echo off
rem Reporte diario de Clipardo -> estado-hoy.md (se puede programar con el Programador de tareas, p. ej. a las 23:45)
call "%~dp0entorno.bat"
"%CLIPARDO_PY%" -I "%CLIPARDO_HOME%\publicador\reporte_diario.py" %* > "%CLIPARDO_HOME%\reportes\ultimo.log" 2>&1
