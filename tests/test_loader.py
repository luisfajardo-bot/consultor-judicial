import pytest
from openpyxl import Workbook

from consultor.loader import FuenteExcel, crear_fuente

ENC = ["Radicado", "Empresa", "Despacho", "Calidad", "Estado"]


def hacer_excel(ruta, filas, encabezado=ENC, hoja="GENERAL"):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append(encabezado)
    for f in filas:
        ws.append(f)
    wb.save(ruta)


def fuente(ruta, **extra):
    return FuenteExcel(
        ruta=ruta,
        hoja="GENERAL",
        col_radicado="Radicado",
        col_empresa="Empresa",
        col_despacho="Despacho",
        col_calidad="Calidad",
        col_estado="Estado",
        **extra,
    )


def test_lee_radicados_con_sus_datos(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [["11001400307720210114700", "ICEIN", "Juzgado 77", "Demandado", "Activo"]])
    r = fuente(ruta).cargar()[0]
    assert (r.radicado, r.empresa, r.despacho, r.calidad) == (
        "11001400307720210114700",
        "ICEIN",
        "Juzgado 77",
        "Demandado",
    )


def test_limpia_espacios_y_guiones_del_radicado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[" 11001-40-03-077-2021-01147-00 ", "ICEIN", "", "", "Activo"]])
    assert fuente(ruta).cargar()[0].radicado == "11001400307720210114700"


def test_duplicado_une_las_empresas(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
            ["11001400307720210114700", "COHERPA", "", "", "Activo"],
        ],
    )
    radicados = fuente(ruta).cargar()
    assert len(radicados) == 1
    assert radicados[0].empresa == "ICEIN / COHERPA"


def test_filas_vacias_se_saltan_pero_los_invalidos_se_conservan(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, None, None, None, None], ["123", "ICEIN", "", "", "Activo"]])
    radicados = fuente(ruta).cargar()
    assert [r.radicado for r in radicados] == ["123"]


def test_filtra_por_estado_si_se_configura(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
            ["11001400307720210114701", "ICEIN", "", "", "Cerrado"],
        ],
    )
    radicados = fuente(ruta, estados_incluidos=["activo"]).cargar()
    assert [r.radicado for r in radicados] == ["11001400307720210114700"]


def test_el_filtro_de_estado_acepta_variantes_que_empiezan_igual(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "", "", "", "ACTIVO"],
            ["11001400307720210114701", "", "", "", "ACTIVO -COBRO COSTAS"],
            ["11001400307720210114702", "", "", "", "  activo "],
            ["11001400307720210114703", "", "", "", "CERRADO"],
            ["11001400307720210114704", "", "", "", "CERRADO POR NO SER PARTE"],
            ["11001400307720210114705", "", "", "", None],
        ],
    )
    radicados = fuente(ruta, estados_incluidos=["ACTIVO"]).cargar()
    assert [r.radicado[-2:] for r in radicados] == ["00", "01", "02"]


def test_columna_inexistente_da_un_error_claro(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [], encabezado=["Otra"])
    with pytest.raises(ValueError, match="Radicado"):
        fuente(ruta).cargar()


def test_crear_fuente_excel_y_tipo_desconocido(tmp_path):
    cfg = {"tipo": "excel", "ruta": str(tmp_path / "x.xlsx"), "hoja": "GENERAL", "col_radicado": "Radicado"}
    assert isinstance(crear_fuente(cfg), FuenteExcel)
    with pytest.raises(ValueError, match="sql"):
        crear_fuente({"tipo": "sql"})


@pytest.mark.parametrize(
    "celda, esperados",
    [
        # dos radicados pegados sin separador (46 dígitos)
        (
            "0500131050232019005610005001310502320190056101",
            ["05001310502320190056100", "05001310502320190056101"],
        ),
        (
            "68081333300120210014100/TRIBUNAL68081333300120210014102",
            ["68081333300120210014100", "68081333300120210014102"],
        ),
        (
            "73001333300720220024300tribunal73001333300720220024301",
            ["73001333300720220024300", "73001333300720220024301"],
        ),
        (
            "68081333300220210021700SEGUNDAINSTANCIA68081333300220210021702",
            ["68081333300220210021700", "68081333300220210021702"],
        ),
        # un radicado con texto alrededor
        ("05266310500220230011400SEGUNDAINSTANCIAc", ["05266310500220230011400"]),
        ("otrojuzgado11001310303720250036100", ["11001310303720250036100"]),
        (
            "JUZGADO1CIVILDELCIRCUITODEITAGUI05360310300120260013800",
            ["05360310300120260013800"],
        ),
        # con separadores y texto
        ("Juzgado 1 Civil: 11001-40-03-077-2021-01147-00 (ver)", ["11001400307720210114700"]),
    ],
)
def test_saca_los_radicados_de_celdas_con_texto_o_pegados(tmp_path, celda, esperados):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[celda, "ICEIN", "", "", "Activo"]])
    assert [r.radicado for r in fuente(ruta).cargar()] == esperados


