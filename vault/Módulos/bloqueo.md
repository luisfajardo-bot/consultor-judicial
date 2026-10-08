# bloqueo

**Qué hace:** impide que corran dos ciclos a la vez y publica el avance del que está corriendo.

## El candado
Es un candado del sistema operativo sobre `datos\consultor.lock`: `msvcrt` en Windows y `fcntl` en Linux. Si el programa muere, el sistema lo libera solo, sin archivos huérfanos que limpiar. No se usa `os.kill(pid, 0)`: en Windows termina procesos.

Quien intenta un segundo ciclo recibe `CicloEnCurso` con el avance del primero y [[main]] responde con código 3: "Ya hay una consulta en curso (09:00 | 12 de 44). No hace falta lanzarla otra vez".

## El avance
`estado.txt`, con el formato `HH:MM | N de M`, se reescribe de forma atómica en cada radicado y se borra al terminar. Es la **fuente única del avance**: lo leen el segundo intento de ejecución y el [[panel y ventana]], así que la ventana muestra también el avance de la tarea programada.

Usado por [[main]]. Medido en [[Operación y límites del portal]].
