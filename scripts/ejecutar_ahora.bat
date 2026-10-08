@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -X utf8 -m consultor run --config config.toml --abrir
echo.
if %ERRORLEVEL% EQU 0 (echo Listo. El reporte se abrio en Excel.) else (echo La consulta no se ejecuto o termino con avisos. Lea el mensaje de arriba.)
echo.
pause
