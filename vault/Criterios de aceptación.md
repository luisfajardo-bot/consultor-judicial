# Criterios de aceptación

Del campo 11 de la spec inicial.

| Criterio | Dado... | La herramienta produce... | Cómo se prueba |
|---|---|---|---|
| CA1 Cobertura | la lista del piloto | consulta exitosa de al menos el 90 % por ciclo y el 100 % del resto como NO VERIFICADO con motivo | Medición en el piloto con el reporte |
| CA2 Detección | un conjunto de prueba con actuaciones nuevas conocidas por Alisson | POSIBLE NOVEDAD en al menos el 90 %, sin omitir ninguna cuya consulta fue exitosa | Medición en el piloto. La lógica se prueba en [[comparator]] |
| CA3 Sin alertas innecesarias | un radicado sin cambios entre dos ciclos | SIN CAMBIO, sin alerta. Máximo 10 % de alertas Descartadas por ciclo | Prueba de [[comparator]] y medición en el piloto |
| CA4 Fallas | portal caído, captcha o bloqueo | NO VERIFICADO con hora y motivo, y aviso "fuente no disponible" | Prueba de [[fetcher]] con respuestas grabadas |
| CA5 Trazabilidad | cualquier alerta | quién la validó, cuándo y con qué resultado, y no se repite en el ciclo siguiente | Prueba de dos ciclos sobre [[store]] |

CA1 y CA2 dependen del portal y de datos reales. No se automatizan completos.
