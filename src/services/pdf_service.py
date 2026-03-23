"""
Servicio PDF — Fase 1: renderizado del template con overlay de datos del formulario.
Fase 2 añadirá: fill_pdf_fields() y extract_fields_from_pdf().

Coordenadas calibradas con cuadrícula sobre pdfplumber (página 612×1008 pts).
"""

import io
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

PDF_TEMPLATE_PATH = Path("plantillas/crt_blanco.pdf")
RENDER_SCALE = 2.0  # 612×2=1224 px  |  1008×2=2016 px


# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------

def _load_font(size_pts: float) -> ImageFont.ImageFont:
    size_px = max(10, int(size_pts * RENDER_SCALE))
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size=size_px)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


_FONT_LG = _load_font(11)   # número de CRT
_FONT_MD = _load_font(9)    # campos principales
_FONT_SM = _load_font(8)    # campos secundarios / combinados

_FONTS = {11: _FONT_LG, 9: _FONT_MD, 8: _FONT_SM}


# ---------------------------------------------------------------------------
# Formateo de valores
# ---------------------------------------------------------------------------

def _fmt(key: str, value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, float):
        return "" if value == 0.0 else f"{value:,.2f}"
    if isinstance(value, int):
        return "" if value == 0 else str(value)
    text = str(value).strip()
    if " — " in text:           # selectbox "EXW — Ex Works" → "EXW"
        text = text.split(" — ")[0]
    return text


# ---------------------------------------------------------------------------
# Mapa de coordenadas — calibrado con cuadrícula sobre pdfplumber
#
# Referencia de zonas clave (puntos PDF):
#   Col izquierda:  x = 52  – 280
#   Col derecha:    x = 286 – 450
#   Col angosta:    x = 457 – 560   (campo 12/13/14)
#   Línea divisoria: x ≈ 283
#
#   Cas. 1  Remitente          izq  y = 132 – 173
#   Cas. 2  Número CRT         der  y = 132 – 173
#   Cas. 3  Transportista      der  y = 173 – 197
#   Cas. 4  Destinatario       izq  y = 197 – 236
#   Cas. 5  Emisión            der  y = 236 – 262   ← solo 1 línea
#   Cas. 6  Consignatario      izq  y = 262 – 307
#   Cas. 7  Cargo mercadería   der  y = 264 – 307   ← 2 líneas justas
#   Cas. 8  Lugar entrega      der  y = 307 – 344
#   Cas. 11 Descripción        izq  y = 368 – 418   (SON: en y≈390)
#   Cas. 12 Peso bruto         ang  y = 368 – 418   (Kg Brutos en y≈389)
#   Cas. 14 Valor/Incoterm     ang  y = 462 – 490   (CFR estaba en y≈473)
#   Cas. 15 Flete              izq  y = 549 – 588   (ORIGEN/FRONTERA en y≈565)
#   Cas. 17 Facturas           der  y = 563 – 600
#   Cas. 18 Instrucciones      der  y = 636 – 695
# ---------------------------------------------------------------------------

OVERLAY_MAP = [
    # ── Casilla 1 — Remitente (col. izquierda) ──────────────────────────────
    {"key": "f_remitente",
     "tx":  57, "ty": 147, "size": 9,
     "clear": (52, 138, 280, 163)},
    {"key": "f_dir_remitente",
     "tx":  57, "ty": 163, "size": 8,
     "clear": (52, 161, 280, 173)},

    # ── Casilla 2 — Número CRT (col. derecha) ───────────────────────────────
    {"key": "f_numero_crt",
     "tx": 295, "ty": 151, "size": 11,
     "clear": (286, 138, 560, 173)},

    # ── Casilla 3 — Transportista (col. derecha) ────────────────────────────
    {"key": "f_transportista",
     "tx": 295, "ty": 186, "size": 9,
     "clear": (286, 180, 560, 197)},

    # ── Casilla 4 — Destinatario (col. izquierda) ───────────────────────────
    {"key": "f_destinatario",
     "tx":  57, "ty": 207, "size": 9,
     "clear": (52, 203, 280, 221)},
    {"key": "f_dir_destinatario",
     "tx":  57, "ty": 221, "size": 8,
     "clear": (52, 219, 280, 236)},

    # ── Casilla 5 — Lugar + Fecha de Emisión (col. derecha, 1 sola línea) ───
    # f_fecha_emision se combina aquí — ver lógica especial en render()
    {"key": "f_lugar_emision",
     "tx": 295, "ty": 252, "size": 8,
     "clear": (286, 244, 560, 263)},

    # ── Casilla 7 — Cargo mercadería: lugar (línea 1) y fecha (línea 2) ─────
    {"key": "f_lugar_recepcion",
     "tx": 295, "ty": 286, "size": 9,
     "clear": (286, 281, 560, 306)},
    {"key": "f_fecha_documento",
     "tx": 295, "ty": 298, "size": 8,
     "clear": None},                   # la clear la cubre el ALWAYS_CLEAR

    # ── Casilla 8 — Lugar de entrega (col. derecha) ─────────────────────────
    {"key": "f_lugar_entrega",
     "tx": 295, "ty": 317, "size": 9,
     "clear": (286, 307, 560, 344)},
    {"key": "f_fecha_entrega",
     "tx": 295, "ty": 330, "size": 8,
     "clear": None},

    # ── Casilla 11 — Descripción de carga (col. izquierda) ──────────────────
    # "SON:" label está en y≈390; clear sólo desde y=400 para no borrarlo
    {"key": "f_descripcion",
     "tx":  57, "ty": 401, "size": 9,
     "clear": (52, 400, 450, 418)},

    # ── Casilla 12 — Peso bruto (col. angosta) ──────────────────────────────
    # "Kg Brutos" label está en y≈389; clear sólo desde y=400
    {"key": "f_peso_bruto",
     "tx": 461, "ty": 401, "size": 9,
     "clear": (456, 400, 560, 418)},

    # ── Totales — Peso neto (fila "TOTAL KILOS NETOS:" y≈488) ───────────────
    {"key": "f_peso_neto",
     "tx": 130, "ty": 487, "size": 9,
     "clear": (125, 481, 285, 497)},

    # ── Casilla 14 — Incoterm / Valor (col. angosta, y≈462–490) ────────────
    {"key": "f_incoterm",
     "tx": 461, "ty": 471, "size": 9,
     "clear": (456, 462, 560, 490)},

    # ── Casilla 15 — Flete ORIGEN/FRONTERA (y≈565) ──────────────────────────
    {"key": "f_flete_usd",
     "tx": 130, "ty": 563, "size": 9,
     "clear": (127, 557, 200, 574)},

    # ── Casilla 17 — Número de Factura (junto a "FACTURAS NROS:", y≈576) ────
    {"key": "f_num_factura",
     "tx": 451, "ty": 575, "size": 8,
     "clear": (450, 570, 560, 588)},

    # ── Casilla 18 — Instrucciones de Aduana (col. derecha, y≈648–694) ──────
    {"key": "f_instrucciones_aduana",
     "tx": 295, "ty": 651, "size": 8,
     "clear": (286, 647, 560, 695)},
]

