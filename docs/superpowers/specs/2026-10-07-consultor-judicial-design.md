# Consultor Judicial: documento de diseño

Fecha: 2026-10-07
Estado: borrador para revisión
Fuente de requisitos: `spec-inicial.pdf` (16 campos, Fase B y piloto)

## 1. Qué se construye

Una herramienta que consulta tres veces por semana (lunes, miércoles y viernes) una lista de radicados en la Consulta de Procesos Nacional Unificada de la Rama Judicial. Guarda las actuaciones de cada proceso, detecta las que son nuevas y entrega un reporte para que Alisson Rengifo las valide.

No decide nada jurídico, no lee providencias, no escribe en el cuadro oficial de seguimiento y no envía nada fuera del equipo jurídico. El seguimiento manual sigue en paralelo hasta que haya una decisión expresa de adopción.

Escala: 44 procesos activos hoy, techo de diseño de 500.

## 2. Hallazgo técnico que condiciona el diseño

El portal consume una API JSON pública. Se verificó el 2026-10-07 con consultas de solo lectura sobre un radicado público: responde sin captcha, sin cookies y sin autenticación.

| Paso | Llamada | Devuelve |
|---|---|---|
| 1 | `GET /api/v2/Procesos/Consulta/NumeroRadicacion?numero=<23 dígitos>&SoloActivos=false&pagina=1` | `idProceso`, despacho, `fechaUltimaActuacion`, partes |
| 2 | `GET /api/v2/Proceso/Actuaciones/<idProceso>?pagina=1` | lista de actuaciones con `idRegActuacion`, `consActuacion`, `fechaActuacion`, `actuacion`, `anotacion`, `fechaRegistro`, `fechaInicial`, `fechaFinal` |

Host: `consultaprocesos.ramajudicial.gov.co:448`.

Detalles que importan:

- Siempre `SoloActivos=false`. Con `true`, un proceso inactivo vuelve vacío y R3 lo marcaría como "sin resultados" sin que lo esté.
- `sujetosProcesales` trae nombres de personas naturales. Se descarta en el módulo `fetcher`, antes de que llegue al resto del código, para respetar el límite de Nivel 2 de la spec.
- Cada actuación tiene identificador propio. La detección de novedades compara por `idRegActuacion`, que es más robusto que comparar fecha y texto.
- El portal muestra una "fecha de replicación de datos" que puede ir por detrás del despacho. Se guarda con cada consulta para explicar retrasos.

Sin verificar todavía: límites de frecuencia del portal, comportamiento desde la máquina virtual de Sistemas, actuaciones de procesos contencioso-administrativos con publicación parcial, y paginación más allá de la página 1.

Razón de elegir HTTP directo y no un navegador automatizado: no hay captcha, es mucho más rápido y no depende del diseño visual de la página. El navegador queda como contingencia si la API se cierra.

## 3. Arquitectura final

```
                    config.toml
                         |
  +----------+     +-----------+     +------------+     +--------------+
  | Fuente   | --> |  loader   | --> |  fetcher   | --> |  comparator  |
  | (Excel   |     | cargar()  |     | 2 GET a la |     | reglas R1,   |
  | hoy,     |     | list[     |     | API, pausa |     | R2, R6.      |
  | otra     |     | Radicado] |     | y reintentos|    | Lógica pura  |
  | mañana)  |     +-----------+     +------------+     +--------------+
  +----------+                              |                    |
                                            v                    v
                                      +--------------------------------+
                                      |             store              |
                                      |  SQLite: radicado, actuacion,  |
                                      |  alerta, ciclo, consulta       |
                                      +--------------------------------+
                                            |                    ^
                                            v                    |
                                      +------------+     registrar_decision()
                                      |  reporter  |             |
                                      | Excel/CSV  |     +------------------+
                                      | + aviso    | --> | Excel del reporte|
                                      +------------+     | (Alisson marca   |
                                                         | Confirmada /     |
                                                         | Descartada)      |
                                                         +------------------+

  main.py orquesta un ciclo y aplica R5 (corte si fallan demasiadas consultas).
  Programador de tareas de Windows lanza: python -m consultor run  (lun, mié, vie)
```

