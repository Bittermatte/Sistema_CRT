"""
Audit Log — Sistema CRT.

Genera un archivo JSONL append-only por día en logs/audit_YYYY-MM-DD.jsonl.
Cada línea es un evento JSON independiente.

Eventos:
  documento_extraido — se loguea tras cada extracción de PDF/Excel
  crt_descargado     — se loguea cuando el usuario descarga un PDF

El "diff" en crt_descargado es la prueba legal de qué extrajo el sistema
frente a qué terminó descargando el usuario.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Directorio de logs relativo a la raíz del proyecto
_LOGS_DIR = Path(__file__).parent.parent.parent / "logs"

# Campos de guia_datos que se incluyen en el diff
_CAMPOS_GUIA = [
    "numero_guia", "orden_venta", "peso_bruto", "peso_neto",
    "bultos", "patente_tracto", "patente_semi", "conductor",
    "cert_sanitario", "destinatario", "pesquera", "fecha",
]

# Campos de factura_datos que se incluyen en el diff
_CAMPOS_FACTURA = [
    "numero_factura", "ref_pedido", "incoterm", "moneda", "total",
    "destinatario", "pais_destino", "cert_sanitario", "pesquera", "fecha",
]

# Mapeo campo form_data → (fuente, campo_original)
# Para construir el diff extraccion vs PDF final
_MAPA_DIFF = {
    "f_destinatario":      ("factura", "destinatario"),
    "f_num_factura":       ("factura", "numero_factura"),
    "f_cert_sanitario":    ("factura", "cert_sanitario"),
    "f_peso_bruto":        ("guia",    "peso_bruto"),
    "f_peso_neto":         ("guia",    "peso_neto"),
    "f_total_cajas":       ("guia",    "bultos"),
    "f_valor_mercaderia":  ("factura", "total"),
    "f_incoterm":          ("factura", "incoterm"),
    "f_conductor":         ("guia",    "conductor"),
    "f_patente_camion":    ("guia",    "patente_tracto"),
    "f_patente_rampla":    ("guia",    "patente_semi"),
    "f_guias_despacho":    ("guia",    "numero_guia"),
}


def _log_file() -> Path:
    """Retorna el path del archivo JSONL del día actual."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    return _LOGS_DIR / f"audit_{fecha}.jsonl"


def _append(evento: dict) -> None:
    """Escribe una línea JSON en el archivo del día. Thread-safe por append."""
    linea = json.dumps(evento, ensure_ascii=False, default=str)
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def log_extraccion(
    nombre_archivo: str,
    tipo: str,
    pesquera: str,
    datos_extraidos: dict,
) -> None:
    """
    Loguea la extracción de un documento.
    Llamar desde procesar_documentos() tras cada extraer_documento().
    """
    try:
        campos = _CAMPOS_GUIA if tipo == "guia" else _CAMPOS_FACTURA
        datos_log = {k: datos_extraidos.get(k) for k in campos}
        _append({
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "evento":          "documento_extraido",
            "nombre_archivo":  nombre_archivo,
            "tipo":            tipo,
            "pesquera":        pesquera,
            "datos_extraidos": datos_log,
        })
    except Exception as e:
        print(f"[audit_log] Error logueando extracción: {e}")


def log_descarga(
    crt_id: str,
    correlativo: Optional[str],
    estado: str,
    form_data_final: dict,
    guia_datos: Optional[dict],
    factura_datos: Optional[dict],
    is_fallback: bool = False,
) -> None:
    """
    Loguea la descarga de un CRT por el usuario.
    Incluye diff entre datos extraídos originalmente y datos del PDF final.
    Llamar desde el callback descargar_crt() en elaborar_crt.py.
    """
    try:
        diff = _calcular_diff(form_data_final, guia_datos or {}, factura_datos or {})
        _append({
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "evento":         "crt_descargado",
            "crt_id":         crt_id,
            "correlativo":    correlativo,
            "estado":         estado,
            "is_fallback":    is_fallback,
            "form_data_final": form_data_final,
            "diff":           diff,
        })
    except Exception as e:
        print(f"[audit_log] Error logueando descarga: {e}")


def _calcular_diff(
    form_data: dict,
    guia_datos: dict,
    factura_datos: dict,
) -> dict:
    """
    Compara campos clave del form_data final contra lo que extrajeron
    los parsers originalmente. Retorna solo los campos que difieren.
    """
    diff = {}
    fuentes = {"guia": guia_datos, "factura": factura_datos}

    for campo_form, (fuente, campo_original) in _MAPA_DIFF.items():
        valor_final    = str(form_data.get(campo_form) or "").strip()
        valor_extraido = str(fuentes[fuente].get(campo_original) or "").strip()

        if valor_final != valor_extraido and (valor_final or valor_extraido):
            diff[campo_form] = {
                "extraido": valor_extraido,
                "final":    valor_final,
            }

    return diff
