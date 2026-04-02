"""
calibrador.py — Ingeniería inversa de coordenadas para el Módulo 5.
Extrae posición X/Y (sistema ReportLab), tipografía y tamaño de palabras
clave en un CRT de referencia ya terminado.
"""

import os
import pdfplumber

RUTA_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "VESPRINI - CRT - 5098-BB (2).pdf")

PALABRAS_CLAVE = [
    "5098/2026VSP",
    "3.958,52",
    "874.00",
    "1812188",
    "AE296NK",
    "12.051.854-2",
]

def buscar_palabras(pagina, claves):
    """
    Extrae todas las palabras de la página y filtra las que coincidan
    (exacta o parcialmente) con alguna clave de búsqueda.
    Devuelve lista de dicts con x, y_reportlab, font, size y texto.
    """
    palabras = pagina.extract_words(extra_attrs=["fontname", "size"])
    altura   = pagina.height          # puntos PDF — para invertir el eje Y

    resultados = []
    for w in palabras:
        texto = w["text"]
        if any(clave.upper() in texto.upper() for clave in claves):
            resultados.append({
                "texto":       texto,
                "x":           round(w["x0"], 2),
                # ReportLab mide Y desde abajo → invertir usando 'bottom' (borde inferior del glifo)
                # page.height - bottom ≈ baseline de drawString en ReportLab
                "y_reportlab": round(altura - w["bottom"], 2),
                "font":        w.get("fontname", "N/A"),
                "size":        round(w.get("size", 0), 2),
            })
    return resultados


if __name__ == "__main__":
    print(f"\n{'═' * 62}")
    print(f"  CALIBRADOR DE COORDENADAS — CRT DE REFERENCIA")
    print(f"  {os.path.basename(RUTA_PDF)}")
    print(f"{'═' * 62}")

    with pdfplumber.open(RUTA_PDF) as pdf:
        pagina     = pdf.pages[0]
        encontrados = buscar_palabras(pagina, PALABRAS_CLAVE)

    if not encontrados:
        print("  ⚠  No se encontró ninguna de las palabras clave en la página 1.")
    else:
        print(f"\n  {'TEXTO':<22} {'X':>7}  {'Y (RL)':>7}  {'FONT':<28}  {'SIZE':>5}")
        print(f"  {'─'*22} {'─'*7}  {'─'*7}  {'─'*28}  {'─'*5}")
        for r in encontrados:
            print(
                f"  {r['texto']:<22} "
                f"{r['x']:>7.2f}  "
                f"{r['y_reportlab']:>7.2f}  "
                f"{r['font']:<28}  "
                f"{r['size']:>5.2f}"
            )

    print(f"\n{'═' * 62}\n")
