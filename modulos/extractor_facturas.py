import re
import pdfplumber
from typing import Optional

# ── Patrones reales ───────────────────────────────────────────────────────────

# Número de factura — 6 variantes reales
PATRONES_FACTURA = [
    r"FACTURAS?\s+(?:DE\s+)?EXPORTACION\s*[.:/]\s*([\d,\s]+)",
    r"FACTURA\s+COMERCIAL\s*[.:/]\s*([\d,\s]+)",
    r"COMMERCIAL\s+INVOICE\s*[.:/]?\s*(?:N[°º])?\s*([\d,\s/]+)",
    r"INVOICE\s+N[°º]?\s*[.:/]\s*([\d,\s/]+)",
    r"N[°º]\s+FACTURA\s*[.:/]\s*([\d,\s]+)",
    r"FACT(?:URA)?\s*[.:/]\s*(\d+)",
]

# Blumar tiene formato especial: "139067/67254" (factura_chile/factura_cliente)
PATRON_FACTURA_BLUMAR = r"(\d{6,})\s*/\s*(\d{4,})"

# Incoterm — CPT es el más frecuente (260 casos), luego CFR (128), CIF (97)
PATRONES_INCOTERM = [
    r"CL[AÁ]USULA\s+DE\s+VENTA\s*[.:/]\s*([A-Z]{2,5})",
    r"INCOTERMS?\s*[.:/]\s*([A-Z]{2,5})",
    r"CONDICI[OÓ]N\s+DE\s+VENTA\s*[.:/]\s*([A-Z]{2,5})",
    r"\b(CPT|CFR|CIF|FOB|FCA|DAP|EXW|DDP)\b",
]

# Moneda
PATRONES_MONEDA = [
    r"TIPO\s+DE\s+MONEDA\s*[.:/]\s*([A-Z]{3})",
    r"CURRENCY\s*[.:/]\s*([A-Z]{3})",
    r"\b(USD|CNY|EUR|CLP)\b",
]

# Valor total
PATRONES_TOTAL = [
    r"TOTAL\s+[A-Z]{2,5}\s*:\s*([\d.,]+)",          # "TOTAL CPT : 109.648,80"
    r"TOTAL\s+(?:GENERAL\s+)?(?:USD|US\$|CLP|CNY|EUR)?\s*[.:/]?\s*([\d.,]+)",
    r"(?:USD|US\$)\s*([\d.,]+)\s*(?:TOTAL|$)",
    r"MONTO\s+TOTAL\s*[.:/]\s*([\d.,]+)",
    r"GRAND\s+TOTAL\s*[.:/]?\s*([\d.,]+)",
    r"TOTAL\s+INVOICE\s*[.:/]?\s*([\d.,]+)",
]

# Destinatario
PATRONES_DESTINATARIO = [
    r"SE[ÑN]OR\(ES\)\s*/\s*MESSRS\s*:\s*(.+?)\s+FECHA",   # formato AquaChile/Blumar
    r"(?:CONSIGNEE|DESTINATARIO|BUYER|COMPRADOR)\s*[.:/]\s*(.+?)(?:\n\n|\n[A-Z]{2,}:)",
    r"SOLD\s+TO\s*[.:/]\s*(.+?)(?:\n\n|\n[A-Z])",
    r"SHIP\s+TO\s*[.:/]\s*(.+?)(?:\n\n|\n[A-Z])",
]

# Dirección del destinatario
PATRONES_DIRECCION = [
    r"DIRECCI[OÓ]N\s*/\s*ADDRESS\s*:\s*(.*?)\s*(?:GIRO\s*:|CIUDAD\s*/\s*CITY\s*:)",
    r"ADDRESS\s*[.:/]\s*(.+?)(?:\n\n|\n[A-Z]{2,}:)",
]

# País de destino — para generar glosa casilla 18
PATRONES_PAIS = [
    r"COUNTRY\s+OF\s+(?:FINAL\s+)?DESTINATION\s*[.:/]\s*([A-Z\s]+?)(?:\n|,)",
    r"DESTINO\s+FINAL\s*[.:/]\s*([A-Z\s]+?)(?:\n|,)",
    r"\b(USA|CHINA|VIETNAM|MEXICO|M[EÉ]XICO|TAIWAN|RUSSIA|COLOMBIA|PANAMA|ARGENTINA)\b",
]

