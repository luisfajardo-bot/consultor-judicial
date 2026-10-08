# Riesgos y pendientes

Actualizado el 2026-10-08, antes del primer ciclo oficial (viernes 9-oct, 9:00).

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

## Riesgos de la solución

1. **API no documentada.** Puede cambiar sin aviso. Mitigación: la herramienta avisa "ALERTA: la API posiblemente cambió" y marca los radicados como NO VERIFICADO. La consulta manual sigue en paralelo.
2. **El portal limita las consultas.** Corta tras unas 60 a 70 peticiones. Mitigación: pausa entre peticiones, espera larga, pausa del ciclo y reanudación. Con más de unos 100 radicados será frecuente ([[Operación y límites del portal]]).
3. **Bloqueo de IP desde otro equipo o red.** Solo se midió desde el equipo actual.
4. **Datos con retraso** respecto del despacho. La fecha de replicación está disponible pero apagada.
5. **Contencioso-administrativo con publicación parcial.** Solo entran los validados.
6. **Una sola persona validadora** y un solo responsable técnico. El seguimiento manual no se suspende.
7. **La base de datos es el único registro** cuando se archivan los Excel, y está en un solo equipo. Mitigación: respaldo semanal, pero en el mismo equipo hasta que se defina la carpeta de red.
8. **La tarea programada depende de que la sesión de Windows esté iniciada** y de que el equipo esté encendido.

## Limitaciones conocidas

- Una decisión corregida en el Excel se ignora: cuenta solo la primera.
- Una consulta de un solo radicado no se reanuda como ciclo completo.
- Las alertas pendientes reaparecen en cada reporte hasta que Alisson las decide.

Contexto técnico en [[API Rama Judicial]] y [[Arquitectura]].
