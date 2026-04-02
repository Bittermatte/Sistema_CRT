"""
Módulo 5 — Generador de PDF del CRT.
Superpone los datos del envío sobre la plantilla crt_blanco.pdf usando
reportlab (canvas de texto) + pypdf (merge de capas).
"""

import io
import os

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter

# ── Coordenadas (x, y) en puntos PDF (origen = esquina inferior-izquierda) ───
# Ajustar estos valores en la fase de calibración visual.
COORDENADAS = {
    "numero_crt":          (480, 698),
    "remitente":           ( 60, 650),
    "destinatario":        ( 60, 600),
    "direccion":           ( 60, 580),
    "pais_destino":        ( 60, 560),
    "casilla_8":           ( 60, 480),
    "descripcion_carga":   ( 60, 420),
    "bultos":              ( 60, 380),
    "peso_neto":           (200, 380),
    "peso_bruto":          (340, 380),
    "flete_total":         (480, 320),
    "flete_8_pct":         (480, 300),
    "flete_92_pct":        (480, 280),
    "patente_tracto":      ( 60, 120),
    "patente_semi":        (200, 120),
    "casilla_18":          ( 60,  80),
}


def generar_pdf_crt(
    datos_completos: dict,
    ruta_plantilla: str,
    ruta_salida: str,
) -> None:
    """
    Superpone datos_completos sobre ruta_plantilla y guarda el PDF en ruta_salida.

    Pasos:
        1. Crear un canvas reportlab en memoria (tamaño letter).
        2. Escribir cada campo en la coordenada definida en COORDENADAS.
        3. Abrir ruta_plantilla con pypdf y fusionar la capa de texto.
        4. Guardar el resultado en ruta_salida.
    """
    # 1 — Canvas temporal en memoria
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 9)

    # 2 — Imprimir cada campo en su coordenada
    # Tolerancia a fallos: None o campos ausentes se renderizan como cadena vacía.
    for campo, texto in datos_completos.items():
        if campo in COORDENADAS:
            x, y = COORDENADAS[campo]
            valor = str(texto) if texto is not None else ""
            if valor:                        # no llamar drawString con cadena vacía
                c.drawString(x, y, valor)

    c.save()
    buffer.seek(0)

    # 3 — Fusionar con la plantilla
    plantilla_pdf = PdfReader(ruta_plantilla)
    overlay_pdf   = PdfReader(buffer)

    writer = PdfWriter()
    pagina_base    = plantilla_pdf.pages[0]
    pagina_overlay = overlay_pdf.pages[0]

    pagina_base.merge_page(pagina_overlay)
    writer.add_page(pagina_base)

    # 4 — Guardar resultado
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    with open(ruta_salida, "wb") as f:
        writer.write(f)

    print(f"  PDF generado → {ruta_salida}")


# ── Bloque de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Resolver rutas relativas al proyecto (un nivel arriba de /modulos/)
    DIR_MODULOS  = os.path.dirname(os.path.abspath(__file__))
    DIR_PROYECTO = os.path.dirname(DIR_MODULOS)

    ruta_plantilla = os.path.join(DIR_PROYECTO, "plantillas", "crt_blanco.pdf")
    ruta_salida    = os.path.join(DIR_PROYECTO, "crts_generados", "prueba_coordenadas.pdf")

    datos_prueba = {
        "numero_crt":        "5098/2026VSP",
        "remitente":         "EMPRESAS AQUACHILE S.A.",
        "destinatario":      "AGROSUPER CHINA CO., LTD.",
        "direccion":         "ROOM 1702-03 NO.168 XIZANG ROAD, SHANGHAI, CHINA",
        "pais_destino":      "CHINA",
        "casilla_8":         "AEROPUERTO INT. MINISTRO PISTARINI BUENOS AIRES ARGENTINA-DESTINO FINAL CHINA",
        "descripcion_carga": "SALMON DEL ATLANTICO CRUDO ENTERO SIN VISCERAS/HON PREMIUM 6-8KG — 90 CAJAS",
        "bultos":            "90",
        "peso_neto":         "1827.48 KG",
        "peso_bruto":        "2189.19 KG",
        "flete_total":       "USD 949.48",
        "flete_8_pct":       "USD 75.96",
        "flete_92_pct":      "USD 873.52",
        "patente_tracto":    "AE296NK",
        "patente_semi":      "AF260YK",
        "casilla_18":        "MERCADERIA EN TRANSITO POR ARGENTINA. SALIDA POR PASO MONTE AYMOND.",
    }

    print(f"\n{'─' * 55}")
    print(f"  Generando CRT de prueba...")
    print(f"  Plantilla : {ruta_plantilla}")
    print(f"  Salida    : {ruta_salida}")
    print(f"{'─' * 55}")

    generar_pdf_crt(datos_prueba, ruta_plantilla, ruta_salida)

    print(f"{'─' * 55}")
    print(f"  Abre el archivo para calibrar las coordenadas.")
    print()
