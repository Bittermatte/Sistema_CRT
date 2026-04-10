"""
motor_agrupacion.py — Lógica de agrupación de documentos en CRTs

Reglas derivadas del análisis de 3.198 CRTs históricos cruzados con Gmail.

La pregunta central: dado un set de guías y facturas del mismo camión,
¿cuántos CRTs se generan y cómo se agrupan?

Respuesta por pesquera y destinatario — ver REGLAS_AGRUPACION.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re


# ── Tipos de datos ────────────────────────────────────────────────────────────

@dataclass
class Documento:
    """Representa una guía o factura individual."""
    tipo: str          # "guia" | "factura"
    pesquera: str      # clave de config_cliente
    numero: str        # número extraído
    destinatario: str  # nombre del cliente final
    datos: dict        # dict completo del extractor
    pdf_bytes: bytes = field(repr=False, default=b"")
    ciudad_destino: str = ""  # ciudad/puerto destino (extraído de la factura)


@dataclass
class GrupoCRT:
    """
    Conjunto de documentos que forman un solo CRT.
    Un GrupoCRT tiene exactamente 1 destinatario y N guías + N facturas.
    """
    pesquera: str
    destinatario: str
    guias: list[Documento] = field(default_factory=list)
    facturas: list[Documento] = field(default_factory=list)
    cert_sanitario: Optional[str] = None
    ciudad_destino: str = ""  # ciudad/puerto destino del grupo

    @property
    def completo(self) -> bool:
        return len(self.guias) > 0 and len(self.facturas) > 0

    @property
    def n_documentos(self) -> int:
        return len(self.guias) + len(self.facturas)


# ── Tabla de clientes que agrupan (por pesquera) ──────────────────────────────
# Si el destinatario hace match con alguno de estos strings,
# todos los documentos del mismo camión van en UN solo CRT.

CLIENTES_AGRUPAN: dict[str, list[str]] = {
    "aquachile":         ["AQUACHILE INC"],
    "blumar_magallanes": ["BLUGLACIER", "BLU GLACIER"],
    "blumar":            ["BLUGLACIER", "BLU GLACIER"],
    "multix":            ["MULTI X INC"],
    "australis":         ["TRAPANANDA SEAFARMS", "COSTCO", "PESCADERIA ATLANTICA",
                          "PESCADERÍA ATLÁNTICA"],
    "cermaq":            ["CERMAQ US LLC"],
}

# Clientes que NUNCA agrupan aunque el destinatario se repita
# (regla explícita de la pesquera)
CLIENTES_NUNCA_AGRUPAN: dict[str, list[str]] = {
    "aquachile": ["AGROSUPER"],
}

# Pesqueras con reglas especiales de descripción
PESQUERAS_DESCRIPCION_INGLES = {"australis"}
PESQUERAS_IGNORAR_FACTURA_LB  = {"australis"}


# ── Funciones de matching ─────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Normaliza texto para comparación: mayúsculas, sin tildes, sin puntuación extra."""
    if not texto:
        return ""
    t = texto.upper().strip()
    reemplazos = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
        "À": "A", "È": "E", "Ì": "I", "Ò": "O", "Ù": "U",
    }
    for orig, remp in reemplazos.items():
        t = t.replace(orig, remp)
    return t


def _cliente_agrupa(pesquera: str, destinatario: str) -> bool:
    """
    Retorna True si este destinatario debe agrupar múltiples GDs en un solo CRT.
    """
    dest_norm = _normalizar(destinatario)

    # Verificar primero si está en la lista de NUNCA AGRUPAN
    nunca = CLIENTES_NUNCA_AGRUPAN.get(pesquera, [])
    for patron in nunca:
        if _normalizar(patron) in dest_norm:
            return False

    # Verificar si está en la lista de AGRUPAN
    agrupan = CLIENTES_AGRUPAN.get(pesquera, [])
    for patron in agrupan:
        if _normalizar(patron) in dest_norm:
            return True

    return False