# Certificado sanitario en facturas (algunas lo incluyen)
PATRONES_CERT = [
    r"CERTIFICADO\s+SANITARIO\s*(?:NRO?|N[°º])\s*[.:/]?\s*(\d+)",
    r"N[°º]\s+CODAUT\s*[.:/]\s*(\d+)",
    r"CODAUT\s*[.:/]\s*(\d+)",
]

# Referencia cruzada con la guía — número que coincide con orden_venta en la guía
# Por pesquera, según los documentos reales
PATRONES_REF_PEDIDO_PESQUERA = {
    # Multi X: factura dice "PV: 12345" — guía dice "N° Pedido: 12345"
    "multix":            [r"PV\s*[.:]\s*(\d+)"],
    # AquaChile: factura dice "N° PEDIDO / ORDER: 12345"
    "aquachile":         [r"N[°º]\s*PEDIDO\s*/\s*ORDER\s*[.:/]?\s*(\d+)"],
    # Blumar: valor debajo de "SELLER'S REFERENCE No."
    "blumar":            [r"SELLER'S\s+REFERENCE\s+N[Oo°]\.?\s*[:\n]?\s*(\d+)",
                          r"SELLER.S\s+REFERENCE\s+N[Oo°]\.?\s*[:\n]?\s*(\d+)"],
    "blumar_magallanes": [r"SELLER'S\s+REFERENCE\s+N[Oo°]\.?\s*[:\n]?\s*(\d+)",
                          r"SELLER.S\s+REFERENCE\s+N[Oo°]\.?\s*[:\n]?\s*(\d+)"],
    # Cermaq: factura dice "Order Ref: 12345"
    "cermaq":            [r"ORDER\s+REF\.?\s*[.:/]?\s*(\d+)",
                          r"Order\s+Ref\.?\s*[.:/]?\s*(\d+)"],
    # Australis: fallback
    "australis":         [r"N[°º]\s*PEDIDO\s*[.:/]\s*(\d+)",
                          r"ORDER\s+N[°º]?\s*[.:/]\s*(\d+)"],
}

