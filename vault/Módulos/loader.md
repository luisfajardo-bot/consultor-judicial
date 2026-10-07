# loader

**Qué hace:** entrega la lista de radicados a consultar.

**Contrato:** `cargar() -> list[Radicado]`, donde `Radicado` tiene radicado, empresa, despacho y calidad.

**Hoy:** lee el Excel GENERAL, solo lectura (R9). Valida que el radicado tenga 23 dígitos y marca los inválidos (R7).

**Mañana:** otra fuente (CSV, SQL Server, SharePoint, API interna) es un archivo más que cumple el mismo contrato. Una línea en `config.toml` dice cuál usar.

**Depende de:** openpyxl.

Reglas: [[Reglas de negocio]] R7 y R9. Usado por [[main]].