### Módulos

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `loader.py` | Contrato `cargar() -> list[Radicado]`. Valida 23 dígitos (R7). Implementación inicial: Excel, solo lectura | openpyxl |
| `fetcher.py` | Dos GET por radicado, pausa de 1 s entre consultas, reintentos con espera creciente. Devuelve actuaciones o un error tipificado. Único módulo que conoce la Rama Judicial | requests |
| `comparator.py` | Lógica pura. Recibe actuaciones traídas y guardadas, devuelve POSIBLE NOVEDAD, SIN CAMBIO o NO VERIFICADO | ninguna |
| `store.py` | SQLite. Histórico, bitácora y estado de validación. Única puerta de escritura de decisiones: `registrar_decision(alerta_id, estado, usuario)` | sqlite3 |
| `reporter.py` | Genera el Excel/CSV por ciclo y el aviso, con encabezado de totales y la leyenda obligatoria | openpyxl |
| `main.py` | Orquesta el ciclo, importa las decisiones de Alisson al inicio, aplica R5 | todos |

### Modelo de datos (SQLite)

- `radicado`: radicado, empresa, despacho, `id_proceso`, activo.
- `actuacion`: `id_reg_actuacion` (clave), radicado, `fecha_actuacion`, actuación, anotación, `fecha_registro`, `fecha_inicial`, `fecha_final`, `primera_vez_visto`.
- `alerta`: radicado, `id_reg_actuacion`, ciclo, estado (Pendiente, Confirmada, Descartada), validada_por, validada_en. Sostiene R6 y CA5.
- `ciclo`: inicio, fin, totales, estado final.
- `consulta`: ciclo, radicado, hora, resultado, motivo del fallo, fecha de replicación del portal. Cada consulta se registra al terminar, lo que permite reanudar un ciclo interrumpido.

Nada se borra (R8).

## 4. Flujo de un ciclo

1. `main` abre un ciclo y lee del Excel de reportes anteriores las decisiones de Alisson, que guarda con `registrar_decision`.
2. `loader` entrega la lista de radicados.
3. Para cada radicado sin consulta registrada en este ciclo, `fetcher` pide las dos llamadas.
4. `comparator` clasifica:
   - Primera vez que se ve el radicado: se guarda como referencia, sin alerta (R2).
   - Hay actuaciones cuyo `idRegActuacion` no estaba guardado: POSIBLE NOVEDAD, con todas las nuevas, no solo la última (R1).
   - No hay actuaciones nuevas: SIN CAMBIO.
   - Sin resultados o error tras reintentos: NO VERIFICADO con motivo (R3, R4).
5. Una actuación ya alertada o Descartada no vuelve a alertar (R6).
6. Si falla más del porcentaje configurado de consultas, el ciclo se detiene y avisa "fuente no disponible" (R5).
7. `reporter` escribe el reporte y envía el aviso a Alisson, con copia a Juan Uribe.

## 5. Validación humana

El reporte trae por cada alerta una columna "Decisión" con desplegable (Pendiente, Confirmada, Descartada). Alisson la completa en el mismo archivo. Al iniciar el ciclo siguiente, esas decisiones se leen y se guardan en SQLite. El Excel es una vista y la fuente de verdad es el Store.

Preparación para una web futura: como `registrar_decision` es la única puerta de escritura, una mini página web sería otro cliente de esa misma función, sin cambiar la base de datos ni las reglas.

El reporte pone arriba las POSIBLES NOVEDADES y los NO VERIFICADOS, y deja los SIN CAMBIO en una hoja aparte. Lleva la leyenda: "Alerta automática. No constituye notificación procesal ni actuación confirmada; verificar en la fuente oficial."

Decisiones que siguen siendo exclusivamente humanas: lectura de providencias, cómputo de términos y gestión del proceso.

## 6. Fallos y reglas operativas

- Reintentos con espera creciente por radicado. Número configurable (pendiente con Sistemas, R4).
- Corte de ciclo por porcentaje de fallas configurable (pendiente con Sistemas, R5).
- Cualquier error inesperado queda en la bitácora y el ciclo termina con aviso. No se queda parado en silencio (CA4).
- Se consulta siempre por radicado, nunca por nombre de parte (R7).
- La herramienta nunca escribe en el cuadro oficial (R9).

