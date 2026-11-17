import itertools
import sqlite3
from datetime import date, datetime, time, timedelta

import pytest

# En Linux sin librerías gráficas el import falla con ImportError, no con ModuleNotFoundError
tk = pytest.importorskip("tkinter", exc_type=ImportError)

import consultor.main as main_mod  # noqa: E402
from consultor.bloqueo import Bloqueo  # noqa: E402
from consultor.models import CONFIRMADA, DESCARTADA, PENDIENTE, POSIBLE_NOVEDAD, Veredicto  # noqa: E402
from consultor.reporter import ENLACE_PORTAL  # noqa: E402
from consultor.store import Store  # noqa: E402
from consultor.ventana import Ventana  # noqa: E402
from tests.test_main import R1, preparar  # noqa: E402
from tests.utiles import act, ok  # noqa: E402

HOY = date(2026, 11, 13)
RADICADO = R1.radicado
_ACTUACIONES = itertools.count(1000)  # id_reg_actuacion únicos entre llamadas a _con_alertas


@pytest.fixture(scope="session")
def _tk_unico():
    # Crear y destruir varios Tk() en un mismo proceso falla de forma intermitente en Windows.
    # Se crea uno para toda la sesión de pruebas, como hace la aplicación real.
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"sin entorno gráfico: {e}")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def raiz(_tk_unico):
    ventana = tk.Toplevel(_tk_unico)
    ventana.withdraw()
    yield ventana
    ventana.destroy()


def _cfg(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    return main_mod.cargar_config(args[args.index("--config") + 1])


def test_sin_consultas_previas_muestra_el_texto_inicial_y_habilita_el_boton(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.refrescar()
    assert "Todavía no se ha hecho ninguna consulta" in v.etiqueta_resumen.cget("text")
    assert str(v.boton_consultar.cget("state")) == "normal"


def test_con_otro_ciclo_corriendo_muestra_el_avance_y_deshabilita_el_boton(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg)
        v.refrescar()
        assert "12 de 44" in v.etiqueta_avance.cget("text")
        assert float(v.barra["value"]) == 12 and float(v.barra["maximum"]) == 44
        assert str(v.boton_consultar.cget("state")) == "disabled"


def test_consultar_ahora_corre_en_un_hilo_y_muestra_el_resultado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "terminada" in v.etiqueta_estado.cget("text").lower()
    assert "1 consultados" in v.etiqueta_resumen.cget("text")


def test_si_el_ciclo_es_rechazado_se_muestra_el_mensaje(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    main_mod.ejecutar_ciclo(cfg)  # deja un ciclo reciente: el siguiente será rechazado por el límite
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "espera hasta las" in v.etiqueta_estado.cget("text")


def _estado(w):
    return str(w.cget("state"))


def test_sin_ciclo_el_boton_cancelar_esta_deshabilitado(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch), confirmar=lambda: True)
    v.refrescar()
    assert _estado(v.boton_cancelar) == "disabled"


def test_con_ciclo_el_boton_cancelar_esta_habilitado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: True)
        v.refrescar()
        assert _estado(v.boton_cancelar) == "normal"


def test_si_no_se_confirma_no_se_pide_cancelar(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: False)
        v.refrescar()
        v.boton_cancelar.invoke()
        assert not (tmp_path / "datos" / "cancelar.txt").exists()


def test_al_confirmar_se_crea_cancelar_txt_y_se_avisa(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: True)
        v.refrescar()
        v.boton_cancelar.invoke()
        assert (tmp_path / "datos" / "cancelar.txt").exists()
        assert "Cancelando" in v.etiqueta_estado.cget("text")
        assert _estado(v.boton_cancelar) == "disabled"


def test_si_el_ciclo_ya_termino_se_dice_que_no_hay_consulta(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch), confirmar=lambda: True)
    v.cancelar()
    assert "No hay ninguna consulta en curso" in v.etiqueta_estado.cget("text")
    assert not (tmp_path / "datos" / "cancelar.txt").exists()


