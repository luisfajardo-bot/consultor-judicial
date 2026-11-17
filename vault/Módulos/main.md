# main

**Qué hace:** orquesta un ciclo completo.

## Puntos de entrada
- `ejecutar_ciclo(cfg, forzar, solo_radicado, progreso, avisar_fn)`: la función pública. No imprime: devuelve una `Ejecucion` con `codigo`, `mensaje` y `resumen`. La usan la consola y la ventana.
- `ejecutar(argv)`: el comando. `python -m consultor run` o `ventana`. Opciones: `--forzar`, `--solo-radicado`, `--abrir`, `--config`.

## Códigos de salida
| Código | Significado |
|---|---|
| 0 | Ciclo completo |
| 1 | Pausado, detenido o con alertas (portal bloqueado, API cambiada, fuente no disponible, lista vacía) |
| 2 | Error inesperado |
| 3 | No se ejecutó: ya hay otro ciclo corriendo o la última consulta es muy reciente |

## Orden de un ciclo
1. Candado ([[bloqueo]]) y límite entre ejecuciones (30 min por defecto). Una consulta de un solo radicado no cuenta para el límite.
2. Importa las decisiones de Alisson y marca Interrumpidos los ciclos viejos.
3. Recorre los radicados, saltando los consultados con éxito en este ciclo. Lo fallido se reintenta; no se borra, para no perder el primer intento de un radicado nuevo.
4. **Portal caído:** 5 fallas seguidas (`FALLAS_SEGUIDAS`) o R5 (a partir de 10 consultas, más del 50 %). Espera 15 y 30 min (`ESPERAS_CAIDA`) y reintenta lo fallido. Si sigue, lo deja "Pausado: el portal no responde", reanudable el mismo día. Si la mayoría de las fallas son respuestas con forma inesperada (cambio de la API), no espera: se detiene.
5. **Bloqueo del portal:** se detiene al primer bloqueo, no registra el radicado bloqueado ni los siguientes, avisa cuántos quedan y deja el ciclo Pausado.
5b. Si más de la mitad de los radicados no aparecen en el portal, avisa posible cambio de la API.
6. **Cambio de API:** si alguna consulta devolvió forma inesperada, avisa "ALERTA: la API posiblemente cambió".
7. Escribe el reporte **antes** de cerrar el ciclo, para que un fallo del reporte no cierre un ciclo sin que nadie vea sus alertas.
8. Mantenimiento ([[mantenimiento]]). Un fallo ahí nunca cambia el código de salida.

## Estados finales del ciclo
Completo · Completo con fallas de la fuente · Completo con alerta: posible cambio en la API · Detenido: fuente no disponible · Detenido: posible cambio en la API · Pausado: el portal bloqueó las consultas · Lista vacía.

## Configuración
Todo viene de `config.toml`. Ver `config.example.toml`: fuente, salida, portal (ritmo y bloqueo), ejecución (límite) y mantenimiento.

Ver [[Arquitectura]] y [[Operación y límites del portal]].
