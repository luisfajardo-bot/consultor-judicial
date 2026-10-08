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
