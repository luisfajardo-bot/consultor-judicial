# API de la Rama Judicial

Verificada el 2026-10-07 con consultas de solo lectura sobre un radicado público. Responde JSON sin captcha, sin cookies y sin autenticación.

Host: `consultaprocesos.ramajudicial.gov.co:448`

## Llamada 1: buscar el proceso

`GET /api/v2/Procesos/Consulta/NumeroRadicacion?numero=<23 dígitos>&SoloActivos=false&pagina=1`

Devuelve `idProceso`, despacho, `fechaUltimaActuacion` y partes.

Usar siempre `SoloActivos=false`. Con `true`, un proceso inactivo vuelve vacío y [[Reglas de negocio]] R3 lo marcaría como "sin resultados" sin serlo.

## Llamada 2: actuaciones

`GET /api/v2/Proceso/Actuaciones/<idProceso>?pagina=1`

Cada actuación trae `idRegActuacion`, `consActuacion`, `fechaActuacion`, `actuacion`, `anotacion`, `fechaRegistro`, `fechaInicial` y `fechaFinal`.

## Datos personales

`sujetosProcesales` trae nombres de personas naturales. [[fetcher]] los descarta antes de que lleguen al resto del código.

## Fecha de replicación

El portal muestra una fecha de replicación de datos que puede ir por detrás del despacho. Se guarda con cada consulta, en [[store]].

## Sin verificar

- Límites de frecuencia
- Comportamiento desde la máquina virtual de Sistemas
- Actuaciones de procesos contencioso-administrativos
- Paginación más allá de la página 1

Ver [[Riesgos y pendientes]].
