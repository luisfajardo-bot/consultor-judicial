"""Vista mínima con tkinter. Toda la lógica está en panel.py y main.py."""

import os
import queue
import sqlite3
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime
from tkinter import messagebox, ttk

from .ajustes import DIAS_MAXIMO, DIAS_POR_DEFECTO, consultas_activas, guardar_activas, guardar_dias, leer_dias
from .main import Ejecucion, cargar_config, ejecutar_ciclo
from .models import CONFIRMADA, DESCARTADA, PENDIENTE
from .panel import (
    leer_avance,
    resumen_ultimo_ciclo,
    separar,
    solicitar_cancelacion,
    texto_avance,
    texto_confirmar_bloque,
    texto_dias_guardado,
    texto_pestana_anteriores,
    texto_pestana_rango,
    texto_resumen,
    ultimo_reporte,
)
from .reporter import ENLACE_PORTAL
from .store import Store

FUENTE = ("Segoe UI", 11)
FUENTE_TITULO = ("Segoe UI", 16, "bold")
ROJO = "#8b0000"
VERDE = "#006400"

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
AYUDA = (
    "Confirmar = la actuación es real y ya la revisé en el portal. "
    "Descartar = no requiere acción (repetida, trámite sin efecto, error)."
)
AL_DIA = "Al día ✓"
SIN_SELECCION = "Seleccione al menos una alerta."
BASE_OCUPADA = "La base está ocupada por una consulta; intente de nuevo en unos segundos."
RADICADO_COPIADO = "Radicado copiado"
MAXIMO_SIN_PREGUNTAR = 5
ANCHO_AYUDA = 900  # la ayuda en una línea: tabla y detalle ya ocupan ese ancho
LINEAS_DETALLE = 5
ESPERA_BASE_SEGUNDOS = 2  # lo que espera la ventana para escribir si una consulta tiene la base
SIN_CARGAR = object()  # la lista aún no se pudo leer: sondear() reintenta
FILTROS = ("Todas", "Confirmada", "Descartada")
COLUMNAS_DECIDIDAS = (
    ("decision", "Decisión", 90),
    ("decidida", "Decidida en", 130),
    ("por", "Por", 90),
    ("radicado", "Radicado", 150),
    ("actuacion", "Actuación", 260),
)
MARCADA, SIN_MARCAR = "☑", "☐"
COLUMNAS = (
    ("marca", "", 32),
    ("detectada", "Detectada", 80),
    ("radicado", "Radicado", 150),
    ("fecha", "Fecha actuación", 110),
    ("actuacion", "Actuación", 220),
)


def dia_mes(texto) -> str:
    """'2026-11-13...' -> '13-nov', sin depender del idioma del sistema."""
    try:
        d = date.fromisoformat(str(texto)[:10])
    except ValueError:
        return str(texto or "")
    return f"{d.day:02d}-{MESES[d.month - 1]}"


