# Consultor Judicial

Consulta los radicados de la lista en la API de la Rama Judicial, detecta actuaciones nuevas y deja un Excel de alertas para que Alisson Rengifo las valide. No decide nada jurídico y no escribe en el cuadro oficial.

## Instalación

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy config.example.toml config.toml
```

Edita `config.toml`: ruta del Excel con los radicados y nombres de sus columnas.

## Uso

```
python -m consultor run
python -m consultor run --solo-radicado 11001400307720210114700
```

Códigos de salida: 0 ciclo completo, 1 detenido por fuente no disponible, 2 error inesperado.

## Validación

Abrir `reportes\reporte_ciclo_NNNN_AAAA-MM-DD.xlsx`, hoja Alertas. En cada fila con ID de alerta elegir en la columna Decisión: Confirmada o Descartada (y escribir el nombre en Validó). Guardar y cerrar el archivo. El ciclo siguiente lee la decisión.

## Programación (la configura Sistemas)

```
schtasks /Create /TN "ConsultorJudicial" /TR "C:\consultor_judicial\scripts\ejecutar_ciclo.bat" /SC WEEKLY /D MON,WED,FRI /ST 06:30 /RU DOMINIO\cuenta_servicio /RP *
```

La cuenta debe tener permiso de lectura sobre el Excel de radicados y de escritura sobre `datos\` y `reportes\`.

## Ejecutar a mano

Doble clic en `scripts\ejecutar_ahora.bat`. Se ve una barra de avance con el radicado que se está consultando; no cierres la ventana. Al terminar, el reporte se abre en Excel.

- Si ya hay una consulta en curso (por ejemplo la tarea programada), el programa lo dice, muestra su avance y no hace nada: el candado impide dos ciclos a la vez.
- Si la última consulta terminó hace menos de 30 minutos, el programa lo dice y no hace nada, para no repetir consultas al portal. El límite se cambia en `config.toml`, sección `[ejecucion]`, con `min_minutos_entre_ciclos` (0 lo desactiva). Quien administra la herramienta puede saltarlo con `--forzar`.
- Código de salida 3: no se ejecutó por candado o por el límite. Los demás: 0 completo, 1 detenido o con fallas, 2 error inesperado.

## Limitaciones conocidas

- Una decisión corregida en el Excel se ignora: solo cuenta la primera decisión registrada para cada alerta.

## Pruebas

```
python -m pytest
```
