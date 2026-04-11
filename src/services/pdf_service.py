"""
Servicio PDF — Fase 1: overlay de datos sobre plantilla CRT vacía.

Estrategia: se usa pypdf para leer la plantilla base (crt_blanco.pdf) y
ReportLab para generar una capa transparente con los datos del formulario,
luego se fusionan ambas páginas. Las coordenadas, fuentes y tamaños son
exactamente los del documento original generado en Google Sheets.

Sistema de coordenadas ReportLab: origen en la esquina INFERIOR IZQUIERDA.
Para convertir desde pdfplumber (origen superior izq): y_rl = page_h - y_pl

Página: 612 × 1008 pts
"""

import io
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PDF_TEMPLATE_PATH = Path("plantillas/crt_blanco.pdf")
PAGE_W = 612.0
PAGE_H = 1008.0

def _find_font(candidates: list) -> str | None:
    """Retorna la primera ruta de la lista que exista en el sistema."""
    for path in candidates:
        if Path(path).exists():
            return path
    return None

_FONT_CANDIDATES = {
    "Carlito": [
        # Linux
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        # macOS — Calibri nativo o Arial como fallback
        "/System/Library/Fonts/Supplemental/Calibri.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "Carlito-Bold": [
        "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Calibri Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "LiberationSans": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "LiberationSans-Bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}

def _register_fonts():
    for name, candidates in _FONT_CANDIDATES.items():
        path = _find_font(candidates)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception as e:
                print(f"[pdf_service] Advertencia: no se pudo registrar {name} desde {path}: {e}")
        else:
            print(f"[pdf_service] Advertencia: no se encontró fuente para '{name}' en ninguna ruta candidata")

_register_fonts()

F_REGULAR  = "Carlito"
F_BOLD     = "Carlito-Bold"
F_ITALIC   = "LiberationSans"
F_ARIAL_BD = "LiberationSans-Bold"


def _y(pdf_plumber_top: float) -> float:
    return PAGE_H - pdf_plumber_top


def _fmt(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, float):
        return "" if value == 0.0 else f"{value:,.2f}"
    if isinstance(value, int):
        return "" if value == 0 else str(value)
    text = str(value).strip()
    if " — " in text:
        text = text.split(" — ")[0]
    return text


def _get(form: dict, key: str) -> str:
    return _fmt(form.get(key))


def _build_overlay(form: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))

    def clear(x0, y0_top, x1, y1_bottom, margin=1):
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(1, 1, 1)
        rl_y0 = _y(y1_bottom) - margin
        h = (y1_bottom - y0_top) + margin * 2
        c.rect(x0 - margin, rl_y0, (x1 - x0) + margin * 2, h, fill=1, stroke=0)

    def text(x, y_pl, txt, font=F_REGULAR, size=8.3):
        if not txt:
            return
        c.setFillColorRGB(0, 0, 0)
        c.setFont(font, size)
        c.drawString(x, _y(y_pl), txt)

    # Limpiar zonas variables de la plantilla
    clear(386.0, 143.0, 560.0, 168.0)   # Número CRT
    clear(348.0, 181.0, 560.0, 196.0)   # Transportista
    clear(286.0, 196.0, 560.0, 236.0)   # Dirección portador
    clear(286.0, 243.0, 560.0, 262.0)   # Lugar emisión
    clear(286.0, 283.0, 560.0, 308.0)   # Lugar recepción
    clear(286.0, 308.0, 560.0, 355.0)   # Lugar entrega / notificar
    clear(460.0, 463.0, 560.0, 485.0)   # Valor/Incoterm
    clear(125.0, 469.0, 290.0, 512.0)   # Totales
    clear(412.0, 538.0, 560.0, 556.0)   # Declaración valor
    clear(147.0, 558.0, 186.0, 574.0)   # Flete origen 0.00
    clear(147.0, 570.0, 186.0, 585.0)   # Flete frontera 0.00
    clear(140.0, 620.0, 168.0, 638.0)   # Total flete
    clear(449.0, 580.0, 560.0, 622.0)   # Docs anexos números
    clear(286.0, 653.0, 560.0, 692.0)   # Instrucciones aduana
    clear(444.0, 746.0, 560.0, 762.0)   # Conductor valor
    clear(415.0, 762.0, 424.0, 780.0)   # Patente camión valor
    clear(497.0, 762.0, 560.0, 780.0)   # Patente rampla valor
    clear(170.0, 747.0, 235.0, 762.0)   # Fecha firma remitente
    clear(170.0, 877.0, 235.0, 893.0)   # Fecha firma transportista

    # Casilla 1 — Remitente
    text(116.8, 148.0, _get(form, "f_remitente"), font=F_REGULAR, size=9.2)
    dir_rem = _get(form, "f_dir_remitente")
    if "\n" in dir_rem:
        parts = dir_rem.split("\n", 1)
        text(128.8, 162.0, parts[0].strip(), font=F_REGULAR, size=8.3)
        text(126.7, 174.0, parts[1].strip(), font=F_REGULAR, size=8.3)
    elif dir_rem:
        text(128.8, 162.0, dir_rem, font=F_REGULAR, size=8.3)

    # Casilla 2 — Número CRT
    text(386.5, 153.0, _get(form, "f_numero_crt"), font=F_BOLD, size=11.9)

    # Casilla 3 — Transportista
    text(361.8, 186.0, _get(form, "f_transportista"), font=F_ITALIC, size=8.3)

    # Casilla 4 — Destinatario
    text(139.4, 214.0, _get(form, "f_destinatario"),     font=F_REGULAR, size=8.3)
    text(85.7,  227.0, _get(form, "f_dir_destinatario"), font=F_REGULAR, size=7.3)

    # Casilla 5 — Lugar Emisión
    text(380.1, 250.0, _get(form, "f_lugar_emision"), font=F_REGULAR, size=8.3)

    # Casilla 6 — Consignatario
    text(136.5, 276.0, _get(form, "f_consignatario"),     font=F_REGULAR, size=9.2)
    text(85.7,  290.0, _get(form, "f_dir_consignatario"), font=F_REGULAR, size=7.3)

    # Casilla 7 — Lugar y fecha recepción
    lugar_rec = _get(form, "f_lugar_recepcion")
    fecha_doc = _get(form, "f_fecha_documento")
    recepcion = "  ".join(filter(None, [lugar_rec, fecha_doc]))
    text(356.8, 290.0, recepcion, font=F_REGULAR, size=8.3)

    # Casilla 8 — Lugar entrega
    text(341.3, 318.0, _get(form, "f_lugar_entrega"), font=F_REGULAR, size=8.3)

    # Casilla 9 — Notificar a
    text(139.4, 332.0, _get(form, "f_notificar"),     font=F_REGULAR, size=8.3)
    text(372.4, 333.0, _get(form, "f_destino_final"), font=F_REGULAR, size=7.3)
    text(95.6,  345.0, _get(form, "f_dir_notificar"), font=F_REGULAR, size=6.4)

    # Casilla 11 — Descripción de carga
    desc1    = _get(form, "f_descripcion_1")
    kn1      = _get(form, "f_kilos_netos_1")
    desc2    = _get(form, "f_descripcion_2")
    kn2      = _get(form, "f_kilos_netos_2")
    desc_gen = _get(form, "f_descripcion")

    if desc1:
        text(60.8, 402.0, desc1, font=F_BOLD, size=7.3)
        if kn1:
            text(60.8, 417.0, f"CON: {kn1} KILOS NETOS", font=F_REGULAR, size=7.3)
    if desc2:
        text(60.8, 431.0, desc2, font=F_BOLD, size=7.3)
        if kn2:
            text(60.8, 446.0, f"CON: {kn2} KILOS NETOS", font=F_REGULAR, size=7.3)
    if not desc1 and not desc2 and desc_gen:
        for i, line in enumerate(desc_gen.split("\n")[:4]):
            text(60.8, 402.0 + i * 15.0, line.strip(), font=F_BOLD, size=7.3)

    # Casilla 12 — Peso bruto
    pb = _get(form, "f_peso_bruto")
    if pb:
        text(472.6, 389.0, pb, font=F_REGULAR, size=9.2)

    # Totales (solo valores; labels ya están en la plantilla)
    total_cajas = _get(form, "f_total_cajas")
    total_kn    = _get(form, "f_peso_neto")
    total_kb    = _get(form, "f_peso_bruto")
    if total_cajas:
        text(130.0, 475.0, total_cajas, font=F_BOLD, size=7.3)
    if total_kn:
        text(130.0, 488.0, total_kn,   font=F_BOLD, size=7.3)
    if total_kb:
        text(130.0, 501.0, total_kb,   font=F_BOLD, size=7.3)

    # Casilla 14 — Valor / Incoterm
    valor = _get(form, "f_valor_mercaderia")
    inco  = _get(form, "f_incoterm")
    val_str = "  ".join(filter(None, [valor, inco]))
    if val_str:
        text(482.5, 473.0, val_str, font=F_REGULAR, size=9.2)

    # Casilla 16 — Declaración valor
    val_mer = _get(form, "f_valor_mercaderia")
    if val_mer:
        text(412.5, 544.0, val_mer, font=F_REGULAR, size=9.2)

    # Casilla 15 — Flete
    flete_orig = _get(form, "f_flete_origen")
    flete_fron = _get(form, "f_flete_frontera")
    flete_tot  = _get(form, "f_flete_usd")
    if flete_orig:
        text(135.5, 564.0, flete_orig, font=F_REGULAR, size=8.3)
        text(170.0, 564.0, "USD",      font=F_REGULAR, size=8.3)
    if flete_fron:
        text(130.0, 576.0, flete_fron, font=F_REGULAR, size=8.3)
        text(170.0, 576.0, "USD",      font=F_REGULAR, size=8.3)
    if flete_tot:
        text(145.9, 627.0, flete_tot, font=F_REGULAR, size=8.3)

    # Casilla 17 — Documentos anexos
    facturas = _get(form, "f_num_factura")
    guias    = _get(form, "f_guias_despacho")
    cert_san = _get(form, "f_cert_sanitario")
    if facturas:
        text(450.0, 587.0, facturas,  font=F_REGULAR, size=7.3)
    if guias:
        text(450.0, 598.0, guias,     font=F_REGULAR, size=7.3)
    if cert_san:
        text(450.0, 609.0, cert_san,  font=F_REGULAR, size=7.3)

    # Casilla 18 — Instrucciones aduana
    instrucciones = _get(form, "f_instrucciones_aduana")
    if instrucciones:
        for i, line in enumerate(instrucciones.split("\n")[:3]):
            text(322.2, [660.0, 672.0, 682.0][i], line.strip(), font=F_REGULAR, size=6.4)

    # Casilla 21 — Fecha firma remitente
    fecha_emision = _get(form, "f_fecha_emision")
    if fecha_emision:
        text(171.5, 753.0, fecha_emision, font=F_BOLD, size=8.3)

    # Casilla 22 — Conductor y patentes
    conductor  = _get(form, "f_conductor")
    pat_camion = _get(form, "f_patente_camion")
    pat_rampla = _get(form, "f_patente_rampla")
    if conductor:
        text(445.0, 753.0, conductor,  font=F_BOLD, size=7.3)
    if pat_camion:
        text(416.0, 769.0, pat_camion, font=F_BOLD, size=7.3)
    if pat_rampla:
        text(498.0, 769.0, pat_rampla, font=F_BOLD, size=7.3)

    # Casilla 24 — Destinatario firma
    text(395.7, 820.0, _get(form, "f_destinatario"), font=F_REGULAR, size=8.3)

    # Casilla 23 — Fecha firma transportista
    if fecha_emision:
        text(171.8, 883.0, fecha_emision, font=F_BOLD, size=8.3)

    c.save()
    buf.seek(0)
    return buf.read()


