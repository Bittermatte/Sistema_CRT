"""
Fase 1: Helpers de validación de campos CRT.
Fase 2 ampliará con validación de RUT, formatos de fecha, etc.
"""


def is_valid_crt_number(value: str) -> bool:
    """Verifica que el número de CRT no esté vacío."""
    return bool(value and value.strip())


def is_positive_weight(value: float) -> bool:
    """Verifica que el peso sea mayor que cero."""
    return value > 0