def test_dos_radicados_en_una_celda_comparten_los_datos_de_la_fila(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "OTRA", "", "", "Activo"],
            ["11001400307720210114700/TRIBUNAL11001400307720210114702", "ICEIN", "Juz", "Demandado", "Activo"],
        ],
    )
    por = {r.radicado: r for r in fuente(ruta).cargar()}
    assert list(por) == ["11001400307720210114700", "11001400307720210114702"]
    assert por["11001400307720210114700"].empresa == "OTRA / ICEIN"
    assert por["11001400307720210114702"].empresa == "ICEIN"


def test_sin_23_digitos_en_ninguna_parte_se_conserva_el_texto_limpio(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [["sin radicado 12-34", "ICEIN", "", "", "Activo"]])
    assert [r.radicado for r in fuente(ruta).cargar()] == ["sinradicado1234"]


@pytest.mark.parametrize(
    "celda",
    [
        "11001400307720210114700-2026",
        "11001400307720210114700.1",
        "11001400307720210114700 - 2",
        "11001400307720210114700 2026-01-15",
    ],
)
def test_un_radicado_pegado_a_otros_numeros_con_separador_se_conserva(tmp_path, celda):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[celda, "ICEIN", "", "", "Activo"]])
    assert [r.radicado for r in fuente(ruta).cargar()] == ["11001400307720210114700"]


def test_una_celda_numerica_se_marca_como_tal_y_no_como_un_numero_recortado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[1.10014003077202e22, "ICEIN", "", "", "Activo"]])
    (r,) = fuente(ruta).cargar()
    assert r.radicado.startswith("numérico:")


def test_cuenta_las_filas_con_datos_pero_sin_radicado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            [None, "ICEIN", "Juzgado 7", "", "Activo"],  # datos sin radicado
            [None, None, None, None, None],  # fila vacía: no cuenta
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
        ],
    )
    f = fuente(ruta)
    assert len(f.cargar()) == 1
    assert f.filas_sin_radicado == 1


def test_una_fila_sin_radicado_y_con_otro_estado_no_cuenta(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, "ICEIN", "", "", "Cerrado"]])
    f = fuente(ruta, estados_incluidos=["activo"])
    f.cargar()
    assert f.filas_sin_radicado == 0


R = "11001400307720210114700"
S = "05001310301520190045600"


@pytest.mark.parametrize(
    "celda, esperado",
    [
        ("11001-40-03-077-2021-01147-00 y " + S, {R, S}),
        (S + " y 11001-40-03-077-2021-01147-00", {R, S}),
        (R + "\n" + S[:-1], {R, S[:-1]}),
        (R + " / " + S + "1", {R, S + "1"}),
        (R + " 2026-01-15", {R}),
        (R + "-077", {R}),
        (R + ".1", {R}),
        ("11001-40-03-077-2021-01147-00-2026", {"110014003077202101147002026"}),
    ],
)
def test_una_celda_con_varios_radicados_no_pierde_ninguno(tmp_path, celda, esperado):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[celda, "ICEIN", "", "", "Activo"]])
    assert {r.radicado for r in fuente(ruta).cargar()} == esperado


def test_el_estado_no_cuenta_como_dato_de_una_fila_sin_radicado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, None, None, None, "Activo"]])
    f = fuente(ruta, estados_incluidos=["activo"])
    f.cargar()
    assert f.filas_sin_radicado == 0
    hacer_excel(ruta, [[None, None, "Juzgado 7", None, "Activo"]])
    f.cargar()
    assert f.filas_sin_radicado == 1


def test_filas_sin_radicado_se_reinicia_entre_cargas(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, "ICEIN", "", "", "Activo"]])
    f = fuente(ruta)
    f.cargar()
    assert f.filas_sin_radicado == 1
    hacer_excel(ruta, [[R, "ICEIN", "", "", "Activo"]])
    f.cargar()
    assert f.filas_sin_radicado == 0
