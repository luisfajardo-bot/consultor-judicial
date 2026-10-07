# Decisiones

| Decisión | Elegido | Razón |
|---|---|---|
| Cómo leer el portal | HTTP directo a la API JSON | No hay captcha, es rápido y no depende del diseño de la página. Navegador automatizado queda como contingencia. Ver [[API Rama Judicial]] |
| Plataforma | Python | Comparación, deduplicación y estado persistente son más simples y verificables en código. Power Automate programado sin supervisión puede exigir licencia de RPA desatendido. Sujeta a validación de Sistemas |
| Almacén del histórico | SQLite, un archivo | Transaccional, no se corrompe si un ciclo falla a la mitad. El Excel editado a mano sí podría romper el estado |
| Fuente de radicados | Contrato `cargar()` con Excel como primera implementación | Mañana puede cambiar la fuente sin tocar el resto. Ver [[loader]] |
| Dónde decide Alisson | Excel del reporte | Es lo que ya usa. Preparado para una web futura con [[Validación humana]] |
| Escala | Consultas en serie, techo de 500 | 500 radicados son unos 17 minutos. Concurrencia solo si se supera el techo |
| Segunda llamada | Siempre se hace | Si no, una actuación nueva con la misma fecha que la anterior pasaría sin detectarse |
| Detección | Por `idRegActuacion` | Más robusto que comparar fecha y texto |
| Datos personales | `sujetosProcesales` se descarta en [[fetcher]] | Límite de Nivel 2 de la spec |
