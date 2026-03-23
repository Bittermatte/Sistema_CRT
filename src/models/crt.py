"""
Modelo canónico del documento CRT siguiendo el estándar ALADI.
Todos los campos son Optional en Fase 1.
Fase 2 añadirá validadores Pydantic y el mapper SQLAlchemy.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from decimal import Decimal


class CRTDocument(BaseModel):
    # Sección 1: Identificación
    numero_crt:            Optional[str]     = Field(None, description="Casilla 1")
    lugar_emision:         Optional[str]     = Field(None, description="Casilla 2")
    fecha_emision:         Optional[date]    = Field(None, description="Casilla 3")
    fecha_documento:       Optional[date]    = Field(None, description="Casilla 5")

    # Sección 2: Remitente
    remitente:             Optional[str]     = Field(None, description="Casilla 4")
    dir_remitente:         Optional[str]     = Field(None, description="Casilla 6")

    # Sección 3: Destinatario
    fecha_entrega:         Optional[date]    = Field(None, description="Casilla 7")
    destinatario:          Optional[str]     = Field(None, description="Casilla 8")
    dir_destinatario:      Optional[str]     = Field(None, description="Casilla 9")

    # Sección 4: Transporte y Ruta
    transportista:         Optional[str]     = Field(None, description="Casilla 10")
    pais_origen:           Optional[str]     = Field(None, description="Casilla 11")
    pais_destino:          Optional[str]     = Field(None, description="Casilla 12")
    lugar_recepcion:       Optional[str]     = Field(None, description="Casilla 13")
    lugar_entrega:         Optional[str]     = Field(None, description="Casilla 16")

    # Sección 5: Condiciones Comerciales
    incoterm:              Optional[str]     = Field(None, description="Casilla 14")
    flete_usd:             Optional[Decimal] = Field(None, description="Casilla 15")
    num_bultos:            Optional[int]     = Field(None, description="Casilla 17")
    instrucciones_aduana:  Optional[str]     = Field(None, description="Casilla 18")

    # Sección 6: Descripción de la Carga
    tipo_embalaje:         Optional[str]     = Field(None, description="Casilla 19")
    descripcion:           Optional[str]     = Field(None, description="Casilla 20")
    peso_neto_kg:          Optional[Decimal] = Field(None, description="Casilla 21")
    peso_bruto_kg:         Optional[Decimal] = Field(None, description="Casilla 22")
    marcas_numeros:        Optional[str]     = Field(None, description="Casilla 23")
    num_factura:           Optional[str]     = Field(None, description="Casilla 24")