def _es_factura_lb(factura_datos: dict) -> bool:
    """
    Detecta si una factura es en LB (a ignorar para Australis).
    Busca indicadores de LB en el texto de la factura.
    """
    texto = (factura_datos.get("texto_completo") or "").upper()
    indicadores_lb = [
        "NET WEIGHT LB",
        "POUNDS",
        "LBS NET",
        "WEIGHT IN LB",
        "IN POUNDS",
    ]
    indicadores_kg = [
        "NET WEIGHT KG",
        "KILOGRAMS",
        "KGS NET",
        "WEIGHT IN KG",
        "IN KILOS",
        "NET KG",
    ]
    score_lb = sum(1 for i in indicadores_lb if i in texto)
    score_kg = sum(1 for i in indicadores_kg if i in texto)

    if score_lb > score_kg:
        return True

    nombre = (factura_datos.get("nombre_archivo") or "").upper()
    if "LB" in nombre and "KG" not in nombre:
        return True

    return False


# ── Función principal ─────────────────────────────────────────────────────────

def agrupar_documentos(
    documentos: list[Documento],
    patente_tracto: Optional[str] = None,
) -> list[GrupoCRT]:
    """
    Recibe todos los documentos de un camión (o lote de documentos)
    y retorna una lista de GrupoCRT — uno por cada CRT a generar.

    Parámetros:
        documentos:     lista de Documento (guías y facturas mezcladas)
        patente_tracto: opcional — para agrupar por camión en Multi X

    Retorna:
        lista de GrupoCRT listos para pasar a construir_form_data()
    """
    if not documentos:
        return []

    # Detectar pesquera dominante del lote
    pesqueras = [d.pesquera for d in documentos if d.pesquera]
    pesquera = max(set(pesqueras), key=pesqueras.count) if pesqueras else "aquachile"

    # Separar guías y facturas
    guias    = [d for d in documentos if d.tipo == "guia"]
    facturas = [d for d in documentos if d.tipo == "factura"]

    # Australis: filtrar facturas LB antes de procesar
    if pesquera in PESQUERAS_IGNORAR_FACTURA_LB:
        facturas_filtradas = [f for f in facturas if not _es_factura_lb(f.datos)]
        if facturas_filtradas:
            facturas = facturas_filtradas

    # ── Estrategia de agrupación ──────────────────────────────────────────────

    # Detectar destinatarios únicos en el lote
    destinatarios = set()
    for d in documentos:
        dest = _normalizar(d.destinatario or "")
        if dest:
            destinatarios.add(dest)

    if len(destinatarios) == 1:
        dest = (guias[0].destinatario if guias else facturas[0].destinatario)
        if _cliente_agrupa(pesquera, dest):
            # Agrupar facturas por ciudad destino
            ciudades_facts: dict[str, list] = {}
            for f in facturas:
                c = f.ciudad_destino or ""
                ciudades_facts.setdefault(c, []).append(f)

            if len(ciudades_facts) <= 1:
                # Una sola ciudad (o desconocida) — un único CRT
                ciudad = next(iter(ciudades_facts), "")
                grupos = [GrupoCRT(
                    pesquera=pesquera,
                    destinatario=dest,
                    ciudad_destino=ciudad,
                    guias=guias,
                    facturas=facturas,
                )]
            else:
                # Múltiples ciudades → un CRT por ciudad; guías distribuidas FIFO
                grupos = []
                guias_pool = list(guias)
                for ciudad, facts_ciudad in ciudades_facts.items():
                    n = len(facts_ciudad)
                    g_asignadas = guias_pool[:n]
                    guias_pool  = guias_pool[n:]
                    grupos.append(GrupoCRT(
                        pesquera=pesquera,
                        destinatario=dest,
                        ciudad_destino=ciudad,
                        guias=g_asignadas,
                        facturas=facts_ciudad,
                    ))
                if guias_pool:
                    grupos.append(GrupoCRT(
                        pesquera=pesquera,
                        destinatario=dest,
                        guias=guias_pool,
                    ))
        else:
            # 1 GD + 1 factura = 1 CRT (zip por orden)
            grupos = _agrupar_uno_a_uno(pesquera, guias, facturas)
    else:
        # Múltiples destinatarios — agrupar por destinatario
        grupos = _agrupar_por_destinatario(pesquera, guias, facturas)

    return [g for g in grupos if g.n_documentos > 0]


