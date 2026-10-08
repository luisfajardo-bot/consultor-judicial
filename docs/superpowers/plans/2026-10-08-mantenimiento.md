# Mantenimiento: archivar reportes y respaldar la base de datos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. TDD: cada sección empieza con una prueba que falla.

Contexto: `2026-10-08-pantalla-minima.md`. Comandos con `.venv\Scripts\python -m pytest`. Cada commit termina con `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Sin rayas largas. No hacer peticiones al portal real en las pruebas.

**Política decidida (valores por defecto):**
- Los reportes Excel con más de 14 días se **mueven** a `reportes\archivo\AAAA-MM\`. No se borran.
- El borrado del archivo existe pero está **apagado** (`borrar_archivo_tras_dias = 0`). Lo decide la Gerencia Jurídica.
- La base de datos se respalda cada 7 días con la función de respaldo de SQLite y se conservan las últimas 8 copias.

**Por qué es seguro archivar:** los reportes de ciclos anteriores ya fueron leídos en el arranque de cada ciclo (sus decisiones están en SQLite) y las alertas pendientes reaparecen en cada reporte nuevo. Aun así, nunca se archiva el reporte más reciente, y un archivo que no se puede mover (abierto en Excel) se salta y se reintenta en el siguiente ciclo.

Todo corre **al final de cada ciclo**, dentro de `ejecutar_ciclo`, sin tarea programada extra. Un fallo del mantenimiento **nunca** cambia el código de salida ni tumba el ciclo: se avisa y se sigue.

---

## A. Archivar y, opcionalmente, borrar reportes

**Archivos:** `consultor/mantenimiento.py` (nuevo), `tests/test_mantenimiento.py` (nuevo)

Convención del nombre: `reporte_ciclo_NNNN_AAAA-MM-DD.xlsx`. La fecha y el número se leen del nombre; si el nombre no cuadra con el patrón, el archivo se ignora (no se toca).

Funciones:
```python
def archivar_reportes(carpeta, hoy: date, dias: int = 14) -> list[Path]
```
Mueve a `carpeta/archivo/AAAA-MM/` (AAAA-MM de la fecha del nombre) los `reporte_ciclo_*.xlsx` de la carpeta (no recursivo) cuya fecha sea anterior a `hoy - dias`, **excepto el de mayor número de ciclo**. Ignora los que empiezan por `~$`. Si el destino ya existe, no sobrescribe: omite ese archivo. Si mover lanza `OSError` (por ejemplo `PermissionError` por Excel abierto), lo omite y sigue. Crea las carpetas necesarias. Devuelve las rutas de destino de lo movido. `dias <= 0` desactiva (devuelve `[]`).

```python
def borrar_archivo_antiguo(carpeta, hoy: date, dias: int) -> list[Path]
```
Borra de `carpeta/archivo/` (recursivo) los `reporte_ciclo_*.xlsx` cuya fecha del nombre sea anterior a `hoy - dias`, y elimina las carpetas `AAAA-MM` que queden vacías. `dias <= 0` no hace nada (devuelve `[]`). Un `OSError` en un archivo lo omite. Devuelve las rutas borradas.

- [ ] **Pruebas que fallan** (`tests/test_mantenimiento.py`; ayudante `crear(carpeta, nombre)` que escribe un archivo de bytes):
  1. Con reportes de hace 30, 20 y 3 días y `dias=14`, se archivan los de 30 y 20 en `archivo/AAAA-MM/` y el de 3 se queda.
  2. El reporte de mayor número **no se archiva aunque tenga 60 días** (único reporte viejo).
  3. Un nombre que no cuadra (`notas.xlsx`, `reporte_algo.xlsx`) y un `~$reporte_ciclo_...xlsx` no se tocan.
  4. Repetir la llamada no falla ni duplica nada (idempotente); si el destino ya existe, no se sobrescribe y el origen se queda.
  5. Con `monkeypatch` sobre `shutil.move` que lanza `PermissionError` para un archivo, la función no lanza, omite ese archivo y mueve los demás.
  6. `dias=0` no mueve nada.
  7. `borrar_archivo_antiguo` con `dias=0` no borra nada; con `dias=90` borra solo lo anterior a 90 días y quita las carpetas vacías, dejando las que aún tienen archivos.
- [ ] **Implementar** con `re.fullmatch(r"reporte_ciclo_(\d{4})_(\d{4})-(\d{2})-(\d{2})\.xlsx", nombre)` y `shutil.move`.
- [ ] Commit: `feat: archivar reportes antiguos sin borrarlos`

---

## B. Respaldo de la base de datos

**Archivos:** `consultor/mantenimiento.py`, `tests/test_mantenimiento.py`

```python
def respaldar_base(con, carpeta_respaldo, hoy: date, cada_dias: int = 7, conservar: int = 8) -> Path | None
```
- `con` es la conexión SQLite en uso. Usa `con.backup(destino)` (API de respaldo de SQLite: segura con la base abierta).
- Archivos `consultor_AAAA-MM-DD.db` en `carpeta_respaldo`. Crea la carpeta.
- Si ya existe un respaldo con fecha de hace menos de `cada_dias` días, no hace nada y devuelve `None`. `cada_dias <= 0` desactiva.
- Escribe primero a `consultor_AAAA-MM-DD.db.tmp` y al terminar lo renombra, para que un corte no deje un respaldo a medias con nombre válido.
- Verifica el respaldo abriéndolo y ejecutando `PRAGMA integrity_check`; si no devuelve `ok`, **borra el respaldo** y lanza `RuntimeError("el respaldo no pasó la verificación de integridad")`.
- Después de crear uno nuevo, conserva solo los `conservar` más recientes (por fecha del nombre) y borra el resto. `conservar <= 0` no borra ninguno.
- Devuelve la ruta del respaldo creado.

- [ ] **Pruebas que fallan:**
  1. Crea el respaldo, y su contenido tiene las mismas filas que la base origen (crear una tabla de prueba con datos).
  2. Segunda llamada con fecha de hace 3 días (relativo al respaldo) devuelve `None` y no crea otro; con 8 días crea otro.
  3. Con `conservar=3` y 5 respaldos escalonados, quedan los 3 más recientes.
  4. Funciona con la base abierta con una transacción de escritura reciente ya confirmada.
  5. Si la verificación de integridad falla (simularlo con `monkeypatch` sobre la función interna que la ejecuta), lanza `RuntimeError` y no queda ningún `.db` ni `.tmp` de ese día.
  6. No quedan archivos `.tmp` tras una ejecución normal.
- [ ] Commit: `feat: respaldo semanal verificado de la base de datos`

---

## C. Integración en el ciclo y configuración

**Archivos:** `consultor/main.py`, `config.example.toml`, `tests/test_main.py`

Configuración nueva, opcional (si falta la sección, valen estos defectos):
```toml
[mantenimiento]
archivar_reportes_tras_dias = 14
borrar_archivo_tras_dias = 0
respaldo_cada_dias = 7
respaldos_a_conservar = 8
carpeta_respaldo = ""
```
`carpeta_respaldo` vacía significa `<carpeta de la base de datos>/respaldo`.

- [ ] **Pruebas que fallan** (usar los ayudantes `preparar`, `Falso` existentes; escribir en el `config.toml` temporal la sección `[mantenimiento]` cuando haga falta):
  1. Tras un ciclo, existe `datos/respaldo/consultor_AAAA-MM-DD.db` con la fecha de hoy.
  2. Con reportes viejos preexistentes en la carpeta de reportes (nombres válidos, de hace 40 días), tras un ciclo quedan en `reportes/archivo/AAAA-MM/`, y el reporte nuevo del ciclo sigue en su sitio.
  3. Con `borrar_archivo_tras_dias = 0` (defecto) nada se borra de `archivo/`.
  4. Si `archivar_reportes` lanza una excepción (monkeypatch en `main_mod`), `ejecutar_ciclo` devuelve el mismo código (0), el ciclo ya está cerrado y queda un aviso en `avisos.log` que menciona "mantenimiento".
  5. Si `respaldar_base` lanza `RuntimeError`, igual: código 0 y aviso con "respaldo".
  6. Un ciclo rechazado (código 3, por candado o por límite) **no** ejecuta mantenimiento.
- [ ] **Implementar:** en `ejecutar_ciclo`, justo después de que `correr_ciclo` termina bien (antes de construir el `Ejecucion` de retorno) y solo si el ciclo no fue rechazado, llamar a una función `_mantenimiento(cfg, store, avisar_fn, hoy)` que:
  1. lee la sección `mantenimiento` con `.get` y los valores por defecto de arriba;
  2. llama `archivar_reportes`, y si `borrar_archivo_tras_dias > 0` también `borrar_archivo_antiguo`;
  3. llama `respaldar_base(store.con, ...)`;
  4. envuelve **cada** paso en su propio `try/except Exception`, avisando `f"Mantenimiento: no se pudo archivar los reportes ({tipo}: {e})"` o `f"Mantenimiento: falló el respaldo de la base de datos ({tipo}: {e})"` y siguiendo con el otro;
  5. avisa de forma informativa solo cuando hizo algo: `Mantenimiento: N reportes archivados.` y `Mantenimiento: respaldo creado en <ruta>.`
  `hoy` es la fecha del reloj del ciclo (`ahora()`), para que las pruebas con `Reloj` sean deterministas.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `feat: archivado y respaldo al final de cada ciclo`

---

## D. Documentación

- [ ] `README.md`: sección "Reportes antiguos y copias de seguridad" para una persona no técnica: dónde quedan los reportes archivados (`reportes\archivo\AAAA-MM\`), que el reporte para validar es siempre el más reciente (las alertas pendientes reaparecen ahí) y que decidir en un reporte archivado no se importa, dónde están las copias de la base (`datos\respaldo\`), cada cuánto se hacen y cuántas se conservan, cómo restaurar (cerrar todo, copiar el respaldo elegido sobre `datos\consultor.db`), y que el borrado de archivados existe pero está apagado hasta que la Gerencia Jurídica decida el plazo de conservación (`borrar_archivo_tras_dias`).
- [ ] Commit: `docs: reportes archivados y copias de seguridad en el README`

## Cierre

- [ ] `python -m pytest -q` completo en verde; reportar el conteo.
- [ ] Reportar: lista de commits y cualquier desviación respecto a este documento.
