# Riesgos y pendientes

Actualizado el 2026-10-13. El ciclo de referencia terminó a las 9:27: 34 radicados con referencia, 7 con radicado inválido, 0 alertas.

## Pendientes

| Tema | Quién | Estado |
|---|---|---|
| Depurar los radicados inválidos de la lista (7 activos con formato inválido, 3 repetidos, 1 fila con una dirección web en el estado) | Gerencia correspondiente, con Alisson | Mañana |
| De dónde sale la empresa en el reporte: la hoja real no la trae | Gerencia | Sin decidir |
| Carpeta de red para las copias de la base | Sistemas | Sin definir. Hoy están en el mismo equipo |
| Cuenta de GitHub para el repositorio | Luis | Por confirmar si es corporativa |
| Plazo de conservación de los reportes archivados | Gerencia Jurídica | Sin decidir. El borrado está apagado |
| Protocolo de contingencia por portal caído | Núcleo Técnico redacta, Gerencia Jurídica aprueba | Pendiente |
| Línea base de tiempos manuales de Alisson | Alisson | Pendiente |
| Responsable técnico que mantiene el código | Núcleo Técnico | Por confirmar |
| Canal de alertas (correo o Teams) | Sistemas | Aplazado, ver [[Fase de escalamiento]] |
| Verificar `scripts\ejecutar_ciclo.bat` en el equipo de producción: ahora usa `.venv\Scripts\pythonw.exe` con `start /wait`; probar que corre oculto, que el código de salida llega bien (0 completo, 3 límite) y que sin `.venv` deja el aviso en `reportes\consola.log` y sale con 2 | Luis y Sistemas | Pendiente |
| Mover `reporte_ciclo_0001_2026-10-09.xlsx` de la raíz del repositorio a `reportes\archivo\` (git lo ignora pero es información confidencial) | Luis | Pendiente |
| Hora de la tarea programada: el README dice 06:30 y la bóveda 9:00 | Luis | Sin decidir |
| Aviso activo (correo, Teams o archivo ALERTA) y reintento automático tras un bloqueo del portal: hoy un bloqueo un viernes deja los pendientes hasta el lunes | Sistemas | Aplazado |
| Fijar dependencias transitivas con hashes y `pip-audit` periódico | Núcleo Técnico | Pendiente |

## Riesgos de la solución

1. **API no documentada.** Puede cambiar sin aviso. Mitigación: la herramienta avisa "ALERTA: la API posiblemente cambió" y marca los radicados como NO VERIFICADO. La consulta manual sigue en paralelo.
2. **El portal limita las consultas.** Corta tras unas 60 a 70 peticiones. Mitigación: pausa entre peticiones, espera larga, pausa del ciclo y reanudación. Con más de unos 100 radicados será frecuente ([[Operación y límites del portal]]).
3. **Bloqueo de IP desde otro equipo o red.** Solo se midió desde el equipo actual.
4. **Datos con retraso** respecto del despacho. La fecha de replicación está disponible pero apagada.
5. **Contencioso-administrativo con publicación parcial.** Solo entran los validados.
6. **Una sola persona validadora** y un solo responsable técnico. El seguimiento manual no se suspende.
7. **La base de datos es el único registro** cuando se archivan los Excel, y está en un solo equipo. Mitigación: respaldo semanal, pero en el mismo equipo hasta que se defina la carpeta de red.
8. **La tarea programada depende de que la sesión de Windows esté iniciada** y de que el equipo esté encendido. Corre oculta, así que cerrar una ventana ya no la corta.
9. **El 9-oct la tarea se cortó a los 20 segundos** porque se cerró su ventana de consola. Se corrigió: ejecución oculta, estado confiable y botón Cancelar.
10. **Decisiones falsificables.** Cualquier archivo `reporte_*.xlsx` en `reportes\` puede descartar alertas ajenas firmando como el validador, y arrastrar para rellenar la columna Decisión descarta alertas de forma irreversible (la primera decisión cuenta). Aceptado el 2026-10-13: la única usuaria de la herramienta es Alisson y nadie más tiene acceso a la carpeta. Se reabre si alguien más obtiene acceso.
11. **Respaldo de `actuacion_radicado`.** Al actualizar una base existente, el respaldo único puede generar una vez alertas de más en radicados que comparten proceso con otro y tenían una sola consulta (el error va hacia avisar de más, nunca de menos). Además la creación de la tabla y su respaldo no son atómicos: si el proceso muere entre ambos, la tabla queda vacía y cada radicado alertaría su historial una vez (alerta de más, no pérdida). Mejora posible: marcar con `PRAGMA user_version`.
12. **Prueba sin cubrir.** `test_ultima_actuacion_no_necesita_ordenar_aparte` revisa una copia fija de la consulta antigua, no la consulta real de `ultima_actuacion` (que ahora pasa por `actuacion_radicado`); la protección del índice quedó sin cubrir. El volumen es de pocas filas por radicado.
13. **Aviso de filas sin radicado.** Si la fuente no tiene filtro de estado configurado, una fila con solo el estado cuenta como "con datos". El aviso también sale en el modo `--solo-radicado`.
14. **Radicados pegados.** Dos radicados distintos con un dígito de más y uno de menos pegados (24+22 dígitos) se cortan en dos números de 23 que parecen válidos; el portal casi seguro no los encuentra (queda NO VERIFICADO). Raro: requiere dos errores de digitación.
15. **Panel y rutas relativas.** El panel abre y recrea el esquema de la base cada segundo, y las rutas son relativas al directorio de trabajo (`datos\`, `reportes\`): lanzar desde otra carpeta crea otra base. Bajo, sin arreglar.

## Limitaciones conocidas

- Una decisión corregida en el Excel se ignora: cuenta solo la primera.
- Una consulta de un solo radicado no se reanuda como ciclo completo.
- Las alertas pendientes reaparecen en cada reporte hasta que Alisson las decide.

Contexto técnico en [[API Rama Judicial]] y [[Arquitectura]].