def _agrupar_uno_a_uno(
    pesquera: str,
    guias: list[Documento],
    facturas: list[Documento],
) -> list[GrupoCRT]:
    """
    Crea un GrupoCRT por cada par guía-factura.
    Intenta hacer match por destinatario cuando hay desigualdad de cantidad.
    """
    grupos = []
    usadas_facturas = set()

    for guia in guias:
        factura_match = None
        dest_guia = _normalizar(guia.destinatario or "")

        for i, factura in enumerate(facturas):
            if i in usadas_facturas:
                continue
            dest_fact = _normalizar(factura.destinatario or "")
            if dest_guia and dest_fact and dest_guia == dest_fact:
                factura_match = factura
                usadas_facturas.add(i)
                break

        if factura_match is None:
            for i, factura in enumerate(facturas):
                if i not in usadas_facturas:
                    factura_match = factura
                    usadas_facturas.add(i)
                    break

        grupos.append(GrupoCRT(
            pesquera=pesquera,
            destinatario=guia.destinatario or "",
            guias=[guia],
            facturas=[factura_match] if factura_match else [],
        ))

    # Facturas sobrantes sin guía (estado FALTA_GUIA)
    for i, factura in enumerate(facturas):
        if i not in usadas_facturas:
            grupos.append(GrupoCRT(
                pesquera=pesquera,
                destinatario=factura.destinatario or "",
                guias=[],
                facturas=[factura],
            ))

    return grupos


def _agrupar_por_destinatario(
    pesquera: str,
    guias: list[Documento],
    facturas: list[Documento],
) -> list[GrupoCRT]:
    """
    Agrupa documentos por destinatario normalizado.
    Para clientes que agregan, también separa por ciudad_destino (Miami ≠ New York).
    Dentro de cada grupo aplica la regla de agrupación.
    """
    grupos_por_dest: dict[str, GrupoCRT] = {}

    # ── Paso 1: procesar guías ────────────────────────────────────────────────
    for guia in guias:
        dest = _normalizar(guia.destinatario or "DESCONOCIDO")
        if _cliente_agrupa(pesquera, guia.destinatario or ""):
            # Guías van a un bucket genérico por dest (sin ciudad — se redistribuirán)
            if dest not in grupos_por_dest:
                grupos_por_dest[dest] = GrupoCRT(
                    pesquera=pesquera,
                    destinatario=guia.destinatario or "",
                )
            grupos_por_dest[dest].guias.append(guia)
        else:
            clave = f"{dest}_{guia.numero}"
            grupos_por_dest[clave] = GrupoCRT(
                pesquera=pesquera,
                destinatario=guia.destinatario or "",
                guias=[guia],
            )

    # ── Paso 2: procesar facturas ─────────────────────────────────────────────
    for factura in facturas:
        dest   = _normalizar(factura.destinatario or "DESCONOCIDO")
        ciudad = _normalizar(factura.ciudad_destino or "")

        if _cliente_agrupa(pesquera, factura.destinatario or ""):
            # Clave por (dest, ciudad) para separar CRTs por ciudad de destino
            clave_agrup = f"{dest}_{ciudad}" if ciudad else dest
            if clave_agrup not in grupos_por_dest:
                grupos_por_dest[clave_agrup] = GrupoCRT(
                    pesquera=pesquera,
                    destinatario=factura.destinatario or "",
                    ciudad_destino=factura.ciudad_destino or "",
                )
            grupos_por_dest[clave_agrup].facturas.append(factura)
        else:
            encontrado = False
            for clave, grupo in grupos_por_dest.items():
                if (_normalizar(grupo.destinatario) == dest
                        and len(grupo.facturas) == 0
                        and len(grupo.guias) == 1):
                    grupo.facturas.append(factura)
                    encontrado = True
                    break
            if not encontrado:
                clave = f"{dest}_fact_{factura.numero}"
                grupos_por_dest[clave] = GrupoCRT(
                    pesquera=pesquera,
                    destinatario=factura.destinatario or "",
                    facturas=[factura],
                )

    # ── Paso 3: redistribuir guías del bucket genérico a grupos por ciudad ────
    # Cuando existen tanto un bucket genérico (key=dest) como grupos por ciudad
    # (key=dest_ciudad), mover las guías del bucket genérico a los grupos ciudad FIFO.
    for dest_key in list(grupos_por_dest.keys()):
        grupo_generico = grupos_por_dest.get(dest_key)
        if grupo_generico is None or grupo_generico.ciudad_destino:
            continue  # solo procesar buckets genéricos (sin ciudad)
        if not grupo_generico.guias:
            continue

        # Buscar grupos con ciudad específica para este mismo destinatario
        dest_norm = _normalizar(grupo_generico.destinatario)
        grupos_ciudad = [
            (k, g) for k, g in grupos_por_dest.items()
            if k != dest_key
            and _normalizar(g.destinatario) == dest_norm
            and g.ciudad_destino
        ]

        if not grupos_ciudad:
            continue  # sin grupos por ciudad → dejar el bucket genérico tal cual

        # Distribuir guías FIFO entre los grupos ciudad
        guias_pool = list(grupo_generico.guias)
        for _, g_ciudad in grupos_ciudad:
            n = len(g_ciudad.facturas)
            asignadas = guias_pool[:n]
            guias_pool = guias_pool[n:]
            g_ciudad.guias.extend(asignadas)

        if guias_pool:
            # Guías sobrantes van al primer grupo ciudad
            grupos_ciudad[0][1].guias.extend(guias_pool)

        # Eliminar el bucket genérico ya vacío
        del grupos_por_dest[dest_key]

    return list(grupos_por_dest.values())


