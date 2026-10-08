@echo off
cd /d "%~dp0.."
if not exist reportes mkdir reportes
call .venv\Scripts\activate.bat
python -m consultor run --config config.toml >> reportes\consola.log 2>&1
exit /b %ERRORLEVEL%
