# Validación humana

## Alisson Rengifo

En cada ciclo revisa el reporte, abre el enlace de cada POSIBLE NOVEDAD en la fuente oficial y marca Confirmada o Descartada. Solo si confirma actualiza el cuadro de seguimiento. Revisa a mano los NO VERIFICADOS. Durante el piloto es la única persona que valida alertas.

## Cómo marca

El reporte de [[reporter]] trae una columna "Decisión" con desplegable: Pendiente, Confirmada, Descartada. Al iniciar el ciclo siguiente, [[main]] lee esas decisiones y las guarda con `registrar_decision(alerta_id, estado, usuario)` en [[store]].

El Excel es una vista. La fuente de verdad es SQLite.

## Web futura

`registrar_decision` es la única puerta de escritura del estado de validación. Una mini página web sería otro cliente de esa función, sin cambios en la base de datos ni en las reglas.

## Escalamiento

Toda novedad confirmada que implique providencia, término, audiencia, requerimiento o sentencia se escala el mismo día a Juan Uribe y al abogado responsable. Lectura de providencias, cómputo de términos y gestión del proceso son decisiones exclusivamente humanas.

Leyenda obligatoria en el reporte: "Alerta automática. No constituye notificación procesal ni actuación confirmada; verificar en la fuente oficial."