def test_un_estado_viejo_sin_candado_no_habilita_cancelar_ni_bloquea_consultar(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    (tmp_path / "datos").mkdir(exist_ok=True)
    (tmp_path / "datos" / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    v = Ventana(raiz, cfg, confirmar=lambda: True)
    v.refrescar()
    assert _estado(v.boton_cancelar) == "disabled"
    assert _estado(v.boton_consultar) == "normal"


def test_la_ventana_muestra_los_dias_actuales(raiz, tmp_path, monkeypatch):
    from consultor.ajustes import guardar_dias

    cfg = _cfg(tmp_path, monkeypatch)
    guardar_dias(tmp_path / "datos", 12)
    v = Ventana(raiz, cfg)
    assert v.dias.get() == "12"


def test_cambiar_los_dias_en_la_ventana_los_guarda(raiz, tmp_path, monkeypatch):
    from consultor.ajustes import leer_dias

    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.dias.set("3")
    v.guardar_dias()
    assert leer_dias(tmp_path / "datos") == 3
    assert "Guardado" in v.etiqueta_ajuste.cget("text")


def test_un_valor_invalido_no_se_guarda_y_se_vuelve_al_anterior(raiz, tmp_path, monkeypatch):
    from consultor.ajustes import guardar_dias, leer_dias

    cfg = _cfg(tmp_path, monkeypatch)
    guardar_dias(tmp_path / "datos", 5)
    v = Ventana(raiz, cfg)
    v.dias.set("abc")
    v.guardar_dias()
    assert leer_dias(tmp_path / "datos") == 5
    assert v.dias.get() == "5"
    assert "entre 0 y 365" in v.etiqueta_ajuste.cget("text")


def test_si_refrescar_falla_la_ventana_lo_dice_y_sigue_sondeando(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    programados = []
    monkeypatch.setattr(v.raiz, "after", lambda ms, fn: programados.append(ms))

    def falla():
        raise RuntimeError("base dañada")

    monkeypatch.setattr(v, "refrescar", falla)
    v.sondear()
    assert "No se pudo actualizar" in v.etiqueta_estado.cget("text")
    assert programados == [1000]  # sigue sondeando


def test_si_el_refresco_se_recupera_la_ventana_limpia_el_aviso(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    monkeypatch.setattr(v.raiz, "after", lambda ms, fn: None)

    def falla():
        raise RuntimeError("base dañada")

    monkeypatch.setattr(v, "refrescar", falla)
    v.sondear()
    assert "No se pudo actualizar" in v.etiqueta_estado.cget("text")
    monkeypatch.setattr(v, "refrescar", lambda: None)
    v.sondear()
    assert v.etiqueta_estado.cget("text") == ""


def test_apagar_desde_la_ventana_guarda_el_interruptor_y_bloquea_consultar(raiz, tmp_path, monkeypatch):
    from consultor.ajustes import consultas_activas

    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.refrescar()
    assert _estado(v.boton_consultar) == "normal"
    v.boton_encendido.invoke()
    v.refrescar()
    assert not consultas_activas(tmp_path / "datos")
    assert _estado(v.boton_consultar) == "disabled"
    assert "APAGADAS" in v.etiqueta_encendido.cget("text")
    v.boton_encendido.invoke()
    v.refrescar()
    assert consultas_activas(tmp_path / "datos") and _estado(v.boton_consultar) == "normal"


def _con_alertas(cfg, hoy: int = 0, hace_20_dias: int = 0) -> list[int]:
    """Crea alertas Pendiente detectadas HOY y hace 20 días. Devuelve los ids, primero las de hoy."""
    store = Store(cfg["salida"]["base_datos"])
    try:
        store.registrar_radicado(R1)
        ids = []
        for cantidad, dia in ((hoy, HOY), (hace_20_dias, HOY - timedelta(days=20))):
            if not cantidad:
                continue
            momento = datetime.combine(dia, time(10, 0))
            numeros = [next(_ACTUACIONES) for _ in range(cantidad)]
            nuevas = tuple(act(n, fecha="2026-11-10", texto=f"Actuación {n}", anotacion=f"Anotación {n}") for n in numeros)
            ciclo = store.iniciar_ciclo(momento)
            store.registrar_resultado(
                ciclo, RADICADO, ok(*nuevas), Veredicto(POSIBLE_NOVEDAD, nuevas=nuevas), "", momento
            )
            store.cerrar_ciclo(ciclo, "Completo", momento)
            ids += [f["id"] for f in store.con.execute("SELECT id FROM alerta WHERE ciclo_id = ? ORDER BY id", (ciclo,))]
        return ids
    finally:
        store.con.close()


def _decidir(cfg, ids, estado=CONFIRMADA) -> None:
    store = Store(cfg["salida"]["base_datos"])
    try:
        store.decidir(ids, estado, "Alisson", datetime.now())
    finally:
        store.con.close()


def _ventana(raiz, cfg, **k):
    v = Ventana(raiz, cfg, hoy=lambda: HOY, **k)
    v.raiz.after = lambda ms, fn: None  # sondear no queda programado sobre una ventana que se destruye
    return v


def test_las_pestanas_separan_rango_y_anteriores(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2, hace_20_dias=3)
    v = _ventana(raiz, cfg)
    v.recargar_alertas()
    assert len(v.tabla_rango.get_children()) == 2 and len(v.tabla_anteriores.get_children()) == 3
    assert v.pestanas.tab(0, "text") == "Por decidir · últimos 7 días (2)"
    assert v.pestanas.tab(1, "text") == "Anteriores sin decidir (3)"
    marca, detectada, radicado, fecha, actuacion = v.tabla_rango.item(str(ids[0]), "values")
    assert (marca, detectada, fecha) == ("☐", "13-nov", "10-nov")
    assert RADICADO.endswith(radicado.lstrip("…"))
    assert v.tabla_anteriores.item(str(ids[2]), "values")[1] == "24-oct"


def test_la_ventana_carga_las_alertas_al_abrir(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=1)
    v = _ventana(raiz, cfg)
    assert len(v.tabla_rango.get_children()) == 1


def test_marcar_alterna_la_casilla(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.alternar_marca(ids[0])
    assert v.marcadas == {ids[0]} and v.tabla_rango.item(str(ids[0]), "values")[0] == "☑"
    v.alternar_marca(ids[0])
    assert v.marcadas == set() and v.tabla_rango.item(str(ids[0]), "values")[0] == "☐"


def test_seleccionar_todas_alterna_con_quitar_seleccion(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2, hace_20_dias=1)
    v = _ventana(raiz, cfg)
    v.seleccionar_todas()
    assert v.marcadas == set(ids[:2]) and v.boton_todas.cget("text") == "Quitar selección"
    v.seleccionar_todas()
    assert v.marcadas == set() and v.boton_todas.cget("text") == "Seleccionar todas"


def test_seleccionar_todas_y_confirmar_deja_la_pestana_al_dia(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2, hace_20_dias=1)
    v = _ventana(raiz, cfg)
    v.recargar_alertas()
    v.seleccionar_todas()
    assert v.aplicar(CONFIRMADA) == 2
    assert v.tabla_rango.get_children() == () and "Al día ✓" in v.etiqueta_alertas.cget("text")
    assert v.pestanas.tab(0, "text") == "Por decidir · últimos 7 días (0)"
    assert v.marcadas == set()
    store = Store(cfg["salida"]["base_datos"])
    try:
        assert [(h["estado_nuevo"], h["usuario"], h["origen"]) for h in store.historial(ids[0])] == [
            (CONFIRMADA, "Alisson", "ventana")
        ]
    finally:
        store.con.close()


def test_mas_de_cinco_pide_confirmacion_y_si_no_se_confirma_no_cambia(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=6)
    preguntas = []
    v = _ventana(raiz, cfg, preguntar=lambda t, x: preguntas.append(x) or False)
    v.recargar_alertas()
    v.seleccionar_todas()
    assert v.aplicar(DESCARTADA) == 0 and preguntas == ["¿Descartar 6 alertas? Se puede corregir desde Ver decididas."]
    assert len(v.tabla_rango.get_children()) == 6 and len(v.marcadas) == 6


def test_cinco_o_menos_no_pide_confirmacion(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=5)
    preguntas = []
    v = _ventana(raiz, cfg, preguntar=lambda t, x: preguntas.append(x) or False)
    v.seleccionar_todas()
    assert v.aplicar(DESCARTADA) == 5 and preguntas == []


def test_sin_seleccion_avisa_y_no_cambia(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    assert v.aplicar(CONFIRMADA) == 0
    assert v.etiqueta_alertas.cget("text") == "Seleccione al menos una alerta."
    assert len(v.tabla_rango.get_children()) == 2


def test_con_la_base_ocupada_avisa_y_conserva_la_seleccion(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.seleccionar_todas()
    otra = sqlite3.connect(cfg["salida"]["base_datos"], timeout=0)
    otra.execute("BEGIN EXCLUSIVE")
    try:
        assert v.aplicar(CONFIRMADA) == 0
        assert v.etiqueta_alertas.cget("text") == (
            "La base está ocupada por una consulta; intente de nuevo en unos segundos."
        )
        assert len(v.marcadas) == 2
    finally:
        otra.rollback()
        otra.close()
    assert v.aplicar(CONFIRMADA) == 2  # libre la base, la misma selección se aplica


def test_el_refresco_de_cada_segundo_no_borra_las_marcas(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.alternar_marca(ids[0])
    v.sondear()
    assert v.marcadas == {ids[0]}


def test_sondear_solo_recarga_cuando_termina_otro_ciclo(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.alternar_marca(ids[0])
    v.sondear()
    v.sondear()
    _decidir(cfg, [ids[1]])  # otro equipo decide, sin ciclo nuevo: la lista no se repinta todavía
    v.sondear()
    assert len(v.tabla_rango.get_children()) == 2
    nuevas = _con_alertas(cfg, hoy=1)  # termina otro ciclo
    v.sondear()
    assert set(v.tabla_rango.get_children()) == {str(ids[0]), str(nuevas[0])}
    assert v.marcadas == {ids[0]}


def test_al_recargar_se_sueltan_las_marcas_de_alertas_que_ya_no_estan(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.seleccionar_todas()
    _decidir(cfg, [ids[1]])
    v.recargar_alertas()
    assert v.marcadas == {ids[0]}


def test_guardar_dias_recarga_las_pestanas_y_explica_las_dos_cosas(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=2, hace_20_dias=3)
    v = _ventana(raiz, cfg)
    v.dias.set("30")
    v.guardar_dias()
    assert len(v.tabla_rango.get_children()) == 5
    assert "La pestaña Por decidir ya muestra los últimos 30 días" in v.etiqueta_ajuste.cget("text")
    assert v.pestanas.tab(1, "text") == "Anteriores sin decidir (0)"


def test_guardar_cero_dias_dice_que_solo_muestra_hoy(raiz, tmp_path, monkeypatch):
    v = _ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.dias.set("0")
    v.guardar_dias()
    assert v.etiqueta_ajuste.cget("text") == (
        "Guardado: 0 días. No se avisará nada en radicados nuevos; Por decidir muestra solo lo detectado hoy."
    )
    assert v.pestanas.tab(0, "text") == "Por decidir · hoy (0)"


def test_el_detalle_muestra_la_fila_enfocada(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=1)
    v = _ventana(raiz, cfg)
    v.tabla_rango.focus(str(ids[0]))
    v.mostrar_detalle()
    texto = v.texto_detalle()
    actuacion = v.tabla_rango.item(str(ids[0]), "values")[4]
    numero = actuacion.split()[-1]
    assert RADICADO in texto and "JUZGADO 077" in texto and actuacion in texto and f"Anotación {numero}" in texto


def test_abrir_en_el_portal_copia_el_radicado(raiz, tmp_path, monkeypatch):
    abiertos = []
    monkeypatch.setattr("webbrowser.open", abiertos.append)
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=1)
    v = _ventana(raiz, cfg)
    v.tabla_rango.focus(str(ids[0]))
    v.abrir_portal()
    assert abiertos == [ENLACE_PORTAL] and raiz.clipboard_get() == RADICADO
    assert v.etiqueta_alertas.cget("text") == "Radicado copiado"


def test_la_ventana_cabe_en_una_pantalla_de_768_px(raiz, tmp_path, monkeypatch):
    # 1366×768 con barra de tareas y título deja ~700 px; se reservan 25 px para el aviso rojo de la Task 6.
    escala = raiz.tk.call("tk", "scaling")
    raiz.tk.call("tk", "scaling", 1.33)  # = Windows al 100 %
    try:
        cfg = _cfg(tmp_path, monkeypatch)
        ids = _con_alertas(cfg, hoy=8, hace_20_dias=3)
        con = sqlite3.connect(cfg["salida"]["base_datos"])
        with con:
            con.execute("UPDATE actuacion SET anotacion = ?", ("Texto largo de la anotación. " * 40,))
        con.close()
        v = _ventana(raiz, cfg)
        v.refrescar()
        v.tabla_rango.focus(str(ids[0]))
        v.mostrar_detalle()
        raiz.update_idletasks()
        assert "Texto largo" in v.texto_detalle()
        assert raiz.winfo_reqheight() <= 700 - 25
    finally:
        raiz.tk.call("tk", "scaling", escala)


def test_corregir_una_descartada_a_pendiente_la_devuelve_a_la_lista(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=2)
    v = _ventana(raiz, cfg)
    v.seleccionar_todas()
    v.aplicar(DESCARTADA)
    d = v.ver_decididas()
    try:
        d.tabla.selection_set(str(ids[0]))
        assert d.corregir(PENDIENTE) == 1
        assert str(ids[0]) in v.tabla_rango.get_children()
        assert str(ids[0]) not in d.tabla.get_children()
    finally:
        d.ventana.destroy()


def test_filtrar_decididas_y_ver_historial(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=3)
    confirmadas, descartada = ids[:2], ids[2:]
    _decidir(cfg, confirmadas, CONFIRMADA)
    _decidir(cfg, descartada, DESCARTADA)
    v = _ventana(raiz, cfg)
    d = v.ver_decididas()
    try:
        assert len(d.tabla.get_children()) == 3
        d.filtro.set("Confirmada")
        d.recargar()
        assert set(d.tabla.get_children()) == {str(i) for i in confirmadas}
        d.tabla.selection_set(str(confirmadas[0]))
        d.tabla.event_generate("<<TreeviewSelect>>")
        raiz.update()
        assert "Pendiente → Confirmada" in d.etiqueta_historial.cget("text")
        assert "(ventana)" in d.etiqueta_historial.cget("text")
    finally:
        d.ventana.destroy()


def test_corregir_sin_seleccion_avisa_y_no_cambia_nada(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _decidir(cfg, _con_alertas(cfg, hoy=1))
    v = _ventana(raiz, cfg)
    d = v.ver_decididas()
    try:
        assert d.corregir(DESCARTADA) == 0
        assert d.etiqueta_aviso.cget("text") == "Seleccione al menos una alerta."
    finally:
        d.ventana.destroy()


def test_ver_decididas_dos_veces_no_apila_ventanas(raiz, tmp_path, monkeypatch):
    v = _ventana(raiz, _cfg(tmp_path, monkeypatch))
    d = v.ver_decididas()
    try:
        assert v.ver_decididas() is d
    finally:
        d.ventana.destroy()
    assert v.ver_decididas() is not d
    v.decididas.ventana.destroy()


def test_corregir_con_la_base_ocupada_avisa(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    ids = _con_alertas(cfg, hoy=1)
    _decidir(cfg, ids)
    v = _ventana(raiz, cfg)
    d = v.ver_decididas()
    try:
        d.tabla.selection_set(str(ids[0]))

        def ocupada(*a):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(v, "_decidir", ocupada)
        assert d.corregir(DESCARTADA) == 0
        assert "ocupada" in d.etiqueta_aviso.cget("text")
    finally:
        d.ventana.destroy()


def _cerrar_ventana(raiz, cfg, preguntar=None, informar=None):
    cerradas, avisos, preguntas = [], [], []
    v = _ventana(
        raiz,
        cfg,
        preguntar=preguntar or (lambda t, x: preguntas.append(x) or True),
        informar=lambda t, x: avisos.append(x),
        cerrar=lambda: cerradas.append(1),
    )
    v.recargar_alertas()
    return v, cerradas, avisos, preguntas


def _con_regla(cfg):
    cfg["alertas"] = {"exigir_puesta_al_dia": True}


def test_cerrar_sin_pendientes_cierra(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    v, cerradas, avisos, preguntas = _cerrar_ventana(raiz, cfg)
    assert v.al_cerrar() == "cerrada" and cerradas and not avisos and not preguntas


def test_cerrar_con_pendientes_pregunta_y_respeta_la_respuesta(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hoy=3)
    v, cerradas, _, preguntas = _cerrar_ventana(raiz, cfg, preguntar=lambda t, x: False)
    assert v.al_cerrar() == "cancelada" and not cerradas
    v2, cerradas2, _, preguntas2 = _cerrar_ventana(raiz, cfg)
    assert v2.al_cerrar() == "cerrada" and cerradas2
    assert preguntas2 == ["Quedan 3 alertas por decidir de los últimos 7 días. ¿Cerrar de todas formas?"]


def test_regla_apagada_no_bloquea_aunque_haya_44_anteriores(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_alertas(cfg, hace_20_dias=44)
    v, cerradas, avisos, _ = _cerrar_ventana(raiz, cfg)
    assert v.al_cerrar() == "cerrada" and cerradas and not avisos
    assert not v.etiqueta_obligacion.winfo_ismapped() and not v.etiqueta_obligacion.winfo_manager()


def test_regla_encendida_bloquea_hasta_bajar_de_10_y_sobrevive_a_reabrir(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_regla(cfg)
    ids = _con_alertas(cfg, hace_20_dias=44)
    v, cerradas, avisos, _ = _cerrar_ventana(raiz, cfg)
    assert v.al_cerrar() == "bloqueada" and not cerradas
    assert "Faltan 35." in v.etiqueta_obligacion.cget("text")
    assert avisos and "Faltan 35." in avisos[0]
    assert v.pestanas.index("current") == 1
    _decidir(cfg, ids[:20])  # quedan 24: sigue activa aunque sea < 30
    v2, cerradas2, _, _ = _cerrar_ventana(raiz, cfg)
    assert v2.al_cerrar() == "bloqueada"
    _decidir(cfg, ids[20:35])  # quedan 9
    v2.recargar_alertas()
    assert v2.al_cerrar() == "cerrada" and cerradas2
    assert not v2.etiqueta_obligacion.winfo_manager()


def test_la_regla_usa_su_propio_corte_y_no_el_campo_de_dias(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_regla(cfg)
    _con_alertas(cfg, hace_20_dias=44)
    v, _, _, _ = _cerrar_ventana(raiz, cfg)
    v.dias.set("365")
    v.guardar_dias()  # las 44 pasan a Por decidir, pero para la regla siguen siendo anteriores
    assert v.al_cerrar() == "bloqueada"


def test_con_consulta_en_curso_el_cierre_sigue_las_mismas_reglas(raiz, tmp_path, monkeypatch):
    import threading

    cfg = _cfg(tmp_path, monkeypatch)
    _con_regla(cfg)
    _con_alertas(cfg, hace_20_dias=44)
    v, cerradas, _, _ = _cerrar_ventana(raiz, cfg)
    parar = threading.Event()
    v.hilo = threading.Thread(target=parar.wait, daemon=True)
    v.hilo.start()
    try:
        assert v.al_cerrar() == "bloqueada" and not cerradas
    finally:
        parar.set()
        v.hilo.join()


def test_consultar_ahora_no_se_bloquea_con_la_obligacion_activa(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_regla(cfg)
    _con_alertas(cfg, hace_20_dias=44)
    v, _, _, _ = _cerrar_ventana(raiz, cfg)
    v.refrescar()
    assert v.obligacion and str(v.boton_consultar.cget("state")) == "normal"


def test_base_ocupada_al_fijar_la_obligacion_no_rompe_y_conserva_el_estado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _con_regla(cfg)
    _con_alertas(cfg, hace_20_dias=44)
    v, _, _, _ = _cerrar_ventana(raiz, cfg)
    assert v.obligacion

    def ocupada(self, activa):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(Store, "fijar_obligacion", ocupada)
    v.recargar_alertas()
    assert v.obligacion and v.al_cerrar() == "bloqueada"


def test_con_el_aviso_rojo_visible_la_ventana_sigue_cabiendo_en_700_px(raiz, tmp_path, monkeypatch):
    escala = raiz.tk.call("tk", "scaling")
    raiz.tk.call("tk", "scaling", 1.33)
    try:
        cfg = _cfg(tmp_path, monkeypatch)
        _con_regla(cfg)
        _con_alertas(cfg, hoy=8, hace_20_dias=44)
        v, _, _, _ = _cerrar_ventana(raiz, cfg)
        raiz.update_idletasks()
        assert v.etiqueta_obligacion.winfo_manager() == "pack"
        assert raiz.winfo_reqheight() <= 700
    finally:
        raiz.tk.call("tk", "scaling", escala)
