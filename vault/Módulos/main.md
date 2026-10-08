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
3. Recorre los radicados, saltando los ya consultados en este ciclo.
4. **R5:** a partir de 10 consultas, si falla más del 50 %, se detiene. También se evalúa al cerrar.
5. **Bloqueo del portal:** se detiene al primer bloqueo, no registra el radicado bloqueado ni los siguientes, avisa cuántos quedan y deja el ciclo Pausado.
6. **Cambio de API:** si alguna consulta devolvió forma inesperada, avisa "ALERTA: la API posiblemente cambió".
7. Escribe el reporte **antes** de cerrar el ciclo, para que un fallo del reporte no cierre un ciclo sin que nadie vea sus alertas.
8. Mantenimiento ([[mantenimiento]]). Un fallo ahí nunca cambia el código de salida.

## Estados finales del ciclo
Completo · Completo con fallas de la fuente · Completo con alerta: posible cambio en la API · Detenido: fuente no disponible · Detenido: posible cambio en la API · Pausado: el portal bloqueó las consultas · Lista vacía.

## Configuración
Todo viene de `config.toml`. Ver `config.example.toml`: fuente, salida, portal (ritmo y bloqueo), ejecución (límite) y mantenimiento.

Ver [[Arquitectura]] y [[Operación y límites del portal]].
