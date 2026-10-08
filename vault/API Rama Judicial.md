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

## Llamada 3: detalle

`GET /api/v2/Proceso/Detalle/<idProceso>` devuelve `ultimaActualizacion`, la fecha de replicación del portal. Se guarda con cada consulta en [[store]].

## Lo que se aprendió probando contra el portal real

- **El portal responde 403 al User-Agent por defecto de `requests`** (`python-requests/x`). `curl`, un User-Agent vacío, uno de navegador y uno descriptivo reciben 200. [[fetcher]] se identifica con un User-Agent propio y honesto.
- **Un proceso sin actuaciones, o una página inexistente, devuelve HTTP 404 con JSON** (`"Message": "No se encontraron Actuaciones ..."`). Solo ese mensaje se acepta como "sin actuaciones". Cualquier otro 404 es falla del portal.
- **Un radicado puede devolver varios procesos.** Se consultan todos y se unen sin duplicar por `idRegActuacion`.
- **Paginación:** cada actuación trae `cant` con el total del proceso. Si la primera página trae menos, se piden las siguientes.

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