class Ventana:
    def __init__(
        self,
        raiz,
        cfg,
        ejecutar=ejecutar_ciclo,
        confirmar=None,
        preguntar=None,
        informar=None,
        hoy=date.today,
    ):
        self.raiz, self.cfg, self.ejecutar, self.hoy = raiz, cfg, ejecutar, hoy
        self.preguntar = preguntar or messagebox.askyesno
        self.informar = informar or messagebox.showwarning
        self.marcadas: set[int] = set()
        self.decididas = None  # la VentanaDecididas abierta, si hay una
        self._alertas: dict[int, dict] = {}
        self.ciclo_recargado = SIN_CARGAR  # último ciclo terminado cuando se cargó la lista
        self.ultimo_ciclo_id = None  # último ciclo terminado que vio refrescar()
        self._error_pantalla = False
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
        self.etiqueta_encendido = tk.Label(marco, text="", font=FUENTE, wraplength=520, justify="left", anchor="w")
        self.etiqueta_encendido.pack(anchor="w", fill="x", pady=(4, 0))
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
        self.boton_cancelar.pack(side="left", padx=(0, 8))
        self.boton_encendido = ttk.Button(botones, command=self.alternar_encendido)
        self.boton_encendido.pack(side="left")
        for b in (self.boton_consultar, self.boton_reporte, self.boton_cancelar, self.boton_encendido):
            b.bind("<Return>", lambda e: e.widget.invoke())

        ajuste = ttk.Frame(marco)  # en una sola línea: la ventana debe caber en pantallas de 768 px
        ajuste.pack(anchor="w", pady=(8, 0))
        ttk.Label(ajuste, text="Días a revisar: avisar lo registrado en los últimos").pack(side="left", padx=(0, 6))
        self.dias = tk.StringVar(value=str(leer_dias(self.carpeta_datos, self._dias_config())))
        self.campo_dias = ttk.Spinbox(
            ajuste, from_=0, to=DIAS_MAXIMO, width=4, textvariable=self.dias, command=self.guardar_dias
        )
        self.campo_dias.pack(side="left", padx=(0, 6))
        ttk.Label(ajuste, text="días (también define la pestaña Por decidir)").pack(side="left")
        for evento in ("<Return>", "<FocusOut>"):
            self.campo_dias.bind(evento, lambda e: self.guardar_dias())
        self.etiqueta_ajuste = tk.Label(marco, text="", font=FUENTE, wraplength=520, justify="left", anchor="w")
        self.etiqueta_ajuste.pack(anchor="w", fill="x")

        self._crear_alertas(marco)
        self.recargar_alertas()

    # alertas por decidir
    def _crear_alertas(self, marco):
        ttk.Style(self.raiz).configure("Pestanas.TNotebook", padding=0)
        self.pestanas = ttk.Notebook(marco, style="Pestanas.TNotebook", height=1)
        for _ in range(2):  # las pestañas solo eligen la lista; la tabla va debajo de la ayuda y los botones
            self.pestanas.add(ttk.Frame(self.pestanas, height=1))
        self.pestanas.pack(anchor="w", fill="x", pady=(8, 0))
        self.pestanas.bind("<<NotebookTabChanged>>", lambda e: self._pintar_pestana())
        ttk.Label(marco, text=AYUDA, wraplength=ANCHO_AYUDA, justify="left").pack(anchor="w", pady=(4, 4))

        botones = ttk.Frame(marco)
        botones.pack(anchor="w")
        self.boton_todas = ttk.Button(botones, text="Seleccionar todas", command=self.seleccionar_todas)
        self.boton_confirmar = ttk.Button(
            botones, text="Confirmar seleccionadas", command=lambda: self.aplicar(CONFIRMADA)
        )
        self.boton_descartar = ttk.Button(
            botones, text="Descartar seleccionadas", command=lambda: self.aplicar(DESCARTADA)
        )
        self.boton_decididas = ttk.Button(botones, text="Ver decididas", command=self.ver_decididas)
        for b in (self.boton_todas, self.boton_confirmar, self.boton_descartar, self.boton_decididas):
            b.pack(side="left", padx=(0, 8))
            b.bind("<Return>", lambda e: e.widget.invoke())
        self.etiqueta_alertas = tk.Label(marco, text="", font=FUENTE, wraplength=520, justify="left", anchor="w")
        self.etiqueta_alertas.pack(anchor="w", fill="x", pady=(4, 0))

        zona = ttk.Frame(marco)  # tabla a la izquierda, detalle a la derecha: así cabe en 768 px de alto
        zona.pack(fill="both", expand=True)
        tablas = ttk.Frame(zona)
        tablas.pack(side="left", fill="both", expand=True)
        self._zonas = [self._crear_tabla(tablas), self._crear_tabla(tablas)]
        self.tabla_rango, self.tabla_anteriores = (tabla for _, tabla in self._zonas)

        detalle = ttk.Frame(zona)
        detalle.pack(side="left", fill="y", padx=(8, 0))
        # Text de alto fijo: una anotación larga se desplaza dentro del cuadro en vez de agrandar la ventana
        self.etiqueta_detalle = tk.Text(
            detalle, width=36, height=LINEAS_DETALLE, wrap="word", font=FUENTE, relief="flat", state="disabled"
        )
        barra = ttk.Scrollbar(detalle, orient="vertical", command=self.etiqueta_detalle.yview)
        self.etiqueta_detalle.configure(yscrollcommand=barra.set)
        self.boton_portal = ttk.Button(detalle, text="Abrir en el portal", command=self.abrir_portal)
        self.boton_portal.pack(side="bottom", anchor="w", pady=(4, 0))
        self.etiqueta_detalle.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        self.boton_portal.bind("<Return>", lambda e: e.widget.invoke())

    def _crear_tabla(self, padre):
        marco = ttk.Frame(padre)
        tabla = ttk.Treeview(marco, columns=[c for c, _, _ in COLUMNAS], show="headings", height=6)
        for columna, titulo, ancho in COLUMNAS:
            tabla.heading(columna, text=titulo)
            anclaje = "center" if columna == "marca" else "w"
            tabla.column(columna, width=ancho, stretch=columna == "actuacion", anchor=anclaje)
        barra = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        tabla.bind("<Button-1>", self._clic_en_tabla)
        tabla.bind("<space>", lambda e: self._alternar_enfocada())
        tabla.bind("<<TreeviewSelect>>", lambda e: self.mostrar_detalle())
        return marco, tabla

    def _tabla_visible(self):
        return self._zonas[self.pestanas.index("current")][1]

    def _dias_guardados(self) -> int:
        return leer_dias(self.carpeta_datos, self._dias_config())

    def recargar_alertas(self) -> None:
        try:
            store = Store(self.cfg["salida"]["base_datos"])
            try:
                pendientes = store.alertas_pendientes()
                ciclo = store.ultimo_ciclo()
            finally:
                store.con.close()
        except sqlite3.OperationalError:
            self.ciclo_recargado = SIN_CARGAR  # base ocupada: se deja la lista como está y se reintenta
            return
        self.ciclo_recargado = self.ultimo_ciclo_id = ciclo["id"] if ciclo else None
        dias = self._dias_guardados()
        en_rango, anteriores = separar(pendientes, self.hoy(), dias)
        self._alertas = {a["id"]: a for a in pendientes}
        self.marcadas &= set(self._alertas)
        for tabla, filas in ((self.tabla_rango, en_rango), (self.tabla_anteriores, anteriores)):
            foco = tabla.focus()
            tabla.delete(*tabla.get_children())
            for a in filas:
                tabla.insert("", "end", iid=str(a["id"]), values=self._valores(a))
            if foco and tabla.exists(foco):
                tabla.focus(foco)
                tabla.selection_set(foco)
        self.pestanas.tab(0, text=texto_pestana_rango(dias, len(en_rango)))
        self.pestanas.tab(1, text=texto_pestana_anteriores(len(anteriores)))
        self._pintar_pestana()

    def _valores(self, a):
        radicado = a["radicado"]
        corto = "…" + radicado[-13:] if len(radicado) > 13 else radicado
        marca = MARCADA if a["id"] in self.marcadas else SIN_MARCAR
        return (marca, dia_mes(a["detectada"]), corto, dia_mes(a["fecha_actuacion"]), a["actuacion"] or "")

    def _pintar_pestana(self):
        visible = self._tabla_visible()
        for marco, tabla in self._zonas:
            if tabla is visible:
                marco.pack(fill="both", expand=True)
            else:
                marco.pack_forget()
        self.etiqueta_alertas.config(text="" if visible.get_children() else AL_DIA, fg=VERDE)
        self._pintar_boton_todas()
        self.mostrar_detalle()

    def _pintar_boton_todas(self):
        ids = {int(i) for i in self._tabla_visible().get_children()}
        todas = bool(ids) and ids <= self.marcadas
        self.boton_todas.config(text="Quitar selección" if todas else "Seleccionar todas")

    def _pintar_marca(self, alerta_id: int):
        for tabla in (self.tabla_rango, self.tabla_anteriores):
            if tabla.exists(str(alerta_id)):
                tabla.set(str(alerta_id), "marca", MARCADA if alerta_id in self.marcadas else SIN_MARCAR)

    def alternar_marca(self, alerta_id: int) -> None:
        self.marcadas ^= {alerta_id}
        self._pintar_marca(alerta_id)
        self._pintar_boton_todas()

    def _clic_en_tabla(self, evento):
        tabla = evento.widget
        fila = tabla.identify_row(evento.y)
        if fila and tabla.identify_region(evento.x, evento.y) == "cell" and tabla.identify_column(evento.x) == "#1":
            self.alternar_marca(int(fila))

    def _alternar_enfocada(self):
        fila = self._tabla_visible().focus()
        if fila:
            self.alternar_marca(int(fila))

    def seleccionar_todas(self) -> None:
        ids = {int(i) for i in self._tabla_visible().get_children()}
        if ids and ids <= self.marcadas:
            self.marcadas -= ids
        else:
            self.marcadas |= ids
        for alerta_id in ids:
            self._pintar_marca(alerta_id)
        self._pintar_boton_todas()

    def aplicar(self, estado: str) -> int:
        """Decide las alertas marcadas de la pestaña visible. Devuelve cuántas cambiaron."""
        ids = [int(i) for i in self._tabla_visible().get_children() if int(i) in self.marcadas]
        if not ids:
            self.etiqueta_alertas.config(text=SIN_SELECCION, fg=ROJO)
            return 0
        if len(ids) > MAXIMO_SIN_PREGUNTAR and not self.preguntar(
            "Decisión en bloque", texto_confirmar_bloque(estado, len(ids))
        ):
            return 0
        try:
            cambiadas = self._decidir(ids, estado)
        except sqlite3.OperationalError:
            self.etiqueta_alertas.config(text=BASE_OCUPADA, fg=ROJO)
            return 0
        self.marcadas -= set(ids)
        self.recargar_alertas()
        return cambiadas

    def _decidir(self, ids, estado) -> int:
        ruta = self.cfg["salida"]["base_datos"]
        # Store() espera hasta 5 s por la base; antes se prueba con espera corta para avisar pronto.
        prueba = sqlite3.connect(ruta, timeout=ESPERA_BASE_SEGUNDOS)
        try:
            prueba.execute("BEGIN IMMEDIATE")
        finally:
            prueba.close()  # sin commit: no se escribió nada
        store = Store(ruta)
        try:
            store.con.execute(f"PRAGMA busy_timeout = {ESPERA_BASE_SEGUNDOS * 1000}")
            return store.decidir(ids, estado, self.cfg["salida"]["validador"], datetime.now())
        finally:
            store.con.close()

    def _alerta_enfocada(self):
        fila = self._tabla_visible().focus()
        return self._alertas.get(int(fila)) if fila else None

    def mostrar_detalle(self) -> None:
        a = self._alerta_enfocada()
        texto = "" if a is None else (
            f"{a['radicado']} · {a['despacho']}\n"
            f"{a['fecha_actuacion']} · {a['actuacion']}\n"
            f"Anotación: {a['anotacion'] or '—'}\n"
            f"Detectada el {str(a['detectada'])[:16].replace('T', ' ')} (consulta {a['ciclo_id']})"
        )
        self.etiqueta_detalle.config(state="normal")
        self.etiqueta_detalle.delete("1.0", "end")
        self.etiqueta_detalle.insert("1.0", texto)
        self.etiqueta_detalle.config(state="disabled")

    def texto_detalle(self) -> str:
        return self.etiqueta_detalle.get("1.0", "end-1c")

    def abrir_portal(self) -> None:
        webbrowser.open(ENLACE_PORTAL)  # el portal no admite enlace directo por radicado
        a = self._alerta_enfocada()
        if a is not None:
            self.raiz.clipboard_clear()
            self.raiz.clipboard_append(a["radicado"])
            self.etiqueta_alertas.config(text=RADICADO_COPIADO, fg=VERDE)

    def ver_decididas(self) -> "VentanaDecididas":
        if self.decididas is not None and self.decididas.ventana.winfo_exists():
            self.decididas.ventana.deiconify()
            self.decididas.ventana.lift()
            self.decididas.ventana.focus_force()
            return self.decididas
        self.decididas = VentanaDecididas(self)
        return self.decididas

    def _dias_config(self):
        return self.cfg.get("primera_consulta", {}).get("alertar_ultimos_dias", DIAS_POR_DEFECTO)

    def guardar_dias(self):
        try:
            dias = guardar_dias(self.carpeta_datos, self.dias.get())
        except ValueError as e:
            self.dias.set(str(leer_dias(self.carpeta_datos, self._dias_config())))
            self.etiqueta_ajuste.config(text=str(e), fg=ROJO)
            return
        self.dias.set(str(dias))
        self.etiqueta_ajuste.config(text=texto_dias_guardado(dias), fg=VERDE)
        self.recargar_alertas()

    def alternar_encendido(self):
        guardar_activas(self.carpeta_datos, not consultas_activas(self.carpeta_datos))
        self.refrescar()

    def refrescar(self):
        activas = consultas_activas(self.carpeta_datos)
        if activas:
            self.etiqueta_encendido.config(text="Consultas de este equipo: ENCENDIDAS", fg=VERDE)
        else:
            self.etiqueta_encendido.config(
                text="Consultas de este equipo: APAGADAS. «Consultar ahora» no sale a la Rama Judicial.",
                fg=ROJO,
            )
        self.boton_encendido.config(text="Apagar consultas" if activas else "Encender consultas")
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
                        resumen = resumen_ultimo_ciclo(store)
                        self.texto_resumen_actual = texto_resumen(resumen)
                        self.ultimo_ciclo_id = resumen.id if resumen else None
                    finally:
                        store.con.close()
                except sqlite3.OperationalError:
                    pass  # base ocupada: se deja el texto anterior
        if not avance:
            self.cancelando = False
        self.etiqueta_resumen.config(text=self.texto_resumen_actual)
        self.boton_consultar.config(state="disabled" if avance or corriendo or not activas else "normal")
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
            self.recargar_alertas()
        try:
            self.refrescar()
            if self.ultimo_ciclo_id != self.ciclo_recargado:  # terminó otra consulta
                self.recargar_alertas()
            if self._error_pantalla:  # el refresco se recuperó: quitar el aviso
                self._error_pantalla = False
                self.etiqueta_estado.config(text="")
        except Exception as e:  # la pantalla debe seguir viva aunque la base o la carpeta fallen
            self._error_pantalla = True
            self.etiqueta_estado.config(
                text=f"No se pudo actualizar la pantalla ({type(e).__name__}). Avise a Sistemas.", fg=ROJO
            )
        finally:
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


