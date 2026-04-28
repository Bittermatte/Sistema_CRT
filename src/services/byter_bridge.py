"""
byter_bridge.py — Puente entre el orchestrator y sheets_service.

Byter llama a esta función con los bytes de los archivos.
Retorna lista de resultados listos para notificar a Luis por Telegram.
"""

from src.services.orchestrator import procesar_documentos
from src.services.sheets_service import generate_crt_sheets


def procesar_y_generar(store: dict, archivos: list[tuple[str, bytes]]) -> dict:
    """
    Parámetros:
        store:    {"crts": {}, "next_numero": 5000}
        archivos: [(nombre_archivo, file_bytes), ...]

    Retorna:
        {
          "store":     store actualizado,
          "errores":   [str],
          "pdfs":      [{"correlativo": str, "pesquera": str, "pdf_bytes": bytes, "crt": dict}],
          "pendientes": [{"estado": str, "pesquera": str, "patente": str}],
        }
    """
    store_nuevo, errores = procesar_documentos(store, archivos)

    pdfs      = []
    pendientes = []

    for crt_id, crt in store_nuevo["crts"].items():
        estado = crt.get("estado")

        if estado == "COMPLETO" and crt.get("form_data"):
            # Solo generar PDF si no se generó antes
            if crt.get("pdf_bytes"):
                continue
            pdf_bytes, error = generate_crt_sheets(
                form_data=crt["form_data"],
                pesquera=crt.get("pesquera", "desconocida"),
            )
            if not error and pdf_bytes:
                crt["pdf_bytes"] = pdf_bytes
                pdfs.append({
                    "correlativo": crt.get("correlativo", "SIN_CORRELATIVO"),
                    "pesquera":    crt.get("pesquera", ""),
                    "pdf_bytes":   pdf_bytes,
                    "crt":         crt,
                })
            else:
                errores.append(f"Error generando PDF para CRT {crt.get('correlativo')}")

        elif estado in ("FALTA_FACTURA", "FALTA_GUIA", "AMBIGUO"):
            guia     = crt.get("guia_datos") or {}
            factura  = crt.get("factura_datos") or {}
            pendientes.append({
                "estado":   estado,
                "pesquera": crt.get("pesquera", ""),
                "patente":  guia.get("patente_tracto", ""),
                "crt_id":   crt_id,
            })

    return {
        "store":      store_nuevo,
        "errores":    errores,
        "pdfs":       pdfs,
        "pendientes": pendientes,
    }
