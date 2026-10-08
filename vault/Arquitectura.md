# Arquitectura

Pipeline lineal. Cada módulo tiene una responsabilidad y se prueba solo. Estado: 141 pruebas, probado en Windows (Python 3.14) y en Linux (Python 3.12).

```mermaid
flowchart LR
    F[(Lista de radicados<br/>Excel hoy, otra mañana)] --> L[loader]
    CFG[config.toml] --> M
    L --> M[main<br/>ejecutar_ciclo]
    B[bloqueo<br/>candado y avance] --- M
    M --> FE[fetcher]
    FE -->|actuaciones| C[comparator]
    C --> S[(store<br/>SQLite)]
    S --> R[reporter]
    R --> X[Excel del reporte]
    X -->|Alisson marca decisión| D[registrar_decision]
    D --> S
    FE -. GET .-> P((Portal Rama Judicial))
    M --> MT[mantenimiento<br/>archivado y respaldo]
    MT --> S
    V[ventana tkinter] --> PA[panel<br/>lógica sin tkinter]
    PA --> S
    V --> M
    B -. estado.txt .-> PA
```

## Un ciclo

1. [[main]] toma el candado ([[bloqueo]]) y comprueba el límite entre ejecuciones.
2. Lee las decisiones de Alisson de los reportes anteriores y las guarda con `registrar_decision`.
3. Marca como Interrumpidos los ciclos abiertos de días anteriores.
4. [[loader]] entrega la lista de radicados.
5. [[fetcher]] consulta cada uno, sin repetir los ya consultados en este ciclo (así se reanuda).
6. [[comparator]] clasifica: POSIBLE NOVEDAD, SIN CAMBIO o NO VERIFICADO.
7. [[store]] guarda actuaciones, consulta y alertas en una sola transacción.
8. Si el portal bloquea, el ciclo se pausa y continúa en la siguiente ejecución. Si fallan demasiadas consultas, se detiene (R5).
9. [[reporter]] escribe el reporte **antes** de cerrar el ciclo.
10. [[mantenimiento]] archiva reportes viejos y respalda la base.

## Capas

| Capa | Módulos | Regla |
|---|---|---|
| Lógica de negocio | [[comparator]], [[store]] | No conocen el portal ni la pantalla |
| Portal | [[fetcher]] | Único que conoce la Rama Judicial |
| Entrada y salida | [[loader]], [[reporter]] | Intercambiables |
| Orquestación | [[main]], [[bloqueo]], [[mantenimiento]] | Una función pública, `ejecutar_ciclo`, usada por consola y ventana |
| Vista | [[panel y ventana]] | La lógica del panel no importa tkinter, así que otra vista (web) la reutiliza |

## Ejecución

- Consola: `python -m consultor run`.
- Ventana (solo Windows): `python -m consultor ventana`, o `scripts\abrir_panel.bat`.
- Tarea programada de Windows `ConsultorJudicial`: lunes, miércoles y viernes a las 9:00, con `scripts\ejecutar_ciclo.bat`.
- Docker: no hay Dockerfile todavía. Funciona en Linux desde la línea de comandos, sin ventana. Ver [[Fase de escalamiento]].

Ver [[Decisiones]] para el porqué de cada elección y [[Operación y límites del portal]] para lo medido contra el portal real.
