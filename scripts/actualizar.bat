@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; from pathlib import Path; from consultor.bloqueo import ciclo_en_curso; from consultor.main import cargar_config; sys.exit(ciclo_en_curso(Path(cargar_config('config.toml')['salida']['base_datos']).parent))"
    if errorlevel 1 (
        echo Hay una consulta en curso. Esperar a que termine o cancelarla desde la pantalla, y volver a ejecutar esto.
        pause
        exit /b 1
    )
)
echo Buscando actualizaciones...
echo.
git pull --ff-only
if errorlevel 1 (
    echo.
    echo No se pudo actualizar. Avise a Sistemas y no modifique archivos del programa.
    pause
    exit /b 1
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo.
        echo El codigo se actualizo pero fallaron las dependencias. Avise a Sistemas.
        pause
        exit /b 1
    )
)
echo.
echo Listo. El programa esta actualizado. Sus datos y su config.toml no se tocan.
pause