INCOTERMS_VALIDOS = {"CPT", "CFR", "CIF", "FOB", "FCA", "DAP", "EXW", "DDP"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _limpiar_numeros(texto: str) -> str:
    nums = re.findall(r'\d+', texto)
    return ", ".join(nums) if nums else ""


def _primera_coincidencia(texto: str, patrones: list) -> Optional[str]:
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _extraer_float(texto: str) -> Optional[float]:
    if not texto:
        return None
    t = texto.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        pass
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def _normalizar_pais(raw: str) -> str:
    """Normaliza el país para la glosa de casilla 18."""
    mapa = {
        "USA": "USA", "ESTADOS UNIDOS": "USA", "UNITED STATES": "USA",
        "CHINA": "CHINA", "VIETNAM": "VIETNAM", "VIET NAM": "VIETNAM",
        "MEXICO": "MEXICO", "MÉXICO": "MEXICO",
        "TAIWAN": "TAIWAN", "RUSSIA": "RUSSIA", "RUSIA": "RUSSIA",
        "COLOMBIA": "COLOMBIA", "PANAMA": "PANAMA", "PANAMÁ": "PANAMA",
        "ARGENTINA": "ARGENTINA",
    }
    raw_up = raw.strip().upper()
    for k, v in mapa.items():
        if k in raw_up:
            return v
    return raw_up


# ── Extractor Excel (Blumar y Cermaq envían facturas en .xlsx) ────────────────

def _buscar_celda_excel(ws, texto: str):
    """Busca celda cuyo valor contenga 'texto'. Retorna (row, col) o None."""
    texto_up = texto.upper()
    for row in ws.iter_rows():
        for cell in row:
            if cell.value and texto_up in str(cell.value).upper():
                return cell.row, cell.column
    return None


def _celda_excel(ws, row, col) -> Optional[str]:
    """Retorna valor de celda como string limpio o None."""
    try:
        v = ws.cell(row=row, column=col).value
        return str(v).strip() if v is not None and str(v).strip() not in ("", "None") else None
    except Exception:
        return None


def _texto_excel(ws) -> str:
    """Extrae todo el texto de la hoja como string para detección de pesquera/país."""
    partes = []
    for row in ws.iter_rows():
        for cell in row:
            if cell.value:
                partes.append(str(cell.value))
    return "\n".join(partes)


def extraer_datos_factura_excel(path: str) -> Optional[dict]:
    """
    Extrae datos de una factura de exportación en formato Excel (.xlsx).
    Soporta los formatos de Blumar y Cermaq.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active

        texto_completo = _texto_excel(ws)
        texto_up = texto_completo.upper()

        from modulos.config_cliente import detectar_pesquera
        pesquera = detectar_pesquera(texto_up)

        # ── Número de factura ─────────────────────────────────────────────────
        numero_factura = None
        for label in ["INVOICE NO", "INVOICE N°", "N° FACTURA", "FACTURA N°",
                       "NUMERO FACTURA", "COMMERCIAL INVOICE"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                # Probar celda derecha (col+1) y debajo (row+1)
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v and re.search(r'\d', v):
                    numero_factura = re.sub(r'\D', '', v.split()[0]) or v
                    break

        # ── Referencia cruzada con guía (ref_pedido) ──────────────────────────
        ref_pedido = None
        labels_ref = {
            "blumar":            ["SELLER'S REFERENCE", "SELLERS REFERENCE"],
            "blumar_magallanes": ["SELLER'S REFERENCE", "SELLERS REFERENCE"],
            "cermaq":            ["ORDER REF", "ORDER REFERENCE"],
        }
        for label in labels_ref.get(pesquera, []):
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v:
                    m = re.search(r'(\d+)', v)
                    if m:
                        ref_pedido = m.group(1)
                        break

        # ── Incoterm ──────────────────────────────────────────────────────────
        incoterm = None
        for label in ["INCOTERM", "CLAUSULA DE VENTA", "DELIVERY TERM"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v:
                    m = re.search(r'\b(CPT|CFR|CIF|FOB|FCA|DAP|EXW|DDP)\b', v.upper())
                    if m:
                        incoterm = m.group(1)
                        break
        if not incoterm:
            m = re.search(r'\b(CPT|CFR|CIF|FOB|FCA|DAP|EXW|DDP)\b', texto_up)
            if m:
                incoterm = m.group(1)

        # ── Total ─────────────────────────────────────────────────────────────
        total = None
        for label in ["GRAND TOTAL", "TOTAL INVOICE", "TOTAL AMOUNT", "TOTAL USD",
                       "TOTAL GENERAL", "MONTO TOTAL"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v:
                    total = _extraer_float(v)
                    if total:
                        break

        # ── Destinatario ──────────────────────────────────────────────────────
        destinatario = None
        for label in ["CONSIGNEE", "BUYER", "SOLD TO", "DESTINATARIO", "SHIP TO"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v and len(v) > 3:
                    destinatario = v
                    break

        # ── Moneda ────────────────────────────────────────────────────────────
        moneda = None
        m = re.search(r'\b(USD|CNY|EUR|CLP)\b', texto_up)
        if m:
            moneda = m.group(1)

        # ── País destino ──────────────────────────────────────────────────────
        raw_pais = None
        for label in ["COUNTRY OF DESTINATION", "FINAL DESTINATION", "DESTINO FINAL"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v:
                    raw_pais = v
                    break
        if not raw_pais:
            m = re.search(r'\b(USA|CHINA|VIETNAM|MEXICO|TAIWAN|RUSSIA|COLOMBIA|PANAMA)\b', texto_up)
            if m:
                raw_pais = m.group(1)
        pais_destino = _normalizar_pais(raw_pais) if raw_pais else "USA"

        # ── Bultos (para detección de discrepancias) ──────────────────────────
        bultos = None
        for label in ["TOTAL CAJAS", "TOTAL BOXES", "BULTOS", "PACKAGES", "UNITS"]:
            pos = _buscar_celda_excel(ws, label)
            if pos:
                v = _celda_excel(ws, pos[0], pos[1] + 1) or _celda_excel(ws, pos[0] + 1, pos[1])
                if v:
                    try:
                        bultos = int(float(v.replace(",", "").replace(".", "")))
                        break
                    except Exception:
                        pass

        return {
            "tipo":           "factura",
            "pesquera":       pesquera,
            "numero_factura": numero_factura,
            "ref_pedido":     ref_pedido,
            "incoterm":       incoterm,
            "moneda":         moneda,
            "total":          total,
            "destinatario":   destinatario,
            "direccion":      None,
            "pais_destino":   pais_destino,
            "cert_sanitario": None,
            "bultos":         bultos,
            "texto_completo": texto_completo,
        }

    except Exception as e:
        print(f"[extractor_facturas_excel] Error: {e}")
        return None


# ── Extractor PDF principal ───────────────────────────────────────────────────

def extraer_datos_factura(path: str) -> Optional[dict]:
    """
    Extrae datos de una factura de exportación.
    Soporta PDF y Excel (.xlsx).
    """
    if path.lower().endswith((".xlsx", ".xls")):
        return extraer_datos_factura_excel(path)

    try:
        texto = ""
        with pdfplumber.open(path) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

        if not texto.strip():
            return None

        texto_up = texto.upper()

        # Detectar pesquera primero — necesario para ref_pedido
        from modulos.config_cliente import detectar_pesquera
        pesquera = detectar_pesquera(texto_up)

        # Número de factura
        raw_fact = _primera_coincidencia(texto_up, PATRONES_FACTURA)
        if not raw_fact:
            m_blumar = re.search(PATRON_FACTURA_BLUMAR, texto_up)
            if m_blumar:
                raw_fact = m_blumar.group(1)
        numero_factura = _limpiar_numeros(raw_fact) if raw_fact else None

        # Referencia cruzada con la guía (ref_pedido) — patrón específico por pesquera
        patrones_ref = PATRONES_REF_PEDIDO_PESQUERA.get(pesquera, [])
        raw_ref    = _primera_coincidencia(texto_up, patrones_ref) if patrones_ref else None
        ref_pedido = raw_ref.strip() if raw_ref else None

        # Incoterm
        raw_inco = _primera_coincidencia(texto_up, PATRONES_INCOTERM)
        incoterm = raw_inco.strip().upper() if raw_inco else None
        if incoterm and incoterm not in INCOTERMS_VALIDOS:
            incoterm = None

        # Moneda
        raw_moneda = _primera_coincidencia(texto_up, PATRONES_MONEDA)
        moneda = raw_moneda.strip().upper() if raw_moneda else None

        # Total
        raw_total = _primera_coincidencia(texto_up, PATRONES_TOTAL)
        total = _extraer_float(raw_total)

        # Destinatario
        raw_dest     = _primera_coincidencia(texto, PATRONES_DESTINATARIO)
        destinatario = raw_dest.strip() if raw_dest else None

        # Dirección
        raw_dir = _primera_coincidencia(texto, PATRONES_DIRECCION)
        if raw_dir:
            raw_dir = re.sub(r"TRANSPORTE\s*/\s*TRANSPORT\s*:\s*\S+", "", raw_dir, flags=re.IGNORECASE)
            direccion = re.sub(r"\s+", " ", raw_dir).strip()
        else:
            direccion = None

        # País destino
        raw_pais     = _primera_coincidencia(texto_up, PATRONES_PAIS)
        pais_destino = _normalizar_pais(raw_pais) if raw_pais else "USA"

        # Certificado (algunas facturas lo incluyen)
        raw_cert       = _primera_coincidencia(texto_up, PATRONES_CERT)
        cert_sanitario = raw_cert.strip() if raw_cert else None

        return {
            "tipo":           "factura",
            "pesquera":       pesquera,
            "numero_factura": numero_factura,
            "ref_pedido":     ref_pedido,
            "incoterm":       incoterm,
            "moneda":         moneda,
            "total":          total,
            "destinatario":   destinatario,
            "direccion":      direccion,
            "pais_destino":   pais_destino,
            "cert_sanitario": cert_sanitario,
            "texto_completo": texto,
        }

    except Exception as e:
        print(f"[extractor_facturas] Error: {e}")
        return None
