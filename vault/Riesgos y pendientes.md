# Riesgos y pendientes

## Pendientes con Sistemas

| Tema | Fecha de la spec |
|---|---|
| Plataforma definitiva y licencias | 18-sep (vencida) |
| Repositorio corporativo restringido y máquina virtual | 18-sep (vencida) |
| Canal de alertas (correo o Teams) | 2-oct (vencida) |
| Prueba desde la máquina virtual: IP y límites de frecuencia | 25-sep (vencida) |
| Número de reintentos (R4) y porcentaje de fallas (R5) | por definir |
| Protocolo de contingencia por portal caído | 9-oct |
| Responsable técnico que mantiene el código | por confirmar |
| Depuración y validación de radicados de la Semana 1 | por confirmar |

## Riesgos de la solución

1. **API no documentada.** Puede cambiar sin aviso. Mitigación: pruebas con respuestas grabadas que fallan si cambia la forma, aviso de "lectura fallida" y consulta manual mientras tanto.
2. **Bloqueo de IP o límite de frecuencia** desde la máquina virtual. Mitigación: pausa entre consultas y prueba temprana en ese entorno.
3. **Datos con retraso** respecto del despacho. Mitigación: se guarda la fecha de replicación de cada consulta.
4. **Contencioso-administrativo con publicación parcial.** Solo entran los validados en la Semana 1.
5. **Una sola persona validadora** y un solo responsable técnico. El seguimiento manual no se suspende.
6. **Calendario.** La construcción termina el 9-oct y el piloto empieza el 19-oct. El alcance de esta entrega se acuerda con la coordinación.

## Limitaciones conocidas

- Una decisión corregida en el Excel se ignora: cuenta solo la primera registrada para cada alerta.
- No se deben lanzar dos ciclos a la vez.
- Las alertas pendientes de ciclos anteriores reaparecen en cada reporte hasta que Alisson las decide.

Contexto técnico en [[API Rama Judicial]] y [[Arquitectura]].
