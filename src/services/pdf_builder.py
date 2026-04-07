"""
PDF Builder — genera el CRT completo desde cero con ReportLab.
Sin plantilla base, sin merge. Todo en un solo sistema de coordenadas.
Página: 612 × 1008 pts (mismo tamaño que la plantilla original de Google Sheets).
Origen ReportLab: esquina inferior izquierda.
Coordenadas verificadas contra VESPRINI - CRT - 5098-BB (2).pdf
"""

import io
from pathlib import Path
from typing import Optional

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black, white, HexColor

# ── Página ────────────────────────────────────────────────────────────────────
W = 612.0
H = 1008.0

def _y(top: float) -> float:
    """Convierte coordenada top (pdfplumber) a bottom (ReportLab)."""
    return H - top

# ── Fuentes ───────────────────────────────────────────────────────────────────
_FONT_CANDIDATES = {
    "Arial":          ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                       "/System/Library/Fonts/Supplemental/Arial.ttf",
                       "/Library/Fonts/Arial.ttf"],
    "Arial-Bold":     ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                       "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "Calibri":        ["/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
                       "/System/Library/Fonts/Supplemental/Calibri.ttf",
                       "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "Calibri-Bold":   ["/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
                       "/System/Library/Fonts/Supplemental/Calibri Bold.ttf",
                       "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "Calibri-BoldItalic": ["/usr/share/fonts/truetype/crosextra/Carlito-BoldItalic.ttf",
                            "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"],
}