# Zonas con datos de muestra del template que se limpian SIEMPRE
_ALWAYS_CLEAR = [
    (286, 197, 560, 236),   # Dirección portador de muestra (Avda Colon...)
    (286, 244, 560, 307),   # Datos emisión + cargo de muestra
    (286, 307, 560, 344),   # Datos entrega de muestra (AEROPUERTO INT...)
    (286, 647, 560, 695),   # Instrucciones aduana de muestra
    (127, 557, 200, 588),   # Valores flete de muestra (0.00 USD)
]


# ---------------------------------------------------------------------------
# Renderizado base (cacheado)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _render_base_png() -> Optional[bytes]:
    """PNG de la plantilla en bruto. Se genera una vez por sesión."""
    if not PDF_TEMPLATE_PATH.exists():
        return None
    doc = pdfium.PdfDocument(str(PDF_TEMPLATE_PATH))
    bitmap = doc[0].render(scale=RENDER_SCALE)
    buf = io.BytesIO()
    bitmap.to_pil().save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Renderizado con overlay
# ---------------------------------------------------------------------------

def render_pdf_with_overlay(form_data: dict) -> Optional[bytes]:
    """
    PNG de la plantilla CRT con los valores del formulario superpuestos.
    Se regenera en cada rerun de Streamlit (no cacheado).
    """
    base_bytes = _render_base_png()
    if base_bytes is None:
        return None

    img = Image.open(io.BytesIO(base_bytes)).copy()
    draw = ImageDraw.Draw(img)
    s = RENDER_SCALE
    WHITE = (255, 255, 255)
    INK   = (15, 15, 15)

    # ── Paso 1: limpiar zonas con datos de muestra ───────────────────────────
    for rect in _ALWAYS_CLEAR:
        draw.rectangle([int(c * s) for c in (rect[0], rect[1], rect[2], rect[3])],
                       fill=WHITE)

    # ── Paso 2: limpiar + dibujar cada campo mapeado ─────────────────────────
    for entry in OVERLAY_MAP:
        if entry["clear"]:
            x0, y0, x1, y1 = [int(c * s) for c in entry["clear"]]
            draw.rectangle([x0, y0, x1, y1], fill=WHITE)

        text = _fmt(entry["key"], form_data.get(entry["key"]))
        if not text:
            continue

        font = _FONTS.get(entry["size"], _FONT_MD)
        draw.text((int(entry["tx"] * s), int(entry["ty"] * s)),
                  text, fill=INK, font=font)

    # ── Paso 3: lógica especial — Casilla 5 combina lugar + fecha ────────────
    # El bloque 5 tiene solo ~18 pts de alto; caben en una línea combinada.
    lugar_em = _fmt("f_lugar_emision", form_data.get("f_lugar_emision"))
    fecha_em = _fmt("f_fecha_emision", form_data.get("f_fecha_emision"))
    combined_5 = "  |  ".join(filter(None, [lugar_em, fecha_em]))
    if combined_5:
        # Reemplaza el texto de lugar_emision ya dibujado con la versión combinada
        # (el clear ya se hizo en el OVERLAY_MAP de f_lugar_emision)
        draw.text((int(295 * s), int(252 * s)), combined_5,
                  fill=INK, font=_FONT_SM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
