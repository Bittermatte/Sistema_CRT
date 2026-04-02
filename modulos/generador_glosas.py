"""
Módulo 4 — Generador de textos y correlativo para el CRT.
Construye las glosas fijas de las casillas 8, 18 y 2.
"""

import datetime


def generar_textos_crt(pais_destino: str, numero_base: int) -> dict:
    """
    Genera los textos de las casillas 8, 18 y el correlativo de la casilla 2.

    Parámetros:
        pais_destino  — país de destino final de la mercadería (ej. 'Mexico')
        numero_base   — número base del CRT (ej. 5098)

    Retorna un diccionario con:
        correlativo_casilla_2  — "{numero_base}/{año_actual}VSP"
        texto_casilla_8        — ruta con destino final
        texto_casilla_18       — declaración de tránsito completa
    """
    pais = pais_destino.upper()
    anio = datetime.datetime.now().year

    correlativo_casilla_2 = f"{numero_base}/{anio}VSP"

    texto_casilla_8 = (
        f"AEROPUERTO INT. MINISTRO PISTARINI BUENOS AIRES ARGENTINA"
        f"-DESTINO FINAL {pais}"
    )

    texto_casilla_18 = (
        f"MERCADERIA PARA SER EXPORTADA A {pais} EN TRANSITO POR LA "
        f"REPUBLICA ARGENTINA, SALIDA DE CHILE POR EL PASO MONTE AYMOND "
        f"Y SALIDA DE ARGENTINA POR EL AEROPUERTO INTERNACIONAL "
        f"MINISTRO PISTARINI."
    )

    return {
        "correlativo_casilla_2": correlativo_casilla_2,
        "texto_casilla_8": texto_casilla_8,
        "texto_casilla_18": texto_casilla_18,
    }


# ── Bloque de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    resultado = generar_textos_crt(pais_destino="Mexico", numero_base=5098)

    print(f"\n{'─' * 60}")
    print(f"  Casilla 2  — Correlativo")
    print(f"{'─' * 60}")
    print(f"  {resultado['correlativo_casilla_2']}")

    print(f"\n{'─' * 60}")
    print(f"  Casilla 8  — Ruta / Destino")
    print(f"{'─' * 60}")
    print(f"  {resultado['texto_casilla_8']}")

    print(f"\n{'─' * 60}")
    print(f"  Casilla 18 — Declaración de tránsito")
    print(f"{'─' * 60}")
    print(f"  {resultado['texto_casilla_18']}")
    print()
