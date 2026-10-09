"""Vista mínima con tkinter. Toda la lógica está en panel.py y main.py."""

import os
import queue
import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .main import Ejecucion, cargar_config, ejecutar_ciclo
from .panel import leer_avance, resumen_ultimo_ciclo, solicitar_cancelacion, texto_avance, texto_resumen, ultimo_reporte
from .store import Store

FUENTE = ("Segoe UI", 11)
FUENTE_TITULO = ("Segoe UI", 16, "bold")
ROJO = "#8b0000"
VERDE = "#006400"


class Ventana:
    def __init__(self, raiz, cfg, ejecutar=ejecutar_ciclo, confirmar=None):
        self.raiz, self.cfg, self.ejecutar = raiz, cfg, ejecutar
        self.confirmar = confirmar or (
            lambda: messagebox.askyesno(
                "Cancelar consulta",
                "¿Cancelar la consulta en curso? Lo ya consultado se conserva y podrá continuar después.",
            )
        )
        self.carpeta_datos = os.path.dirname(cfg["salida"]["base_datos"])
        self.carpeta_reportes = cfg["salida"]["carpeta_reportes"]
        self.cola = queue.Queue()
        self.hilo = None
        self.cancelando = False
        self.texto_resumen_actual = texto_resumen(None)

        raiz.title("Consultor Judicial")
        raiz.option_add("*Font", FUENTE)
        estilo = ttk.Style(raiz)
        estilo.configure("TButton", font=FUENTE, padding=6)
        estilo.configure("TLabel", font=FUENTE)
        estilo.map("TButton", focuscolor=[("focus", "#000000")])
        marco = ttk.Frame(raiz, padding=16)
        marco.pack(fill="both", expand=True)

        ttk.Label(marco, text="Consultor Judicial", font=FUENTE_TITULO).pack(anchor="w")
        self.etiqueta_resumen = ttk.Label(marco, text=self.texto_resumen_actual, justify="left", wraplength=520)
        self.etiqueta_resumen.pack(anchor="w", pady=(8, 8))
        self.barra = ttk.Progressbar(marco, length=520, mode="determinate")
        self.barra.pack(fill="x")
        self.etiqueta_avance = ttk.Label(marco, text="", wraplength=520)
        self.etiqueta_avance.pack(anchor="w", pady=(4, 8))
        self.etiqueta_estado = tk.Label(marco, text="", font=FUENTE, wraplength=520, justify="left", anchor="w")
        self.etiqueta_estado.pack(anchor="w", fill="x", pady=(0, 8))

        botones = ttk.Frame(marco)
        botones.pack(anchor="w")
        self.boton_consultar = ttk.Button(botones, text="Consultar ahora", command=self.consultar)
        self.boton_consultar.pack(side="left", padx=(0, 8))
        self.boton_reporte = ttk.Button(botones, text="Abrir último reporte", command=self.abrir_reporte)
        self.boton_reporte.pack(side="left", padx=(0, 8))
        self.boton_cancelar = ttk.Button(botones, text="Cancelar", command=self.cancelar, state="disabled")
        self.boton_cancelar.pack(side="left")
        for b in (self.boton_consultar, self.boton_reporte, self.boton_cancelar):
            b.bind("<Return>", lambda e: e.widget.invoke())

    def refrescar(self):
        avance = leer_avance(self.carpeta_datos)
        corriendo = bool(self.hilo and self.hilo.is_alive())
        if avance:
            self.barra["maximum"] = avance.total
            self.barra["value"] = avance.hecho
            self.etiqueta_avance.config(text=texto_avance(avance))
        else:
            self.barra["value"] = 0
            self.etiqueta_avance.config(text="")
            if not corriendo:
                try:
                    store = Store(self.cfg["salida"]["base_datos"])
                    try:
                        self.texto_resumen_actual = texto_resumen(resumen_ultimo_ciclo(store))
                    finally:
                        store.con.close()
                except sqlite3.OperationalError:
                    pass  # base ocupada: se deja el texto anterior
        if not avance:
            self.cancelando = False
        self.etiqueta_resumen.config(text=self.texto_resumen_actual)
        self.boton_consultar.config(state="disabled" if avance or corriendo else "normal")
        self.boton_cancelar.config(state="normal" if avance and not self.cancelando else "disabled")

    def consultar(self):
        self.etiqueta_estado.config(text="")
        self.boton_consultar.config(state="disabled")
        self.hilo = threading.Thread(target=lambda: self.cola.put(self.ejecutar(self.cfg)), daemon=True)
        self.hilo.start()

    def cancelar(self):
        if not self.confirmar():
            return
        if solicitar_cancelacion(self.carpeta_datos):
            self.cancelando = True
            self.boton_cancelar.config(state="disabled")
            self.etiqueta_estado.config(text="Cancelando: termina el radicado actual y se detiene.", fg=ROJO)
        else:
            self.etiqueta_estado.config(text="No hay ninguna consulta en curso.", fg=ROJO)

    def sondear(self):
        while True:
            try:
                e = self.cola.get_nowait()
            except queue.Empty:
                break
            self._mostrar(e)
        self.refrescar()
        self.raiz.after(1000, self.sondear)

    def _mostrar(self, e: Ejecucion):
        if e.codigo == 0:
            self.etiqueta_estado.config(text="Consulta terminada", fg=VERDE)
        elif e.codigo == 3:
            self.etiqueta_estado.config(text=e.mensaje, fg=ROJO)
        elif e.codigo == 2:
            self.etiqueta_estado.config(text="La consulta falló con un error inesperado. Ver avisos.log.", fg=ROJO)
        else:
            self.etiqueta_estado.config(text="La consulta terminó con avisos. Revisa el reporte.", fg=ROJO)

    def abrir_reporte(self):
        ruta = ultimo_reporte(self.carpeta_reportes)
        if ruta is None:
            self.etiqueta_estado.config(text="Todavía no hay reportes.", fg=ROJO)
        elif hasattr(os, "startfile"):
            os.startfile(ruta)


def abrir(ruta_config) -> int:
    cfg = cargar_config(ruta_config)
    raiz = tk.Tk()
    v = Ventana(raiz, cfg)
    v.sondear()
    raiz.mainloop()
    return 0
