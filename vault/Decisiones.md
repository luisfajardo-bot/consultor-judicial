# Decisiones

| Decisión | Elegido | Razón |
|---|---|---|
| Cómo leer el portal | HTTP directo a la API JSON | No hay captcha, es rápido y no depende del diseño de la página. Ver [[API Rama Judicial]] |
| Plataforma | Python | Comparación, deduplicación y estado persistente son más simples y verificables en código. Power Automate programado sin supervisión puede exigir licencia de RPA desatendido |
| Almacén del histórico | SQLite, un archivo | Transaccional, no se corrompe si un ciclo falla a la mitad. Sin servidor |
| Modo WAL de SQLite | No | No es seguro si la carpeta queda en una unidad de red |
| Fuente de radicados | Contrato `cargar()` con Excel como primera implementación | Mañana puede cambiar la fuente sin tocar el resto ([[loader]]) |
| Dónde decide Alisson | Excel del reporte | Es lo que ya usa. Preparado para una web con `registrar_decision` ([[store]]) |
| Escala | Consultas en serie, techo de 500 | Concurrencia solo si se supera el techo |
| Segunda llamada | Siempre se hace | Si no, una actuación nueva con la misma fecha que la anterior pasaría sin detectarse |
| Detección | Por `idRegActuacion` | Más robusto que comparar fecha y texto |
| Datos personales | `sujetosProcesales` se descarta en [[fetcher]] | Límite de Nivel 2 de la spec |
| Dónde corre | Equipo corporativo local con tarea programada, lunes, miércoles y viernes a las 9:00 | La máquina virtual no es un requisito técnico. Se aplaza a la fase de escalamiento |
| Dos ciclos a la vez | Imposible, con candado del sistema operativo ([[bloqueo]]) | Una persona no técnica no tiene por qué saber que no debe hacerlo |
| Repetir consultas | Mínimo 30 minutos entre ciclos completos, `--forzar` lo salta | Cuida la cuota del portal |
| Portal bloquea | Esperar y reintentar, y si persiste, pausar y continuar en la siguiente ejecución | La cuota es de 60 a 70 peticiones y se libera en unos 2 minutos ([[Operación y límites del portal]]) |
| Detalle del proceso | Apagado por defecto | Ahorra una petición por radicado y su dato no cambia ninguna decisión |
| Primera página o todas | Todas las páginas de actuaciones | Una página sola podría perder una actuación registrada con fecha antigua |
| Reportes antiguos | Archivar a los 14 días, no borrar | Pesan 10 KB: es orden, no espacio. El plazo de conservación lo decide la Gerencia Jurídica ([[mantenimiento]]) |
| Respaldo de la base | Semanal, verificado, últimas 8 | La base pasa a ser el único registro cuando se archivan los Excel |
| Pantalla | Mínima, con lógica separada de la vista ([[panel y ventana]]) | Ampliarla es una decisión de otra gerencia |
| Agente de lenguaje natural | Aplazado | La spec prohíbe IA generativa sobre las actuaciones en esta fase. Ver [[Fase de escalamiento]] |
| Agregar procesos y cambiar estado desde la ventana | No por ahora | Choca con R9 y con que solo Alisson administra la lista. Requiere decisión de otra gerencia |
| Referencia de partida | Empezar de cero el 9-oct | El ciclo de prueba del 8-oct se descartó |
| Requirements | Versiones fijadas, runtime separado de desarrollo | Reproducible. Probado en Linux limpio con Python 3.12 |