class VentanaDecididas:
    """Alertas ya decididas: se filtran, se corrigen (también a Pendiente) y muestran su historial."""

    def __init__(self, principal: Ventana):
        self.principal = principal
        self.ventana = tk.Toplevel(principal.raiz)
        self.ventana.title("Alertas decididas")
        marco = ttk.Frame(self.ventana, padding=12)
        marco.pack(fill="both", expand=True)

        arriba = ttk.Frame(marco)
        arriba.pack(anchor="w", fill="x")
        ttk.Label(arriba, text="Mostrar:").pack(side="left", padx=(0, 6))
        self.filtro = tk.StringVar(value=FILTROS[0])
        self.selector = ttk.Combobox(arriba, textvariable=self.filtro, values=FILTROS, state="readonly", width=12)
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>", lambda e: self.recargar())

        zona = ttk.Frame(marco)
        zona.pack(fill="both", expand=True, pady=(8, 0))
        self.tabla = ttk.Treeview(
            zona, columns=[c for c, _, _ in COLUMNAS_DECIDIDAS], show="headings", height=10, selectmode="extended"
        )
        for columna, titulo, ancho in COLUMNAS_DECIDIDAS:
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, stretch=columna == "actuacion", anchor="w")
        barra = ttk.Scrollbar(zona, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self.mostrar_historial())

        botones = ttk.Frame(marco)
        botones.pack(anchor="w", pady=(8, 0))
        ttk.Label(botones, text="Pasar seleccionadas a:").pack(side="left", padx=(0, 8))
        for estado in (CONFIRMADA, DESCARTADA, PENDIENTE):
            b = ttk.Button(botones, text=estado, command=lambda e=estado: self.corregir(e))
            b.pack(side="left", padx=(0, 8))
            b.bind("<Return>", lambda e: e.widget.invoke())
        self.etiqueta_aviso = tk.Label(marco, text="", font=FUENTE, wraplength=640, justify="left", anchor="w")
        self.etiqueta_aviso.pack(anchor="w", fill="x", pady=(4, 0))
        self.etiqueta_historial = tk.Label(marco, text="", font=FUENTE, wraplength=640, justify="left", anchor="nw")
        self.etiqueta_historial.pack(anchor="w", fill="x")
        self.recargar()

    def recargar(self) -> None:
        estado = None if self.filtro.get() == FILTROS[0] else self.filtro.get()
        try:
            store = Store(self.principal.cfg["salida"]["base_datos"])
            try:
                filas = store.alertas_decididas(estado)
            finally:
                store.con.close()
        except sqlite3.OperationalError:
            self.etiqueta_aviso.config(text=BASE_OCUPADA, fg=ROJO)
            return
        seleccion = [i for i in self.tabla.selection()]
        self.tabla.delete(*self.tabla.get_children())
        for a in filas:
            self.tabla.insert(
                "",
                "end",
                iid=str(a["id"]),
                values=(
                    a["estado"],
                    str(a["validada_en"] or "")[:16].replace("T", " "),
                    a["validada_por"] or "",
                    a["radicado"],
                    a["actuacion"] or "",
                ),
            )
        conservadas = [i for i in seleccion if self.tabla.exists(i)]
        if conservadas:
            self.tabla.selection_set(conservadas)
        self.mostrar_historial()

    def mostrar_historial(self) -> None:
        seleccion = self.tabla.selection()
        lineas = []
        if len(seleccion) == 1:
            try:
                store = Store(self.principal.cfg["salida"]["base_datos"])
                try:
                    cambios = store.historial(int(seleccion[0]))
                finally:
                    store.con.close()
            except sqlite3.OperationalError:
                self.etiqueta_aviso.config(text=BASE_OCUPADA, fg=ROJO)
                return
            lineas = [
                f"{str(c['momento'])[:16].replace('T', ' ')} · {c['usuario']} · "
                f"{c['estado_anterior']} → {c['estado_nuevo']} ({c['origen']})"
                for c in cambios
            ]
        self.etiqueta_historial.config(text="\n".join(lineas))

    def corregir(self, estado: str) -> int:
        """Pasa las alertas seleccionadas a `estado`. Devuelve cuántas cambiaron."""
        ids = [int(i) for i in self.tabla.selection()]
        if not ids:
            self.etiqueta_aviso.config(text=SIN_SELECCION, fg=ROJO)
            return 0
        try:
            cambiadas = self.principal._decidir(ids, estado)
        except sqlite3.OperationalError:
            self.etiqueta_aviso.config(text=BASE_OCUPADA, fg=ROJO)
            return 0
        self.etiqueta_aviso.config(text="")
        self.recargar()
        self.principal.recargar_alertas()
        return cambiadas


def abrir(ruta_config) -> int:
    cfg = cargar_config(ruta_config)
    raiz = tk.Tk()
    v = Ventana(raiz, cfg)
    v.sondear()
    raiz.mainloop()
    return 0