def _register_fonts():
    for name, candidates in _FONT_CANDIDATES.items():
        for path in candidates:
            if Path(path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    break
                except Exception:
                    continue

_register_fonts()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt(value) -> str:
    if value is None: return ""
    if hasattr(value, "strftime"): return value.strftime("%d-%m-%Y")
    if isinstance(value, float): return "" if value == 0.0 else f"{value:,.2f}"
    if isinstance(value, int): return "" if value == 0 else str(value)
    text = str(value).strip()
    if " — " in text: text = text.split(" — ")[0]
    return text

def _get(form: dict, key: str) -> str:
    return _fmt(form.get(key))


def build_crt_pdf(form: dict) -> bytes:
    """
    Genera el PDF CRT completo desde cero.
    form: dict con keys f_* (mismo formato que pdf_service.py)
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setLineWidth(0.7)
    c.setStrokeColor(black)
    c.setFillColor(black)

    # ── Helpers de dibujo ─────────────────────────────────────────────────────
    def hl(y_top, x0=50.4, x1=562.3):
        yb = H - y_top
        c.line(x0, yb, x1, yb)

    def vl(x, y_top_start, y_top_end):
        c.line(x, H - y_top_start, x, H - y_top_end)

    def txt(x, y_top, text, font="Arial", size=5.5, color=black):
        if not text: return
        c.setFillColor(color)
        c.setFont(font, size)
        c.drawString(x, H - y_top, text)
        c.setFillColor(black)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. ESTRUCTURA — líneas y borde
    # ══════════════════════════════════════════════════════════════════════════

    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0, 0, 0)

    # Borde exterior: rect(x, y_bottom, width, height)
    # y_bottom = H - 906.9 = 101.1 | height = 906.9 - 54.0 = 852.9
    c.rect(50.4, H - 906.9, 511.9, 852.9, stroke=1, fill=0)

    # Líneas horizontales principales
    for y_top in [58.6, 129.2, 170.9, 233.7, 259.8, 305.0, 341.7,
                  366.4, 410.9, 455.4, 523.2, 560.6, 633.3, 690.5, 780.9, 891.8]:
        hl(y_top)

    # Divisor central vertical
    vl(284.5, 129.2, 892.1)

    # Divisor columna casilla 12/13/14
    vl(454.6, 366.1, 523.5)

    # Verticales internas casilla 15
    for x in [105.8, 165.1, 192.7, 254.8]:
        vl(x, 522.8, 643.6)

    # Horizontales casilla 15
    for y_top in [545.8, 618.5, 643.2]:
        hl(y_top, x0=50.4, x1=284.5)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. ENCABEZADO — CRT título y textos legales
    # ══════════════════════════════════════════════════════════════════════════

    # "A" ALADI
    txt(52.5, 65.9, "A", "Arial-Bold", 9.2)

    # Título CRT grande
    txt(58.9, 104.0, "CRT", "Arial-Bold", 18.4)

    # Subtítulos
    txt(152.8, 92.1, "por Carretera", "Arial", 9.2)
    txt(121.0, 109.1, "Conhecimento de Transporte", "Arial", 9.2)
    txt(127.4, 126.0, "Internacional por Rodovia", "Arial", 9.2)

    # Texto legal español (columna derecha, tamaño 5.5)
    legal_es = [
        (257.3, 66.7, "El transporte realizado bajo esta Carta de Porte Internacional está sujeto a las disposiciones del"),
        (257.3, 75.2, "Convenio sobre el contrato de Transportey la Responsabilidad Civil del Portador en el transporte"),
        (257.3, 83.6, "Terrestre Internacional de Mercancias, las cuales anulan toda estipulación que se aparte de estas en"),
        (257.3, 92.1, "perjuicio del remitente o del consignatario"),
        (257.3, 100.6, "O transporte realizado ao ampara deste conhecimiento de Transporte Internacional está sujeto as"),
        (257.3, 109.1, "disposicoes do Convenio sobre o Contrato de Transporte e a Responsabilidade Civil do Transporta-"),
        (257.3, 117.5, "dor no transporte Terrestre Internacional de Mercadorias, as quais anulan toda estipulacao contraria"),
        (257.3, 126.0, "as mesmas em prejuizo do remitente ou do consignatario"),
    ]
    for x, y, t in legal_es:
        txt(x, y, t, "Arial", 5.5)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. LABELS DE CASILLAS (Arial 5.5, bilingüe)
    # ══════════════════════════════════════════════════════════════════════════

    labels = [
        # Casilla 1
        (52.5, 137.3, "1 Nombre o domicilio del remitente / Nome e endereco do remetente"),
        # Casilla 2
        (286.9, 137.3, "2 Número / Número"),
        # Casilla 3
        (286.9, 178.9, "3 Nombre o domicilio del portador / Nome e endereco do transportador"),
        # Casilla 4
        (52.5, 202.9, "4 Nombre o domicilio del destinatario / Nome e endereco do destinatario"),
        # Casilla 5
        (286.9, 241.8, "5 Lugar,PaÍs y Fecha de Emisión/Localidad e país de emisao"),
        # Casilla 6
        (52.5, 267.9, "6 Nombre o domicilio del consignatario / Nome e endereco do consignatario"),
        # Casilla 7
        (288.5, 270.0, "7 Lugar,país y fecha que el porteador se hace cargo de la mercadería"),
        (290.0, 279.9, "Localidade, país e data em que o transportador se responzabiliza pela mercadoria"),
        # Casilla 8
        (286.9, 313.1, "8 Lugar, país y plazo de entrega / Localidade, país e prazo de entrega"),
        # Casilla 9
        (52.5, 323.7, "9 Notificar a / Notificar a:"),
        # Casilla 10
        (286.9, 349.8, "10 Portadores sucesivos / Transportadores sucesivos"),
        # Casilla 11
        (52.5, 373.8, "11 Cantidad y clase de bultos, marcas y números, tipo de mercancías, contenedores y accesorios"),
        (63.2, 383.7, "Quantidade a categoria de volumenes, marcas e números, tipo de mercadorias, containers e pecas"),
        # Casilla 12
        (457.1, 373.8, "12 Peso bruto en kg./Peso bruto em kg."),
        # Casilla 13
        (457.1, 424.0, "13 Volumen en m.cu/Peso bruto em m.cu"),
        # Casilla 14
        (457.1, 468.5, "14 Valor / Valor"),
        # Casilla 15
        (52.5, 532.7, "15   Gastos a pagar"),
        (115.4, 532.7, "Monto remitente"),
        (168.3, 532.7, "Moneda"),
        (259.4, 532.7, "Moneda"),
        (63.1, 542.6, "Gastos a pagar"),
        (116.8, 542.6, "Valor remitente"),
        (170.4, 542.6, "Moeda"),
        (202.2, 542.6, "Valor destinatario"),
        (260.8, 542.6, "Moeda"),
        # Casilla 16
        (286.9, 532.7, "16 Declaración del valor de las mercaderías / Declaracao do valor das mercadorias"),
        # Casilla 17
        (286.9, 568.7, "17 Documentos anexos / Documentos anexos"),
        # Casilla 18
        (286.9, 641.4, "18 Instrucciones sobre formalidades de aduana/Instrucoes sobre formalidades dealfandega"),
        # Casilla 19
        (52.5, 651.3, "19 Monto del flete externo / Valor do frete externo"),
        # Casilla 20
        (52.5, 676.7, "20 Monto de reembolso contra entrega / Valor de reembolso contra entrega"),
        # Casilla 21
        (52.5, 697.9, "21 Nombre y firma del remitente o su representante"),
        (61.7, 707.8, "Nome e assinatura do rematente ou seu representante"),
        # Casilla 22
        (286.9, 697.9, "22 Declaraciones y observaciones / Declaracao e observacao"),
        # Casilla 23
        (52.5, 815.8, "23 Nombre, firma y sello del porteador o su representante."),
        (61.7, 825.7, "Nome, assinatura e capimbo do transportador ou seu representante"),
        # Casilla 24
        (286.9, 797.5, "24 Nombre y firma del destinatario o su representante"),
        (296.1, 807.4, "Nome e assinatura do destinatario ou ssu representante"),
    ]
    for x, y, t in labels:
        txt(x, y, t, "Arial", 5.5)

    # Labels adicionales tamaño 9.2
    txt(52.5, 558.8, "Flete / Frete", "Arial", 9.2)
    txt(52.5, 570.8, "ORIGEN/FRONTERA", "Calibri", 5.5)
    txt(52.5, 582.9, "FRONTERA/DESTINO", "Calibri", 5.5)
    txt(52.5, 616.7, "Otros / Outros", "Arial", 5.5)
    txt(58.2, 641.4, "T  O  T  A  L", "Arial", 9.2)

    # "SON:" label casilla 11
    txt(60.0, 397.9, "SON:", "Calibri", 8.3)

    # Labels fijos casilla 14 (TOTAL CAJAS etc.)
    txt(60.8, 481.9, "TOTAL CAJAS:", "Calibri-Bold", 7.3)
    txt(60.8, 495.3, "TOTAL KILOS NETOS:", "Calibri-Bold", 7.3)
    txt(60.8, 508.7, "TOTAL KILOS BRUTOS:", "Calibri-Bold", 7.3)

    # Moneda/Moeda labels
    txt(457.1, 495.3, "Moneda / Moeda", "Arial", 5.5)
    txt(501.6, 508.7, "US$", "Calibri", 8.3)

    # Labels documentos anexos
    txt(372.4, 594.2, "FACTURAS NROS:", "Calibri", 7.3)
    txt(356.8, 605.4, "GUIAS DE DESPACHO NROS:", "Calibri", 7.3)
    txt(363.9, 616.7, "CERTIFICADO SANITARIO NRO:", "Calibri", 7.3)

    # Texto legal pie izquierdo
    pie_legal = [
        (52.5, 770.0, "Las mercancias consignadas en esta Carta de Porte fueron recibidas por el portador"),
        (52.5, 779.1, "aparentemente en buen estado, bajo las condiciones generales que figuran al dorso."),
        (52.5, 788.3, "As mercadorias consignadas neste Conhacimento de Transporte foran recibidas"),
        (52.5, 797.5, "pelo transportador aparentemente em bom estado, sob as condicoes gerais que"),
        (52.5, 807.4, "figuram no verso."),
    ]
    for x, y, t in pie_legal:
        txt(x, y, t, "Arial", 5.5)

    # ══════════════════════════════════════════════════════════════════════════
    # 4. DATOS FIJOS DEL TRANSPORTISTA (siempre presentes)
    # ══════════════════════════════════════════════════════════════════════════
    from modulos.config_cliente import CONFIG_ACTIVO

    # Casilla 3 — Transportista (BoldItalic)
    txt(361.8, 186.0, CONFIG_ACTIVO["transportista"], "Calibri-BoldItalic", 8.3)
    txt(348.7, 200.0, "Avda Colon 1761 Bahia Blanca BS - AS", "Calibri-BoldItalic", 8.3)
    txt(397.1, 214.0, "ARGENTINA", "Calibri-BoldItalic", 8.3)

    # Casilla 21 — "p.p. REMITENTE" fijo
    txt(112.5, 713.7, f"p.p. {CONFIG_ACTIVO['remitente']}", "Calibri-Bold", 8.3)

    # Casilla 23 — Firma transportista
    txt(94.2, 838.2, CONFIG_ACTIVO["transportista"], "Arial-Bold", 10.1)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. DATOS VARIABLES DEL FORMULARIO
    # ══════════════════════════════════════════════════════════════════════════

    # Casilla 1 — Remitente
    txt(116.8, 148.0, _get(form, "f_remitente"), "Calibri", 9.2)
    dir_rem = _get(form, "f_dir_remitente")
    if "\n" in dir_rem:
        parts = dir_rem.split("\n", 1)
        txt(128.8, 162.0, parts[0].strip(), "Calibri", 8.3)
        txt(126.7, 174.0, parts[1].strip(), "Calibri", 8.3)
    elif dir_rem:
        txt(128.8, 162.0, dir_rem, "Calibri", 8.3)

    # Casilla 2 — Número CRT
    txt(386.5, 153.0, _get(form, "f_numero_crt"), "Calibri-Bold", 11.9)

    # Casilla 4 — Destinatario
    txt(139.4, 214.0, _get(form, "f_destinatario"), "Calibri", 8.3)
    dir_dest = _get(form, "f_dir_destinatario")
    if dir_dest:
        for i, line_t in enumerate(dir_dest.split("\n")[:4]):
            txt(85.7, 227.0 + i * 12.0, line_t.strip(), "Calibri", 7.3)

    # Casilla 5 — Lugar emisión
    txt(380.1, 250.0, _get(form, "f_lugar_emision"), "Calibri", 8.3)

    # Casilla 6 — Consignatario
    txt(136.5, 276.0, _get(form, "f_consignatario"), "Calibri", 9.2)
    dir_cons = _get(form, "f_dir_consignatario")
    if dir_cons:
        for i, line_t in enumerate(dir_cons.split("\n")[:4]):
            txt(85.7, 290.0 + i * 12.0, line_t.strip(), "Calibri", 7.3)

    # Casilla 7 — Lugar recepción + fecha
    lugar_rec = _get(form, "f_lugar_recepcion")
    fecha_doc = _get(form, "f_fecha_documento")
    txt(356.8, 290.0, "  ".join(filter(None, [lugar_rec, fecha_doc])), "Calibri", 8.3)

    # Casilla 8 — Lugar entrega
    txt(341.3, 318.0, _get(form, "f_lugar_entrega"), "Calibri", 8.3)

    # Casilla 9 — Notificar
    txt(139.4, 332.0, _get(form, "f_notificar"), "Calibri", 8.3)
    txt(372.4, 332.0, _get(form, "f_destino_final"), "Calibri", 7.3)
    dir_not = _get(form, "f_dir_notificar")
    if dir_not:
        for i, line_t in enumerate(dir_not.split("\n")[:3]):
            txt(95.6, 345.0 + i * 12.0, line_t.strip(), "Calibri", 6.4)

    # Casilla 11 — Descripción carga
    txt(60.0, 390.0, "SON:", "Calibri", 8.3)
    desc1 = _get(form, "f_descripcion_1")
    kn1   = _get(form, "f_kilos_netos_1")
    desc2 = _get(form, "f_descripcion_2")
    kn2   = _get(form, "f_kilos_netos_2")
    if desc1:
        txt(60.8, 402.0, desc1, "Calibri-Bold", 7.3)
        if kn1:
            txt(60.8, 416.6, f"CON: {kn1} KILOS NETOS", "Calibri", 7.3)
    if desc2:
        txt(60.8, 431.5, desc2, "Calibri-Bold", 7.3)
        if kn2:
            txt(60.8, 446.3, f"CON: {kn2} KILOS NETOS", "Calibri", 7.3)

    # Casilla 12 — Peso bruto
    pb = _get(form, "f_peso_bruto")
    if pb:
        txt(472.6, 389.0, pb, "Calibri", 9.2)
        txt(508.0, 389.0, "Kg Brutos", "Calibri", 9.2)

    # Totales
    total_cajas = _get(form, "f_total_cajas")
    total_kn    = _get(form, "f_peso_neto")
    total_kb    = _get(form, "f_peso_bruto")
    if total_cajas: txt(130.0, 475.0, total_cajas, "Calibri-Bold", 7.3)
    if total_kn:    txt(130.0, 488.0, total_kn,    "Calibri-Bold", 7.3)
    if total_kb:    txt(130.0, 501.0, total_kb,    "Calibri-Bold", 7.3)

    # Casilla 14 — Valor / Incoterm
    valor = _get(form, "f_valor_mercaderia")
    inco  = _get(form, "f_incoterm")
    if valor: txt(482.5, 473.0, valor, "Calibri", 9.2)
    if inco:  txt(521.7, 473.0, inco,  "Calibri", 9.2)

    # Casilla 16 — Declaración valor
    val_mer = _get(form, "f_valor_mercaderia")
    if val_mer:
        txt(395.7, 543.9, "US$", "Calibri", 9.2)
        txt(412.5, 543.9, val_mer, "Calibri", 9.2)

    # Casilla 15 — Flete
    flete_orig = _get(form, "f_flete_origen")
    flete_fron = _get(form, "f_flete_frontera")
    flete_tot  = _get(form, "f_flete_usd")
    if flete_orig:
        txt(135.5, 564.2, flete_orig, "Calibri", 8.3)
        txt(171.1, 564.2, "USD", "Calibri", 8.3)
    if flete_fron:
        txt(135.5, 576.2, flete_fron, "Calibri", 8.3)
        txt(171.1, 576.2, "USD", "Calibri", 8.3)
    if flete_tot:
        txt(145.9, 627.0, flete_tot, "Calibri", 8.3)
        txt(171.1, 627.0, "USD", "Calibri", 8.3)

    # Casilla 17 — Documentos
    facturas = _get(form, "f_num_factura")
    guias    = _get(form, "f_guias_despacho")
    cert_san = _get(form, "f_cert_sanitario")
    if facturas: txt(450.0, 586.8, facturas,  "Calibri", 7.3)
    if guias:    txt(466.0, 598.1, guias,     "Calibri", 7.3)
    if cert_san: txt(470.0, 609.4, cert_san,  "Calibri", 7.3)

    # Casilla 18 — Instrucciones aduana
    instrucciones = _get(form, "f_instrucciones_aduana")
    if instrucciones:
        for i, line_t in enumerate(instrucciones.split("\n")[:3]):
            txt(322.2, [660.5, 671.8, 682.3][i], line_t.strip(), "Calibri", 6.4)

    # Casilla 21 — Fecha firma remitente
    fecha_em = _get(form, "f_fecha_emision")
    txt(52.5, 760.8, "Fecha / Data", "Arial", 5.5)
    if fecha_em:
        txt(171.5, 752.5, fecha_em, "Calibri-Bold", 8.3)

    # Casilla 22 — Conductor y patentes
    conductor  = _get(form, "f_conductor")
    pat_camion = _get(form, "f_patente_camion")
    pat_rampla = _get(form, "f_patente_rampla")
    if conductor:
        txt(375.2, 752.5, "CONDUCTOR:", "Calibri-Bold", 7.3)
        txt(418.4, 752.5, conductor, "Calibri-Bold", 7.3)
    if pat_camion or pat_rampla:
        txt(331.4, 768.8, "PATENTE CAMION:", "Calibri-Bold", 7.3)
        if pat_camion: txt(391.4, 768.8, pat_camion, "Calibri-Bold", 7.3)
        txt(425.7, 768.8, "/ PATENTE RAMPLA:", "Calibri-Bold", 7.3)
        if pat_rampla: txt(488.8, 768.8, pat_rampla, "Calibri-Bold", 7.3)

    # Casilla 24 — Destinatario firma
    txt(395.7, 820.3, _get(form, "f_destinatario"), "Calibri", 8.3)

    # Casilla 23 — Fecha firma transportista
    txt(286.9, 792.0, "Fecha / Data", "Arial", 5.5)
    if fecha_em:
        txt(171.8, 883.3, fecha_em, "Calibri-Bold", 8.3)

    # ══════════════════════════════════════════════════════════════════════════
    c.save()
    buf.seek(0)
    return buf.read()
