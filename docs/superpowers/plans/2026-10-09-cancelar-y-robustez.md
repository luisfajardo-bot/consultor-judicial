# Cancelar un ciclo, estado confiable y ejecución oculta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. TDD: cada sección empieza con una prueba que falla.

Contexto: el 2026-10-09 la tarea de las 9:00 se cortó a los 20 segundos (código `0xC000013A`: cerraron la ventana de la consola). Dejó un `estado.txt` viejo y la ventana lo mostró como un ciclo en marcha durante 15 minutos. Comandos con `.venv\Scripts\python -m pytest`. Cada commit termina con `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Sin rayas largas. No hacer peticiones al portal real en las pruebas.

**Principio:** un ciclo está en curso si y solo si alguien tiene el candado. Un archivo `estado.txt` sin candado es un resto viejo y se ignora.

---

## A. El candado se puede sondear y tolera un choque breve

**Archivos:** `consultor/bloqueo.py`, `tests/test_bloqueo.py`

- [ ] **Pruebas que fallan:**
```python
def test_ciclo_en_curso_es_falso_si_nadie_tiene_el_candado(tmp_path):
    assert ciclo_en_curso(tmp_path) is False


def test_ciclo_en_curso_es_verdadero_mientras_alguien_lo_tiene(tmp_path):
    with Bloqueo(tmp_path):
        assert ciclo_en_curso(tmp_path) is True
    assert ciclo_en_curso(tmp_path) is False


