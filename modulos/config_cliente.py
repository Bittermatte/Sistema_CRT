"""
config_cliente.py — Configuración multi-pesquera AutoCRT

Detección automática del remitente según palabras clave del PDF.
Agregar nueva pesquera: añadir entrada en CONFIGS y keywords en KEYWORDS_PESQUERA.
"""

# ── Configuraciones por pesquera ──────────────────────────────────────────────

CONFIGS = {
    "aquachile": {
        "remitente":         "EMPRESAS AQUACHILE S.A",
        "dir_remitente":     "CARDONAL S/N LOTE B\nPUERTO MONTT - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUERTO NATALES - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. EMPRESAS AQUACHILE S.A.",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
    "blumar_magallanes": {
        "remitente":         "SALMONES BLUMAR MAGALLANES SPA",
        "dir_remitente":     "PUNTA ARENAS - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUNTA ARENAS - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. SALMONES BLUMAR MAGALLANES SPA",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
    "blumar": {
        "remitente":         "SALMONES BLUMAR S.A.",
        "dir_remitente":     "PUNTA ARENAS - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUNTA ARENAS - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. SALMONES BLUMAR S.A.",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
    "multix": {
        "remitente":         "MULTI X S.A.",
        "dir_remitente":     "PUERTO MONTT - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUNTA ARENAS - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. MULTI X S.A.",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
    "australis": {
        "remitente":         "AUSTRALIS MAR S.A.",
        "dir_remitente":     "PUNTA ARENAS - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUNTA ARENAS - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. AUSTRALIS MAR S.A.",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
    "cermaq": {
        "remitente":         "CERMAQ CHILE S.A.",
        "dir_remitente":     "COYHAIQUE - CHILE",
        "transportista":     "TRANSPORTES VESPRINI S.A",
        "dir_transportista": "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA",
        "lugar_emision":     "PUNTA ARENAS - CHILE",
        "tarifa_flete":      4400,
        "firma_remitente":   "p.p. CERMAQ CHILE S.A.",
        "paso_frontera":     "MONTE AYMOND",
        "aeropuerto":        "MINISTRO PISTARINI",
    },
}

# ── Keywords de detección por pesquera ────────────────────────────────────────
# Evaluadas en orden: más específico primero.
# El clasificador busca estas palabras en el texto del PDF (en mayúsculas).

KEYWORDS_PESQUERA = [
    ("blumar_magallanes", ["BLUMAR MAGALLANES", "SALMONES BLUMAR MAGALLANES"]),
    ("blumar",            ["SALMONES BLUMAR S.A", "BLUMAR S.A"]),
    ("aquachile",         ["AQUACHILE", "EMPRESAS AQUACHILE"]),
    ("multix",            ["MULTI X S.A", "MULTI-X", "MULTIX"]),
    ("australis",         ["AUSTRALIS MAR", "AUSTRALIS-SA"]),
    ("cermaq",            ["CERMAQ CHILE", "CERMAQ"]),
]

# Config por defecto si no se detecta ninguna pesquera
CONFIG_ACTIVO = CONFIGS["aquachile"]


# ── Funciones de detección ────────────────────────────────────────────────────

def detectar_pesquera(texto_pdf: str) -> str:
    """
    Detecta la pesquera remitente a partir del texto extraído del PDF.
    Retorna la clave de CONFIGS (ej: 'aquachile', 'blumar_magallanes').
    Retorna 'aquachile' como fallback si no detecta ninguna.
    """
    texto = texto_pdf.upper()
    for clave, keywords in KEYWORDS_PESQUERA:
        for kw in keywords:
            if kw in texto:
                return clave
    return "aquachile"


def get_config(clave: str) -> dict:
    """Retorna la config de una pesquera por su clave."""
    return CONFIGS.get(clave, CONFIGS["aquachile"])


def get_config_desde_texto(texto_pdf: str) -> tuple[str, dict]:
    """
    Detecta la pesquera y retorna (clave, config).
    Uso típico en el orquestador:
        clave, config = get_config_desde_texto(texto_extraido)
    """
    clave = detectar_pesquera(texto_pdf)
    return clave, CONFIGS[clave]
