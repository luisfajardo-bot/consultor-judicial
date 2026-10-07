# fetcher

**Qué hace:** por cada radicado hace las dos llamadas de [[API Rama Judicial]] y devuelve las actuaciones o un error tipificado.

**Comportamiento:**
- Pausa de 1 s entre radicados
- Reintentos con espera creciente (R4). Número configurable
- Siempre `SoloActivos=false`
- Descarta `sujetosProcesales` antes de devolver nada
- Guarda la fecha de replicación del portal

**Es el único módulo que conoce la Rama Judicial.** Si el portal cambia o aparece un captcha, solo se toca este archivo.

**Pruebas:** con respuestas JSON grabadas: éxito, vacío, error 500, timeout.

**Depende de:** requests. Usado por [[main]].
