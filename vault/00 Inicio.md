# Consultor Judicial

Herramienta que consulta lunes, miércoles y viernes los radicados del grupo en la Consulta de Procesos Nacional Unificada, detecta actuaciones nuevas y entrega un reporte que valida Alisson Rengifo.

No decide nada jurídico. El seguimiento manual sigue en paralelo.

## Mapa

- [[Arquitectura]]: vista general y flujo de un ciclo
- [[API Rama Judicial]]: lo que se verificó del portal
- [[Reglas de negocio]]: R1 a R9
- [[Criterios de aceptación]]: CA1 a CA5
- [[Validación humana]]: cómo marca Alisson sus decisiones
- [[Decisiones]]: qué se eligió y por qué
- [[Riesgos y pendientes]]

## Módulos

[[loader]] · [[fetcher]] · [[comparator]] · [[store]] · [[reporter]] · [[main]]

## Escala

44 procesos activos hoy. Techo de diseño: 500.

## Documento de diseño

El texto completo y versionado está en `docs/superpowers/specs/2026-10-07-consultor-judicial-design.md`. Estas notas son la versión navegable.