# ── Helpers para Australis ────────────────────────────────────────────────────

def consolidar_productos_australis(grupos: list[GrupoCRT]) -> list[GrupoCRT]:
    """
    Para Australis: consolida líneas de producto idénticas sumando cajas y kilos.
    Líneas con descripción EXACTAMENTE igual → se suman.
    Se aplica DESPUÉS de agrupar_documentos().

    Modifica grupo.facturas[0].datos["productos"] con la lista consolidada
    para que _merge_facturas() del orquestador lo recoja correctamente.
    """
    for grupo in grupos:
        if grupo.pesquera != "australis" or not grupo.facturas:
            continue

        acumulados: dict[str, dict] = {}

        for factura in grupo.facturas:
            items = factura.datos.get("productos") or []
            for item in items:
                nombre = (item.get("descripcion") or "").strip()
                if not nombre:
                    continue
                # Campos reales del extractor: cajas_totales, kilos_totales
                cajas = item.get("cajas_totales", 0) or 0
                kilos = item.get("kilos_totales", 0) or 0

                if nombre in acumulados:
                    acumulados[nombre]["cajas_totales"] += cajas
                    acumulados[nombre]["kilos_totales"] += kilos
                else:
                    acumulados[nombre] = {
                        "descripcion":   nombre,
                        "familia":       nombre,
                        "cajas_totales": cajas,
                        "kilos_totales": kilos,
                    }

        # Escribir la lista consolidada en la primera factura del grupo
        # (el orquestador llama _merge_facturas que toma datos de facturas[0])
        if grupo.facturas:
            grupo.facturas[0].datos["productos"] = list(acumulados.values())

    return grupos


# ── Test básico ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    casos = [
        ("aquachile",         "AQUACHILE INC.",                   True),
        ("aquachile",         "Agrosuper China Co., Ltd.",        False),
        ("aquachile",         "BB REFRIGERACION, S. DE R.L.",     False),
        ("blumar_magallanes", "BluGlacier, LLC.",                 True),
        ("blumar_magallanes", "BB REFRIGERACION, S. DE R.L.",     False),
        ("multix",            "MULTI X INC",                      True),
        ("multix",            "Chengdu International Trade",      False),
        ("australis",         "TRAPANANDA SEAFARMS, LLC",         True),
        ("australis",         "Costco C/O Pescadería Atlántica",  True),
        ("australis",         "JSC RUSSIAN FISH COMPANY",         False),
        ("cermaq",            "CERMAQ US LLC",                    True),
        ("cermaq",            "ZHEJIANG OCEAN FAMILY CO., LTD.",  False),
    ]

    ok = 0
    print("Test motor_agrupacion.py:")
    for pesquera, dest, esperado in casos:
        resultado = _cliente_agrupa(pesquera, dest)
        estado = "OK" if resultado == esperado else "FALLO"
        if resultado == esperado:
            ok += 1
        print(f"  {estado} | {pesquera:20s} | {dest[:35]:35s} | agrupa={resultado}")
    print(f"\nResultado: {ok}/{len(casos)} correctos")