def test_sondear_borra_un_estado_viejo_pero_no_toca_uno_vivo(tmp_path):
    (tmp_path / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    assert ciclo_en_curso(tmp_path) is False
    assert not (tmp_path / "estado.txt").exists()
    with Bloqueo(tmp_path) as b:
        b.publicar("09:00 | 5 de 41")
        assert ciclo_en_curso(tmp_path) is True
        assert (tmp_path / "estado.txt").read_text(encoding="utf-8") == "09:00 | 5 de 41"


def test_un_choque_breve_con_el_sondeo_no_rechaza_al_ciclo(tmp_path, monkeypatch):
    # Un sondeo de la ventana puede tener el candado unos milisegundos justo cuando arranca un ciclo.
    import consultor.bloqueo as m

    intentos = []
    original = m._bloquear

    def inestable(fd):
        intentos.append(1)
        if len(intentos) < 3:
            raise OSError("ocupado un instante")
        return original(fd)

    monkeypatch.setattr(m, "_bloquear", inestable)
    with Bloqueo(tmp_path):
        pass
    assert len(intentos) == 3
```
Y los tests existentes de rechazo siguen pasando (un candado realmente ocupado agota los reintentos y lanza `CicloEnCurso`).
- [ ] **Implementar:** en `Bloqueo.__enter__`, hasta 4 intentos separados por 0,1 s (`time.sleep`) antes de lanzar `CicloEnCurso`. Función de módulo:
```python
def ciclo_en_curso(carpeta) -> bool:
    """Verdadero si otro proceso tiene el candado. Si está libre, borra un estado.txt viejo."""
    try:
        with Bloqueo(carpeta):
            return False
    except CicloEnCurso:
        return True
```
Importante: `ciclo_en_curso` NO debe esperar los 0,3 s completos de reintentos cuando el candado está realmente ocupado; añade a `Bloqueo.__init__` un parámetro `reintentos=4` y úsalo con `Bloqueo(carpeta, reintentos=1)` aquí, y comprueba que la prueba de choque breve usa el valor por defecto.
- [ ] Commit: `feat: sondear si hay un ciclo corriendo de verdad con el candado`

---

## B. El panel solo cree en un avance con candado

**Archivos:** `consultor/panel.py`, `tests/test_panel.py`

- [ ] **Cambiar y añadir pruebas.** Las pruebas existentes de `leer_avance` que escriben `estado.txt` a mano deben pasar a sostener el candado real (`with Bloqueo(tmp_path) as b: b.publicar(...)`). Añadir:
```python
def test_un_estado_sin_candado_es_un_resto_viejo_y_se_ignora(tmp_path):
    (tmp_path / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    assert leer_avance(tmp_path) is None
    assert not (tmp_path / "estado.txt").exists()


def test_solicitar_cancelacion_solo_actua_si_hay_un_ciclo_corriendo(tmp_path):
    assert solicitar_cancelacion(tmp_path) is False
    assert not (tmp_path / "cancelar.txt").exists()
    with Bloqueo(tmp_path):
        assert solicitar_cancelacion(tmp_path) is True
        assert (tmp_path / "cancelar.txt").exists()
```
- [ ] **Implementar:** `leer_avance` llama primero a `ciclo_en_curso(carpeta_datos)`; si es falso devuelve `None`. Función nueva `solicitar_cancelacion(carpeta_datos) -> bool` que, si `ciclo_en_curso`, crea `cancelar.txt` (contenido: la hora) y devuelve `True`; si no, `False`.
- [ ] Commit: `fix: el panel ignora un avance sin candado y puede pedir cancelar`

---

## C. Cancelar un ciclo en marcha

Cooperativo: la ventana (o cualquier proceso) crea `cancelar.txt` en la carpeta de datos y el ciclo lo detecta **entre radicados y durante las esperas largas**. Lo ya consultado se conserva; el ciclo queda reanudable.

**Archivos:** `consultor/fetcher.py`, `consultor/main.py`, `consultor/store.py`, `tests/test_fetcher.py`, `tests/test_main.py`, `tests/test_store.py`

**Comportamiento:**
- `CicloCancelado` (excepción nueva en `fetcher.py`).
- `Fetcher.__init__` gana `cancelado=None` (invocable que devuelve bool). Las esperas (`pausar`, pausa entre peticiones, esperas de reintento y de bloqueo) pasan por un método `_dormir(segundos)`: si `cancelado is None` hace `self.dormir(segundos)` tal cual (las pruebas existentes no cambian); si no, duerme en tramos de 1 s como máximo y lanza `CicloCancelado` en cuanto `cancelado()` sea verdadero.
- `correr_ciclo(..., cancelado=None)`: se comprueba antes de cada radicado y se captura `CicloCancelado` alrededor de `fetcher.consultar`. El radicado en vuelo **no se registra**. Aviso: `Consulta cancelada por el usuario después de {n} radicados. Quedan {m} sin consultar. Puede continuar más tarde y seguirá desde ahí.` Estado final: `"Cancelado por el usuario"` (máxima precedencia). Se escribe el reporte con lo registrado y `pendientes`.
- `store.iniciar_ciclo` también reutiliza el ciclo abierto del día con estado que empiece por `Cancelado`, y lo deja `En curso`. `cerrar_interrumpidos` marca `Interrumpido` los `Cancelado%` de días anteriores. `ultimo_cierre()` **excluye** los ciclos `Cancelado%` (cancelar a propósito no debe imponer los 30 minutos de espera).
- `ejecutar_ciclo`: justo después de tomar el candado, borra `cancelar.txt` si existe (una petición vieja no debe cancelar un ciclo nuevo) y construye `cancelado = lambda: (carpeta_datos / "cancelar.txt").exists()`, que pasa a `Fetcher(cancelado=...)` y a `correr_ciclo`. Al terminar, vuelve a borrar `cancelar.txt`. Código de salida 1.

- [ ] **Pruebas que fallan:**
  1. `tests/test_fetcher.py`: con `cancelado=lambda: True`, `pausar()` lanza `CicloCancelado` sin dormir el tiempo completo; con `cancelado` que pasa a verdadero tras 2 tramos, una espera de 60 s se interrumpe y `dormidos` tiene 2 o 3 tramos de 1 s, no 60; con `cancelado=None`, `dormidos == [30.0, 60.0]` igual que hoy.
  2. `tests/test_main.py` (con `FetcherFalso` y un `cancelado` que se vuelve verdadero tras el 2.º radicado): de 5 radicados solo se consultan 2, `res.estado == "Cancelado por el usuario"`, `res.pendientes == 3`, el aviso contiene "cancelada" y "Quedan 3", el reporte existe.
  3. Reanudación: tras (2), una segunda ejecución el mismo día, sin `cancelado`, consulta solo los 3 restantes y termina `Completo` con total 5, y **sin** esperar el límite de 30 minutos (el `ultimo_cierre` ignora el cancelado).
  4. `FetcherFalso.consultar` que lanza `CicloCancelado` a mitad de un radicado: ese radicado no queda registrado y se consulta al reanudar.
  5. `ejecutar_ciclo`: una petición vieja (`cancelar.txt` ya existente antes de empezar) no cancela el ciclo; durante el ciclo, crear `cancelar.txt` (por ejemplo desde el callback `progreso`) lo cancela; al terminar el archivo no existe y el código es 1.
  6. `tests/test_store.py`: `iniciar_ciclo` reutiliza un `Cancelado%` del mismo día; `cerrar_interrumpidos` marca el de ayer; `ultimo_cierre` lo ignora.
- [ ] **Implementar** según el comportamiento de arriba.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `feat: cancelar un ciclo en marcha sin perder lo ya consultado`

---

## D. Botón Cancelar en la ventana

**Archivos:** `consultor/ventana.py`, `tests/test_ventana.py`

- [ ] `Ventana.__init__` gana el parámetro `confirmar=None`; por defecto usa `tkinter.messagebox.askyesno` con título "Cancelar consulta" y texto "¿Cancelar la consulta en curso? Lo ya consultado se conserva y podrá continuar después.". Atributo `boton_cancelar`.
- [ ] `refrescar`: `boton_cancelar` habilitado solo cuando hay un ciclo en curso (hay avance); deshabilitado en otro caso.
- [ ] Al pulsarlo: si `confirmar()` es verdadero, llama `solicitar_cancelacion(carpeta_datos)`, deshabilita el botón y muestra en la etiqueta de estado "Cancelando: termina el radicado actual y se detiene." Si devuelve `False` (el ciclo ya terminó), muestra "No hay ninguna consulta en curso."
- [ ] **Pruebas** (con `confirmar=lambda: True` o `False` inyectado, y `Bloqueo` sosteniendo un ciclo simulado como en las pruebas existentes): sin ciclo el botón está deshabilitado; con ciclo está habilitado; con `confirmar` falso no se crea `cancelar.txt`; con `confirmar` verdadero se crea `cancelar.txt` y la etiqueta dice "Cancelando"; un `estado.txt` viejo sin candado no habilita el botón ni deshabilita "Consultar ahora".
- [ ] Commit: `feat: botón Cancelar en la pantalla`

---

## E. Ejecución oculta sin perder los errores

La tarea programada pasará a lanzar `pythonw.exe` (sin ventana de consola). Un error antes de que arranque el registro de avisos no debe desaparecer en silencio.

**Archivos:** `consultor/consola.py`, `consultor/__main__.py`, `tests/test_consola.py`

- [ ] **Pruebas que fallan:**
```python
def test_sin_consola_la_salida_va_a_un_archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ruta = tmp_path / "carpeta" / "consola.log"
    redirigir_si_no_hay_consola(ruta)
    print("hola")
    sys.stderr.write("error\n")
    sys.stdout.flush(); sys.stderr.flush()
    texto = ruta.read_text(encoding="utf-8")
    assert "hola" in texto and "error" in texto


def test_con_consola_no_toca_nada(tmp_path, capsys):
    antes = sys.stdout
    redirigir_si_no_hay_consola(tmp_path / "x.log")
    assert sys.stdout is antes
    assert not (tmp_path / "x.log").exists()
```
- [ ] **Implementar** `redirigir_si_no_hay_consola(ruta)` en `consola.py`: si `sys.stdout` o `sys.stderr` es `None`, crea la carpeta, abre `ruta` en modo `a` con `encoding="utf-8"` y `buffering=1` y asigna ese archivo a los que sean `None`. En `__main__.py`, llamarla con `Path("reportes") / "consola.log"` **antes** de la reconfiguración UTF-8 existente (que ya ignora flujos `None`), y que esa reconfiguración use `errors="replace"`.
- [ ] Commit: `feat: sin consola, la salida y los errores van a reportes/consola.log`

---

## F. Documentación

- [ ] `README.md`: en "Pantalla" explicar el botón **Cancelar** (qué hace, que lo ya consultado se conserva y que se puede continuar, que sirve también para la consulta programada), que Ctrl+C en la consola también cancela de forma segura, y que cerrar la ventana negra corta el programa a la fuerza. Añadir que el ciclo programado corre oculto y que sus mensajes quedan en `reportes\avisos.log` y `reportes\consola.log`.
- [ ] Commit: `docs: cancelar y ejecución oculta en el README`

## Cierre

- [ ] `python -m pytest -q` completo en verde; reportar el conteo.
- [ ] Reportar: lista de commits y cualquier desviación respecto a este documento.
- [ ] NO tocar la tarea programada de Windows ni lanzar ningún ciclo contra el portal. Eso lo hace el controlador después.
