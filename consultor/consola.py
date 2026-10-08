def barra(hecho: int, total: int, ancho: int = 30) -> str:
    lleno = ancho if total == 0 else int(ancho * hecho / total)
    return f"[{'#' * lleno}{'-' * (ancho - lleno)}] {hecho}/{total}"
