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
| Línea base de tiempos manuales de Alisson. La spec (campo 12) trae una base preliminar de la Gerencia Jurídica (sep-2026): ~2 h por ciclo, 2 ciclos por semana, ~4 h semanales. Falta validarla con el formato de la Semana 1 (fecha, hora inicio/fin, procesos, portal, novedades, minutos de actualización del cuadro). El tiempo de la herramienta no se mide aparte: sale de `ciclo.inicio` y `ciclo.fin`, o con cronómetro | Alisson | Parcial |
| Responsable técnico que mantiene el código | Núcleo Técnico | Por confirmar |
| Canal de alertas (correo o Teams) | Sistemas | Aplazado, ver [[Fase de escalamiento]] |
| Mover `reporte_ciclo_0001_2026-10-09.xlsx` de la raíz del repositorio a `reportes\archivo\` (git lo ignora pero es información confidencial) | Luis | Pendiente |
| Aviso activo (correo, Teams o archivo ALERTA) y reintento tras un bloqueo del portal: hoy un bloqueo un viernes deja los pendientes hasta el lunes | Sistemas | Aplazado |
| Fijar dependencias transitivas con hashes y `pip-audit` periódico | Núcleo Técnico | Pendiente |

## Riesgos de la solución

1. **API no documentada.** Puede cambiar sin aviso. Mitigación: la herramienta avisa "ALERTA: la API posiblemente cambió" y marca los radicados como NO VERIFICADO. La consulta manual sigue en paralelo.
2. **El portal limita las consultas.** Corta tras unas 60 a 70 peticiones. Mitigación: pausa entre peticiones, espera larga, pausa del ciclo y reanudación. Con más de unos 100 radicados será frecuente ([[Operación y límites del portal]]).
3. **Bloqueo de IP desde otro equipo o red.** Solo se midió desde el equipo actual.
4. **Datos con retraso** respecto del despacho. La fecha de replicación está disponible pero apagada.
5. **Contencioso-administrativo con publicación parcial.** Solo entran los validados.
6. **Una sola persona validadora** y un solo responsable técnico. El seguimiento manual no se suspende.
7. **La base de datos es el único registro** cuando se archivan los Excel, y está en un solo equipo. Mitigación: respaldo semanal, pero en el mismo equipo hasta que se defina la carpeta de red.
9. **El 9-oct la tarea se cortó a los 20 segundos** porque se cerró su ventana de consola. Se corrigió: ejecución oculta, estado confiable y botón Cancelar.
10. **Decisiones falsificables.** Cualquier archivo `reporte_*.xlsx` en `reportes\` puede descartar alertas ajenas firmando como el validador, y arrastrar para rellenar la columna Decisión descarta alertas de forma irreversible (la primera decisión cuenta). Aceptado el 2026-10-13: la única usuaria de la herramienta es Alisson y nadie más tiene acceso a la carpeta. Se reabre si alguien más obtiene acceso.
11. **Respaldo de `actuacion_radicado`.** Al actualizar una base existente, la migración copia lo conocido entre radicados que comparten proceso (vía `radicado.id_proceso`) y es a prueba de cortes: se ejecuta siempre que la tabla de enlace esté vacía y `actuacion` no. La exposición que queda son solo los radicados cuyo `id_proceso` nunca se registró (el error va hacia avisar de más, nunca de menos).
12. **Aviso de filas sin radicado.** Si la fuente no tiene filtro de estado configurado, una fila con solo el estado cuenta como "con datos". El aviso también sale en el modo `--solo-radicado`.
13. **Radicados pegados.** Dos radicados distintos con un dígito de más y uno de menos pegados (24+22 dígitos) se cortan en dos números de 23 que parecen válidos; el portal casi seguro no los encuentra (queda NO VERIFICADO). Raro: requiere dos errores de digitación.
14. **Panel y rutas relativas.** El panel abre y recrea el esquema de la base cada segundo, y las rutas son relativas al directorio de trabajo (`datos\`, `reportes\`): lanzar desde otra carpeta crea otra base. Bajo, sin arreglar.

Nota: la ventana de la primera consulta se ancla al primer intento del radicado, no a hoy: un radicado que falló varios días sigue contando lo registrado desde que entró a la lista.

## Limitaciones conocidas

- Una decisión corregida en el Excel se ignora: cuenta solo la primera.
- Una consulta de un solo radicado no se reanuda como ciclo completo.
- Las alertas pendientes reaparecen en cada reporte hasta que Alisson las decide.

Contexto técnico en [[API Rama Judicial]] y [[Arquitectura]].
