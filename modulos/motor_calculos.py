"""
Módulo 3 — Motor de cálculos de flete para CRT.
Aplica la fórmula de prorrateo según la matriz de AquaChile.
"""


def calcular_fletes(
    peso_bruto_cliente: float,
    peso_bruto_total_camion: float,
    tarifa_base_viaje: float,
) -> dict:
    """
    Calcula el flete prorrateado de un cliente y lo desglosa en dos tramos.

    Fórmula (orden estricto según matriz):
        flete_prorrateado = (peso_bruto_cliente * tarifa_base_viaje) / peso_bruto_total_camion

    Desglose:
        flete_origen_frontera      =  8% del flete prorrateado
        flete_frontera_destino     = 92% del flete prorrateado

    Retorna un diccionario con los 3 valores redondeados a 2 decimales.
    """
    flete_prorrateado = (peso_bruto_cliente * tarifa_base_viaje) / peso_bruto_total_camion

    return {
        "flete_prorrateado":      round(flete_prorrateado, 2),
        "flete_origen_frontera":  round(flete_prorrateado * 0.08, 2),
        "flete_frontera_destino": round(flete_prorrateado * 0.92, 2),
    }


# ── Bloque de prueba ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    peso_cliente  = 3_958.52
    peso_total    = 18_344.22
    tarifa        = 4_400.00

    resultado = calcular_fletes(peso_cliente, peso_total, tarifa)

    print(f"\n{'─' * 48}")
    print(f"  Datos de entrada")
    print(f"{'─' * 48}")
    print(f"  Peso bruto cliente   : {peso_cliente:>10.2f} kg")
    print(f"  Peso bruto camión    : {peso_total:>10.2f} kg")
    print(f"  Tarifa base viaje    : {tarifa:>10.2f} USD")
    print(f"{'─' * 48}")
    print(f"  Resultados")
    print(f"{'─' * 48}")
    print(f"  Flete prorrateado    : {resultado['flete_prorrateado']:>10.2f} USD")
    print(f"  Origen → Frontera (8%): {resultado['flete_origen_frontera']:>9.2f} USD")
    print(f"  Frontera → Destino (92%): {resultado['flete_frontera_destino']:>6.2f} USD")
    print()
