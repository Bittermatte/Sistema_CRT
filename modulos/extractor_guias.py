import re
import pdfplumber
from typing import Optional

# ── Patrones reales extraídos de 3.198 CRTs históricos ───────────────────────

# Número de guía — 5 variantes reales encontradas
PATRONES_GUIA = [
    r"GUIAS?\s+DE\s+DESPACHO\s+NROS?\s*[.:]\s*([\d,\s\.]+)",
    r"GUIAS?\s+DE\s+DESPACHO\s*[.:]\s*([\d,\s\.]+)",
    r"GUIA\s+DE\s+DESPACHO\s+NRO?\s*[.:]\s*([\d,\s\.]+)",
    r"GUIA\s+DE\s+DESPACHO\s*[.:]\s*([\d]+)",
    r"N[°º]\s+DE\s+GUIA\s*[.:]\s*([\d]+)",
    # Formato SII: "Nº 497318\nS.I.I."
    r"N[°º]\s+(\d+)\s*\n\s*S\.I\.I\.",
]

# Peso bruto — variantes reales
PATRONES_PESO_BRUTO = [
    r"PESO\s+BRUTO\s*:\s*([\d.,]+)\s+Son:",   # formato SII estándar
    r"PESO\s+BRUTO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"BRUTO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"GROSS\s+WEIGHT\s*[.:]\s*([\d.,]+)",
    r"P\.?\s*BRUTO\s*[.:]\s*([\d.,]+)",
]

# Peso neto
PATRONES_PESO_NETO = [
    r"PESO\s+NETO\s*:\s*([\d.,]+)\s+Son:",    # formato SII estándar
    r"PESO\s+NETO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"NET\s+WEIGHT\s*[.:]\s*([\d.,]+)",
    r"P\.?\s*NETO\s*[.:]\s*([\d.,]+)",
]

# Bultos/cajas
PATRONES_BULTOS = [
    r"CANTIDAD\s+DE\s+BULTOS\s*:\s*([\d.,]+)\s+Son:",  # formato SII estándar
    r"BULTOS\s*[.:]\s*(\d+)",
    r"TOTAL\s+CAJAS\s*[.:]\s*(\d+)",
    r"N[°º]\s+BULTOS\s*[.:]\s*(\d+)",
    r"CANTIDAD\s+BULTOS\s*[.:]\s*(\d+)",
    r"(\d+)\s+CAJAS",
]

# Patente — formato chileno nuevo (AB123CD), viejo (AB1234) y argentino (AB123CD)
PATRON_PATENTE_TRACTO = [
    r"CAM[IÍ][OÓ]N\s+PATENTE(.*?)HORA\s+LLEGADA",  # bloque SII con dos placas
    r"PATENTE\s+(?:CAMION|TRACTO|TRACTOR)\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"TRACTO\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"CAMION\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
]

PATRON_PATENTE_SEMI = [
    r"PATENTE\s+(?:RAMPLA|SEMI|REMOLQUE)\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"RAMPLA\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"SEMI\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
]

# Conductor
PATRONES_CONDUCTOR = [
    r"CONDUCTOR\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|RUT|DNI|$)",
    r"CHOFER\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|RUT|$)",
    r"TRANSPORTISTA\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|$)",
]

# Certificado sanitario / Codaut / RUCE / NEPPEX
PATRONES_CERT = [
    r"CERTIFICADO\s+SANITARIO\s*(?:NRO?|N[°º])\s*[.:/]?\s*(\d+)",
    r"CERT(?:IFICADO)?\s+SANITARIO\s*[.:/]\s*(\d+)",
    r"N[°º]\s+CODAUT\s*[.:/]\s*(\d+)",
    r"CODAUT\s*[.:/]\s*(\d+)",
    r"N[°º]\s+RUCE\s*[.:/]\s*(\d+)",
    r"RUCE\s*/\s*NEPPEX\s*[.:/]\s*(\d+)",
    r"NEPPEX\s*[.:/]\s*(\d+)",
]

# Destinatario
PATRONES_DESTINATARIO = [
    r"DESTINATARIO\s*[.:/]\s*(.+?)(?:\n|DIRECCION|DIR\.|RUT)",
    r"CONSIGNATARIO\s*[.:/]\s*(.+?)(?:\n|DIRECCION)",
    r"CLIENTE\s*[.:/]\s*(.+?)(?:\n|RUT|DIRECCION)",
]

# Orden de venta / referencia cruzada con la factura — por pesquera
# El número extraído aquí debe coincidir con ref_pedido en la factura
PATRONES_ORDEN_VENTA_PESQUERA = {
    # Multi X: guía dice "N° Pedido: 12345" — factura dice "PV: 12345"
    "multix":           [r"N[°º]\s*PEDIDO\s*[.:]\s*(\d+)"],
    # AquaChile: guía dice "PEDIDO EXPORTACION 12345"
    "aquachile":        [r"PEDIDO\s+EXPORTACION\s*[.:/]?\s*(\d+)"],
    # Blumar: guía dice "PO: 12345"
    "blumar":           [r"PO\s*[.:]\s*(\d+)"],
    "blumar_magallanes":[r"PO\s*[.:]\s*(\d+)"],
    # Cermaq: guía dice "CO - CLIENTE: 12345 TEXTO" — solo el número
    "cermaq":           [r"CO\s*[-\u2013]\s*CLIENTE\s*[.:]\s*(\d+)"],
    # Australis: fallback genérico (sin patrón específico conocido aún)
    "australis":        [r"ORDEN\s+(?:DE\s+)?VENTA\s*[.:/]\s*(\d+)",
                         r"PURCHASE\s+ORDER\s*[.:/]?\s*(?:N[°º])?\s*(\d+)"],
}