def _load_template_bytes() -> Optional[bytes]:
    if not PDF_TEMPLATE_PATH.exists():
        return None
    return PDF_TEMPLATE_PATH.read_bytes()


# DEPRECATED — reemplazada por pdf_builder. Conservada como referencia.
# def generate_crt_pdf(form_data: dict) -> Optional[bytes]:
#     """Genera el PDF final fusionando plantilla + overlay."""
#     assert isinstance(form_data, dict)
#     template_bytes = _load_template_bytes()
#     if template_bytes is None:
#         return None
#     overlay_bytes = _build_overlay(form_data)
#     template_reader = PdfReader(io.BytesIO(template_bytes))
#     overlay_reader  = PdfReader(io.BytesIO(overlay_bytes))
#     writer = PdfWriter()
#     overlay_page = overlay_reader.pages[0]
#     overlay_page.merge_page(template_reader.pages[0])
#     writer.add_page(overlay_page)
#     out = io.BytesIO()
#     writer.write(out)
#     return out.getvalue()


# Nuevo generador (desde cero, sin merge)
from src.services.pdf_builder import build_crt_pdf

def generate_crt_pdf(form_data: dict) -> tuple[Optional[bytes], bool]:
    """
    Genera el PDF CRT. Usa Excel+LibreOffice si está disponible,
    sino cae al builder ReportLab como fallback.

    Retorna: (pdf_bytes, is_fallback)
      is_fallback=False → LibreOffice (documento oficial)
      is_fallback=True  → ReportLab con marca de agua (coordenadas aproximadas)
    """
    assert isinstance(form_data, dict), "form_data debe ser dict, no None"

    # Intentar con Excel (resultado idéntico al original)
    try:
        from src.services.excel_pdf_builder import generate_crt_pdf_from_excel, _find_soffice
        if _find_soffice():
            result = generate_crt_pdf_from_excel(form_data)
            if result:
                return result, False
    except Exception as e:
        print(f"[pdf_service] Excel builder falló: {e}, usando fallback ReportLab")

    # Fallback: ReportLab con marca de agua BORRADOR NO OFICIAL
    try:
        return build_crt_pdf(form_data, watermark=True), True
    except Exception as e:
        print(f"[pdf_service] ReportLab builder falló: {e}")
        return None, True


# Deprecated — el frontend Dash usa generate_crt_pdf() + iframe base64
def render_pdf_preview(form_data: dict) -> Optional[bytes]:
    """Renderiza el PDF como PNG para la vista previa en Streamlit."""
    pdf_bytes = generate_crt_pdf(form_data)
    if pdf_bytes is None:
        return None
    try:
        import pypdfium2 as pdfium
        doc    = pdfium.PdfDocument(pdf_bytes)
        bitmap = doc[0].render(scale=2.0)
        buf    = io.BytesIO()
        bitmap.to_pil().save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return pdf_bytes
