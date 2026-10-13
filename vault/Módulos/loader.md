# loader

**Qué hace:** entrega la lista de radicados a consultar.

**Contrato:** `cargar() -> list[Radicado]`, donde `Radicado` tiene radicado, empresa, despacho y calidad. `crear_fuente(cfg)` elige la implementación según `tipo` en `config.toml`.

**Hoy:** `FuenteExcel` lee el Excel de seguimiento en solo lectura (R9). Los nombres de las columnas son configurables.
- Quita espacios, guiones y puntos del radicado.
- **No descarta radicados inválidos**: el [[fetcher]] los marca NO VERIFICADO con el motivo, para que no se pierdan en silencio (R3).
- Une las empresas de un radicado repetido.
- Filtro de estado por **prefijo**, sin distinguir mayúsculas: `ACTIVO` incluye `ACTIVO -COBRO COSTAS`.

**Mañana:** otra fuente (CSV, SQL Server, SharePoint) es un archivo más que cumple el mismo contrato.

## Lista real
La hoja `GENERAL` trae `RADICADO`, `ESTADO` y `DESPACHO`, pero no empresa. Hoy el reporte deja la empresa vacía. De 77 filas, 68 radicados son válidos (65 únicos) y 8 tienen un formato inválido, pendientes de depurar con la Gerencia.

## Cambios tras la auditoría (2026-10-13)
- `_radicados` extrae los radicados de una celda: primero el texto crudo y luego sin espacios, guiones ni puntos. Una racha de dígitos múltiplo de 23 se corta cada 23. Las rachas sobrantes de 18 dígitos o más se conservan tal cual para que salgan NO VERIFICADO. Una celda numérica (float) se marca "numérico: …".
- `filas_sin_radicado` cuenta las filas con datos pero sin radicado. Con filtro de estado configurado, la columna de estado no cuenta como dato. [[main]] avisa de esas filas.

**Depende de:** openpyxl. Reglas R7 y R9 en [[Reglas de negocio]]. Usado por [[main]].
