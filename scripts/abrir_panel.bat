@echo off
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" -X utf8 -m consultor ventana --config config.toml