## 7. Escala

Consultas en serie con pausa de 1 s. Peor caso, 500 radicados por dos llamadas: unos 17 minutos. Con los 44 actuales, menos de 2. La concurrencia se añade solo si se superan los 500.

No se omite la segunda llamada aunque `fechaUltimaActuacion` no haya cambiado: una actuación nueva con la misma fecha que la anterior pasaría sin detectarse, lo que contradice CA2.

## 8. Pruebas

- `comparator` se prueba sin red con casos construidos a mano: primera consulta sin alerta, actuación nueva, sin cambios, actuación Descartada que no se repite, varias actuaciones nuevas en el mismo ciclo.
- `fetcher` se prueba con respuestas JSON grabadas: éxito, vacío, error 500, timeout.
- Una prueba de dos ciclos sobre un SQLite temporal, donde el segundo ciclo detecta una actuación inyectada.
- CA1 y CA2 contra radicados reales no se automatizan. Se miden en el piloto con el reporte y el conjunto de prueba de Alisson.

## 9. Configuración y ejecución

Un archivo `config.toml` con: fuente del loader, rutas del Excel, de la base y del repositorio, pausa entre consultas, reintentos, porcentaje de fallas, destinatarios del aviso. Nada de esto va fijo en el código.

Ejecución: `python -m consultor run`. El Programador de tareas de Windows lo lanza lunes, miércoles y viernes en la máquina virtual corporativa, con una cuenta de servicio y la opción "ejecutar aunque el usuario no haya iniciado sesión".

Plataforma: Python. Razón: las reglas de comparación, deduplicación y estado persistente, y las pruebas de aceptación, son mucho más sencillas y verificables en código. Power Automate Desktop programado sin supervisión suele exigir una licencia de RPA desatendido que puede no estar incluida en el Microsoft 365 vigente. Decisión sujeta a validación de Sistemas.

## 10. Fuera de alcance

SAMAI, TYBA, Siglo XXI, micrositios y demás fuentes distintas de la Consulta Nacional Unificada. Descarga o lectura de expedientes y providencias. Interpretación jurídica, cómputo de términos, IA generativa. Escritura en el cuadro oficial. Comunicaciones a terceros. Concurrencia y mini web (ambas se dejan preparadas, no construidas).

## 11. Pendientes y riesgos

| Tema | Responsable | Fecha de la spec |
|---|---|---|
| Plataforma definitiva y licencias | Sistemas / Núcleo Técnico | 18-sep (vencida) |
| Repositorio corporativo restringido y máquina virtual | Sistemas | 18-sep (vencida) |
| Canal de alertas (correo o Teams) | Sistemas | 2-oct (vencida) |
| Prueba desde la máquina virtual: IP, límites de frecuencia | Núcleo Técnico | 25-sep (vencida) |
| Número de reintentos y porcentaje de fallas | Sistemas | por definir |
| Protocolo de contingencia por portal caído | Núcleo Técnico redacta, Gerencia Jurídica aprueba | 9-oct |
| Responsable técnico que mantiene el código | Núcleo Técnico / Sistemas | por confirmar |
| Depuración y validación de radicados de la Semana 1 | Alisson Rengifo | por confirmar |

Riesgos propios de la solución:

1. API no documentada: puede cambiar sin aviso. Mitigación: pruebas con respuestas grabadas que fallan si cambia la forma, aviso de "lectura fallida", consulta manual mientras tanto.
2. Bloqueo de IP o límite de frecuencia desde la máquina virtual. Mitigación: pausa entre consultas, prueba temprana en ese entorno.
3. Datos con retraso respecto del despacho. Mitigación: se guarda la fecha de replicación de cada consulta.
4. Procesos contencioso-administrativos con publicación parcial: solo entran los validados en la Semana 1.
5. Dependencia de una sola persona validadora y de un responsable técnico. Mitigación: la revisión manual no se suspende.
6. Fecha de la spec vencida: la construcción termina el 9-oct y el piloto empieza el 19-oct. El alcance real de esta primera entrega debe acordarse con la coordinación.
