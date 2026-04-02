"""
Módulo 1 — Extractor de datos desde facturas de exportación en PDF.
Usa pdfplumber + regex para leer dinámicamente los campos clave.
"""

import re
import pdfplumber


def extraer_datos_factura(ruta_pdf: str) -> dict:
    """
    Abre un PDF de factura de exportación y extrae 5 campos clave.

    Retorna un diccionario con las claves:
        incoterm    — ej. CFR, CPT, FOB
        moneda      — ej. USD, CNY
        total       — monto numérico final (string tal como aparece en el PDF)
        destinatario — nombre de la empresa compradora
        direccion   — dirección del destinatario
    """
    with pdfplumber.open(ruta_pdf) as pdf:
        texto = "\n".join(
            pagina.extract_text() or "" for pagina in pdf.pages
        )

    # ── Incoterm ─────────────────────────────────────────────────────────────
    # Aparece después de "CLÁUSULA DE VENTA :" o "INCOTERMS :"
    incoterm = None
    for patron in [
        r"CL[AÁ]USULA\s+DE\s+VENTA\s*:\s*([A-Z]{2,5})",
        r"INCOTERMS\s*:\s*([A-Z]{2,5})",
    ]:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            incoterm = m.group(1).strip()
            break

    # ── Moneda ────────────────────────────────────────────────────────────────
    # Aparece después de "TIPO DE MONEDA :" o "CURRENCY :"
    moneda = None
    for patron in [
        r"TIPO\s+DE\s+MONEDA\s*:\s*([A-Z]{3})",
        r"CURRENCY\s*:\s*([A-Z]{3})",
    ]:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            moneda = m.group(1).strip()
            break

    # ── Total ─────────────────────────────────────────────────────────────────
    # Aparece como "TOTAL <INCOTERM> : <monto>"  ej. "TOTAL CPT : 109.648,80"
    total = None
    m = re.search(
        r"TOTAL\s+[A-Z]{2,5}\s*:\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    if m:
        total = m.group(1).strip()

    # ── Destinatario ──────────────────────────────────────────────────────────
    # Aparece en la misma línea que "SEÑOR(ES) / MESSRS :", antes de "FECHA"
    destinatario = None
    m = re.search(
        r"SE[ÑN]OR\(ES\)\s*/\s*MESSRS\s*:\s*(.+?)\s+FECHA",
        texto,
        re.IGNORECASE,
    )
    if m:
        destinatario = m.group(1).strip()

    # ── Dirección ─────────────────────────────────────────────────────────────
    # Captura todo el bloque multilínea desde "DIRECCIÓN / ADDRESS :" hasta
    # "GIRO :" (o "CIUDAD / CITY :" como fallback).
    # "TRANSPORTE / TRANSPORT : <nro>" aparece mezclado en la primera línea
    # del bloque y se elimina antes de limpiar.
    direccion = None
    for fin in [r"GIRO\s*:", r"CIUDAD\s*/\s*CITY\s*:"]:
        m = re.search(
            rf"DIRECCI[OÓ]N\s*/\s*ADDRESS\s*:\s*(.*?)\s*{fin}",
            texto,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            bloque = m.group(1)
            # Quitar el fragmento "TRANSPORTE / TRANSPORT : <número>" intercalado
            bloque = re.sub(
                r"TRANSPORTE\s*/\s*TRANSPORT\s*:\s*\S+", "", bloque, flags=re.IGNORECASE
            )
            direccion = re.sub(r"\s+", " ", bloque).strip()
            break

    return {
        "incoterm": incoterm,
        "moneda": moneda,
        "total": total,
        "destinatario": destinatario,
        "direccion": direccion,
    }


# ── Bloque de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    BASE = os.path.join(os.path.dirname(__file__), "pdfs_prueba")
    facturas = [
        "factura_agrosuper.pdf",
        "factura_bb.pdf",
    ]

    for nombre in facturas:
        ruta = os.path.join(BASE, nombre)
        print(f"\n{'─' * 55}")
        print(f"  Factura : {nombre}")
        print(f"{'─' * 55}")
        datos = extraer_datos_factura(ruta)
        for clave, valor in datos.items():
            print(f"  {clave:<15}: {valor}")
    print()
