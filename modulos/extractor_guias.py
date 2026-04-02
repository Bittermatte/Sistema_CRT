"""
Módulo 2 — Extractor de datos desde Guías de Despacho Electrónica en PDF.
Usa pdfplumber + regex para leer el detalle de la carga logística.
"""

import re
import pdfplumber


def _limpiar_numero(valor: str) -> float:
    """
    Convierte un número en formato chileno (1.827,48) a float (1827.48).
    Elimina los puntos de miles y reemplaza la coma decimal por punto.
    """
    return float(valor.replace(".", "").replace(",", "."))


def extraer_datos_guia(ruta_pdf: str) -> dict:
    """
    Abre un PDF de Guía de Despacho y extrae 5 campos logísticos clave.

    Retorna un diccionario con las claves:
        numero_guia  — número de la guía (int)
        bultos       — cantidad de bultos (int)
        peso_neto    — peso neto en kg (float)
        peso_bruto   — peso bruto en kg (float)
        productos    — bloque de texto de la tabla de productos (str)
    """
    with pdfplumber.open(ruta_pdf) as pdf:
        texto = "\n".join(
            pagina.extract_text() or "" for pagina in pdf.pages
        )

    # ── N° Guía ───────────────────────────────────────────────────────────────
    # Aparece como "Nº 497318" después del encabezado "GUIA DE DESPACHO ... ELECTRONICA"
    numero_guia = None
    m = re.search(r"N[°º]\s+(\d+)\s*\n\s*S\.I\.I\.", texto, re.IGNORECASE)
    if m:
        numero_guia = int(m.group(1))

    # ── Bultos ────────────────────────────────────────────────────────────────
    # "CANTIDAD DE BULTOS : 90 Son:"
    bultos = None
    m = re.search(
        r"CANTIDAD\s+DE\s+BULTOS\s*:\s*([\d.,]+)\s+Son:",
        texto,
        re.IGNORECASE,
    )
    if m:
        bultos = int(_limpiar_numero(m.group(1)))

    # ── Peso Neto ─────────────────────────────────────────────────────────────
    # "PESO NETO : 1.827,48 Son:"
    peso_neto = None
    m = re.search(
        r"PESO\s+NETO\s*:\s*([\d.,]+)\s+Son:",
        texto,
        re.IGNORECASE,
    )
    if m:
        peso_neto = _limpiar_numero(m.group(1))

    # ── Peso Bruto ────────────────────────────────────────────────────────────
    # "PESO BRUTO : 2.189,19 Son:"
    peso_bruto = None
    m = re.search(
        r"PESO\s+BRUTO\s*:\s*([\d.,]+)\s+Son:",
        texto,
        re.IGNORECASE,
    )
    if m:
        peso_bruto = _limpiar_numero(m.group(1))

    # ── Patentes (tracto y semi) ──────────────────────────────────────────────
    # El bloque entre "CAMIÓN PATENTE" y "HORA LLEGADA" contiene ambas placas
    # en formato chileno AA999AA. La primera es el tracto, la segunda el semi.
    patente_tracto = patente_semi = None
    m = re.search(
        r"CAM[IÍ][OÓ]N\s+PATENTE(.*?)HORA\s+LLEGADA",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        placas = re.findall(r"\b([A-Z]{2}\d{3}[A-Z]{2})\b", m.group(1))
        patente_tracto = placas[0] if len(placas) > 0 else None
        patente_semi   = placas[1] if len(placas) > 1 else None

    # ── Productos ─────────────────────────────────────────────────────────────
    # Captura el bloque entre la fila de encabezados de la tabla y el pie
    # "No constituye Venta." (o "TOTAL :" como fallback).
    productos = None
    for fin in [r"No\s+constituye\s+Venta\.", r"TOTAL\s*:"]:
        m = re.search(
            rf"CODIGO\s+PRODUCTOS\s+KILOS\s+CAJAS\s+P\.\s*UNITARIO\s+TOTAL\s*(.*?)\s*{fin}",
            texto,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            bloque = m.group(1)
            # Colapsar saltos de línea en espacios y limpiar bordes
            productos = re.sub(r"\s*\n\s*", " | ", bloque.strip())
            break

    return {
        "numero_guia": numero_guia,
        "bultos": bultos,
        "peso_neto": peso_neto,
        "peso_bruto": peso_bruto,
        "patente_tracto": patente_tracto,
        "patente_semi": patente_semi,
        "productos": agrupar_familias_aquachile(productos) if productos else [],
    }


def agrupar_familias_aquachile(texto_bruto: str) -> list:
    """
    Recibe el bloque de texto de la tabla de productos (separado por ' | ')
    y agrupa las líneas por familia, sumando cajas y kilos.

    Familias reconocidas:
        - 'ENTERO SIN VISCERAS/HON'  → líneas que contienen esa cadena
        - 'FILETE Premium'           → líneas que contienen 'FILETE'

    Retorna una lista de dicts:
        [{"familia": str, "cajas_totales": int, "kilos_totales": float}, ...]
    """
    acumulado: dict = {}
    familia_activa = None

    for segmento in texto_bruto.split(" | "):
        seg = segmento.strip()
        seg_upper = seg.upper()

        # ── Detectar a qué familia pertenece el siguiente bloque de datos ──
        if "ENTERO SIN VISCERAS" in seg_upper:
            familia_activa = "ENTERO SIN VISCERAS/HON"
        elif "FILETE" in seg_upper:
            familia_activa = "FILETE Premium"

        # ── Detectar fila de datos: "CODIGO SALMO SALAR <kilos> <cajas> ..." ─
        m = re.search(r"SALMO\s+SALAR\s+([\d.,]+)\s+(\d+)", seg, re.IGNORECASE)
        if m and familia_activa:
            kilos = _limpiar_numero(m.group(1))
            cajas = int(m.group(2))
            if familia_activa not in acumulado:
                acumulado[familia_activa] = {"kilos": 0.0, "cajas": 0}
            acumulado[familia_activa]["kilos"] += kilos
            acumulado[familia_activa]["cajas"] += cajas

    return [
        {
            "familia": fam,
            "cajas_totales": vals["cajas"],
            "kilos_totales": round(vals["kilos"], 2),
        }
        for fam, vals in acumulado.items()
    ]


# ── Bloque de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    BASE = os.path.join(os.path.dirname(__file__), "pdfs_prueba")
    guias = [
        "guia_agrosuper.pdf",
        "guia_bb.pdf",
    ]

    for nombre in guias:
        ruta = os.path.join(BASE, nombre)
        print(f"\n{'─' * 60}")
        print(f"  Guía : {nombre}")
        print(f"{'─' * 60}")
        datos = extraer_datos_guia(ruta)
        for clave, valor in datos.items():
            if clave == "productos":
                print(f"  {'productos':<15}:")
                for familia in valor:
                    print(
                        f"      {familia['familia']:<30}"
                        f"  cajas: {familia['cajas_totales']:>4}   "
                        f"kilos: {familia['kilos_totales']:>9.2f}"
                    )
            else:
                print(f"  {clave:<15}: {valor}")
    print()
