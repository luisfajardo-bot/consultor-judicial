# main

**Qué hace:** orquesta un ciclo completo. Se lanza con `python -m consultor run`.

**Pasos:**
1. Abre el ciclo en [[store]].
2. Lee las decisiones de Alisson del Excel anterior y las guarda con `registrar_decision`.
3. Pide la lista a [[loader]].
4. Por cada radicado sin consulta registrada en este ciclo: [[fetcher]], luego [[comparator]], luego guarda en [[store]].
5. Si falla más del porcentaje configurado, detiene el ciclo y avisa "fuente no disponible" (R5).
6. Llama a [[reporter]].

**Errores inesperados:** quedan en la bitácora y el ciclo termina con aviso. Nunca se queda parado en silencio (CA4).

**Configuración:** todo viene de `config.toml`: fuente del loader, rutas, pausa, reintentos, porcentaje de fallas y destinatarios.

**Programación:** el Programador de tareas de Windows lo lanza lunes, miércoles y viernes con una cuenta de servicio y la opción "ejecutar aunque el usuario no haya iniciado sesión".

Ver [[Arquitectura]].
