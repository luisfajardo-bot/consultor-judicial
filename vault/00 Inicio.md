# Consultor Judicial

Herramienta que consulta lunes, miércoles y viernes los radicados activos del grupo en la Consulta de Procesos Nacional Unificada, detecta actuaciones nuevas y entrega un reporte que valida Alisson Rengifo.

No decide nada jurídico. El seguimiento manual sigue en paralelo.

**Estado (2026-10-08):** construida y probada contra el portal real con 41 procesos. 141 pruebas en verde, en Windows y en Linux. Tarea programada lista para el viernes 9-oct a las 9:00, que será el ciclo de referencia.

## Mapa

- [[Arquitectura]]: vista general y flujo de un ciclo
- [[API Rama Judicial]]: lo que se verificó del portal
- [[Operación y límites del portal]]: cuota del portal, pausas, candado, mantenimiento y alertas
- [[Reglas de negocio]]: R1 a R9 y cómo quedó cada una
- [[Criterios de aceptación]]: CA1 a CA5
- [[Validación humana]]: cómo marca Alisson sus decisiones
- [[Decisiones]]: qué se eligió y por qué
- [[Fase de escalamiento]]: lo aplazado, incluido el agente de lenguaje natural
- [[Riesgos y pendientes]]

## Módulos

[[loader]] · [[fetcher]] · [[comparator]] · [[store]] · [[reporter]] · [[main]] · [[bloqueo]] · [[mantenimiento]] · [[panel y ventana]]

## Escala

41 procesos activos consultados hoy. Techo de diseño: 500. Con más de unos 100, el portal frenará con frecuencia.

## Documentos del repositorio

- Diseño: `docs/superpowers/specs/2026-10-07-consultor-judicial-design.md`
- Planes de implementación: `docs/superpowers/plans/`
- Cómo instalar y usar: `README.md`

Estas notas son la versión navegable. Si algo no coincide, manda el código.
