# Fase de escalamiento

Lo que se aplazó a propósito hasta que los pilotos demuestren que la herramienta funciona y vale la pena escalarla. Nada de esto bloquea el piloto.

## Infraestructura

- Servidor o máquina virtual corporativa con cuenta de servicio, en lugar del equipo local. Ver [[Decisiones]].
- Repositorio corporativo formal para la lista y los reportes.
- Aviso por correo o Teams. Hoy solo hay `avisos.log` y consola ([[reporter]]).
- Responsable técnico asignado por el Núcleo Técnico.
- Licencias y decisión de plataforma validada con Sistemas.

## Producto

- **Agente de lenguaje natural** para preguntar "¿hay novedades con los procesos?" y recibir la respuesta. Ver abajo.
- Mini página web para validar alertas, en lugar del Excel. La puerta de escritura (`registrar_decision` en [[store]]) ya está preparada.
- Otras fuentes de radicados además del Excel, por ejemplo SQL o SharePoint ([[loader]]).
- SAMAI y demás portales. Fuera de alcance según la spec.
- Columna de empresa en el reporte. La hoja real no la tiene y `DEMANDANTE` y `DEMANDADO` mezclan personas y empresas.

## Rendimiento

- Con más de unos 100 radicados el portal frena con mucha frecuencia ([[Operación y límites del portal]]). Opciones: reutilizar el `idProceso` guardado para saltarse la búsqueda, y pedir solo la primera página de actuaciones cuando ya hay referencia. La segunda puede perder una actuación registrada con fecha antigua, así que requiere decidirlo con cuidado.
- Concurrencia: no hace falta por debajo de 500 radicados.

## Limitaciones conocidas por resolver

- Una decisión corregida en el Excel se ignora: cuenta solo la primera.

## Agente de lenguaje natural

Pregunta de ejemplo: "¿Hay alguna novedad con los procesos?" y respuesta "Sí, en tal y tal".

**Restricción de la spec:** no se usa IA generativa sobre el texto de las actuaciones en esta fase, y los datos se procesan solo en ambiente corporativo, sin cuentas personales. Un modelo en la nube enviaría la posición litigiosa de la empresa a un tercero.

| Opción | Qué es | Estado |
|---|---|---|
| A. Preguntas rápidas sin IA | Respuestas armadas desde la base de datos con detección de palabras clave. Exacto, no inventa | Cumple la spec hoy |
| B. Modelo local | Corre en el mismo equipo, sin internet. Más libre pero más lento y menos fiable | Consultar con Sistemas y la coordinación |
| C. Modelo en la nube | El más capaz, pero los datos salen de la compañía | Requiere aprobación expresa |

Recomendación cuando llegue el momento: empezar por A. Cualquier respuesta debe mostrar el dato real y la leyenda "verificar en la fuente oficial". Un agente generativo sobre procesos judiciales puede equivocarse y una abogada podría confiar en él.

Decisión tomada el 2026-10-08: se aplaza. No se construye en el piloto.

Ver [[Riesgos y pendientes]].
