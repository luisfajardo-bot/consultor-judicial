# Validación humana

## Alisson Rengifo
En cada ciclo revisa el reporte, abre el enlace de cada POSIBLE NOVEDAD en la fuente oficial y marca Confirmada o Descartada. Solo si confirma actualiza el cuadro de seguimiento. Revisa a mano los NO VERIFICADO. Durante el piloto es la única persona que valida alertas.

## Cómo marca
El reporte de [[reporter]] trae una columna "Decisión" con desplegable: Pendiente, Confirmada, Descartada. Al iniciar el ciclo siguiente, [[main]] lee esas decisiones y las guarda con `registrar_decision(alerta_id, estado, usuario)` en [[store]]. Si deja "Validó" en blanco, se registra el validador configurado.

El Excel es una vista. La fuente de verdad es SQLite.

## Reglas que conviene saber
- **El reporte para decidir es siempre el más reciente.** Las alertas Pendiente de ciclos anteriores reaparecen ahí hasta que se deciden.
- **Una decisión marcada en un reporte archivado no se importa** ([[mantenimiento]]).
- **La primera decisión es la que cuenta.** Si se corrige después en el Excel, la corrección se ignora ([[Fase de escalamiento]]).
- **Guardar y cerrar el archivo** antes del siguiente ciclo. Un Excel abierto no se puede leer y se reintenta en el ciclo siguiente.
- Una fila con un ID de alerta que no es un número se ignora sin afectar a las demás.

## Escalamiento
Toda novedad confirmada que implique providencia, término, audiencia, requerimiento o sentencia se escala el mismo día a Juan Uribe y al abogado responsable. Lectura de providencias, cómputo de términos y gestión del proceso son decisiones exclusivamente humanas.

## Web futura
`registrar_decision` es la única puerta de escritura del estado de validación. Una mini página web sería otro cliente de esa función, sin cambios en la base de datos ni en las reglas.

Leyenda obligatoria en el reporte: "Alerta automática. No constituye notificación procesal ni actuación confirmada; verificar en la fuente oficial."