# Fallback genérico cuando la pesquera no tiene patrón específico
PATRONES_ORDEN_VENTA_GENERICO = [
    r"ORDEN\s+DE\s+VENTA\s*[.:/]\s*(\d+)",
    r"N[°º]\s*\.?\s*ORDEN\s+(?:DE\s+)?VENTA\s*[.:/]\s*(\d+)",
    r"PURCHASE\s+ORDER\s*[.:/]?\s*(?:N[°º])?\s*(\d+)",
    r"P\.?O\.?\s*[.:]\s*(\d+)",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _limpiar_numeros(texto: str) -> str:
    """Extrae y limpia lista de números: '545178, 545179' → '545178, 545179'"""
    if not texto:
        return ""
    nums = re.findall(r'\d+', texto)
    return ", ".join(nums) if nums else ""


def _primera_coincidencia(texto: str, patrones: list) -> Optional[str]:
    """Prueba lista de patrones y retorna la primera coincidencia limpia."""
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _extraer_float(texto: str) -> Optional[float]:
    """Convierte '1.234,56' o '1234.56' a float."""
    if not texto:
        return None
    # Formato chileno: punto miles, coma decimal
    t = texto.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        pass
    # Formato anglosajón
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def _extraer_patentes_sii(texto: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extrae tracto y semi del bloque SII 'CAMIÓN PATENTE … HORA LLEGADA'.
    Reconoce formato chileno (AB123CD) y argentino (AB1234 / AB123CD).
    """
    m = re.search(
        r"CAM[IÍ][OÓ]N\s+PATENTE(.*?)HORA\s+LLEGADA",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        placas = re.findall(r"\b([A-Z]{2,3}\d{3,4}[A-Z]{0,2})\b", m.group(1))
        tracto = placas[0] if len(placas) > 0 else None
        semi   = placas[1] if len(placas) > 1 else None
        return tracto, semi
    return None, None


# ── Extractor principal ───────────────────────────────────────────────────────

def extraer_datos_guia(pdf_path: str) -> Optional[dict]:
    """
    Extrae datos de una guía de despacho.
    Retorna dict con campos normalizados o None si falla.
    """
    try:
        texto = ""
        with pdfplumber.open(pdf_path) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

        if not texto.strip():
            return None

        texto_up = texto.upper()

        # Número de guía
        raw_guia    = _primera_coincidencia(texto_up, PATRONES_GUIA)
        numero_guia = _limpiar_numeros(raw_guia) if raw_guia else None

        # Pesos
        raw_pb     = _primera_coincidencia(texto_up, PATRONES_PESO_BRUTO)
        raw_pn     = _primera_coincidencia(texto_up, PATRONES_PESO_NETO)
        peso_bruto = _extraer_float(raw_pb)
        peso_neto  = _extraer_float(raw_pn)

        # Bultos
        raw_bultos = _primera_coincidencia(texto_up, PATRONES_BULTOS)
        bultos = int(_extraer_float(raw_bultos) or 0) if raw_bultos else None
        if bultos == 0:
            bultos = None

        # Patentes — intentar bloque SII primero, luego patrones individuales
        patente_tracto, patente_semi = _extraer_patentes_sii(texto_up)
        if not patente_tracto:
            patente_tracto = _primera_coincidencia(texto_up, PATRON_PATENTE_TRACTO[1:])
        if not patente_semi:
            patente_semi = _primera_coincidencia(texto_up, PATRON_PATENTE_SEMI)

        # Conductor
        raw_cond  = _primera_coincidencia(texto, PATRONES_CONDUCTOR)
        conductor = raw_cond.strip().upper() if raw_cond else None

        # Certificado sanitario / Codaut
        raw_cert       = _primera_coincidencia(texto_up, PATRONES_CERT)
        cert_sanitario = raw_cert.strip() if raw_cert else None

        # Destinatario
        raw_dest     = _primera_coincidencia(texto, PATRONES_DESTINATARIO)
        destinatario = raw_dest.strip() if raw_dest else None

        # Detectar pesquera primero — necesario para elegir el patrón correcto
        from modulos.config_cliente import detectar_pesquera
        pesquera = detectar_pesquera(texto_up)

        # Orden de venta — patrón específico por pesquera, luego fallback genérico
        patrones_ov = (PATRONES_ORDEN_VENTA_PESQUERA.get(pesquera) or []) + PATRONES_ORDEN_VENTA_GENERICO
        raw_ov      = _primera_coincidencia(texto_up, patrones_ov)
        orden_venta = raw_ov.strip() if raw_ov else None

        return {
            "tipo":           "guia",
            "pesquera":       pesquera,
            "numero_guia":    numero_guia,
            "orden_venta":    orden_venta,
            "peso_bruto":     peso_bruto,
            "peso_neto":      peso_neto,
            "bultos":         bultos,
            "patente_tracto": patente_tracto,
            "patente_semi":   patente_semi,
            "conductor":      conductor,
            "cert_sanitario": cert_sanitario,
            "destinatario":   destinatario,
            "texto_completo": texto,
            "productos":      [],   # reservado para parser de tabla por pesquera
        }

    except Exception as e:
        print(f"[extractor_guias] Error: {e}")
        return None
