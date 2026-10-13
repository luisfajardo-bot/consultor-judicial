@echo off
cd /d "%~dp0.."
if not exist reportes mkdir reportes
if not exist ".venv\Scripts\pythonw.exe" (
    echo %date% %time% Falta .venv\Scripts\pythonw.exe: no se ejecuto el ciclo. >> reportes\consola.log
    exit /b 2
)
start "" /wait ".venv\Scripts\pythonw.exe" -X utf8 -m consultor run --config config.toml
exit /b %ERRORLEVEL%
