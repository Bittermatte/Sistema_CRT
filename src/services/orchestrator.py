"""
Orquestador central del sistema AutoCRT.

Responsabilidad única: coordinar el flujo completo de procesamiento
de documentos. El frontend solo llama a este módulo.

Flujo:
  PDF (bytes) → clasificar → extraer → matching → recalcular fletes
              → actualizar store → [si COMPLETO] construir form_data

No importa si los documentos vienen del frontend manual o del Gmail
automático — el orquestador los procesa igual en ambos casos.
"""

import difflib
import io
import os
import re
import tempfile
import uuid
from typing import Optional

from modulos.extractor_guias    import extraer_datos_guia
from modulos.extractor_facturas import extraer_datos_factura
from modulos.motor_calculos     import calcular_fletes
from modulos.generador_glosas   import generar_textos_crt
from modulos.config_cliente     import CONFIG_ACTIVO, get_config_desde_texto

# ── Constantes ────────────────────────────────────────────────────────────────
MATCH_THRESHOLD      = 0.50
ESTADO_COMPLETO      = "COMPLETO"
ESTADO_FALTA_FACTURA = "FALTA_FACTURA"
ESTADO_FALTA_GUIA    = "FALTA_GUIA"

# ── Detección automática de pesquera ─────────────────────────────────────────
PESQUERAS = {
    "AQUACHILE":  ["EMPRESAS AQUACHILE", "AQUACHILE S.A"],
    "BLUMAR":     ["SALMONES BLUMAR MAGALLANES", "SALMONES BLUMAR S.A"],
    "MULTIX":     ["MULTI X S.A", "MULTI X SALMON"],
    "AUSTRALIS":  ["AUSTRALIS MAR S.A"],
    "CERMAQ":     ["CERMAQ CHILE S.A"],
}


def detectar_pesquera(texto: str) -> str:
    """Detecta la pesquera remitente según el texto del PDF."""
    texto_upper = texto.upper()
    for pesquera, keywords in PESQUERAS.items():
        if any(kw in texto_upper for kw in keywords):
            return pesquera
    return "DESCONOCIDA"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _extraer_texto_raw(pdf_bytes: bytes) -> str:
    """Extrae texto crudo del PDF para detección de pesquera."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages[:2])
    except Exception:
        return ""


# ── Clasificador ──────────────────────────────────────────────────────────────
def clasificar_documento(file_bytes: bytes, nombre: str) -> Optional[str]:
    """
    Determina si el documento es 'guia' o 'factura'.
    - Excel (.xlsx/.xls): siempre 'factura' (solo Blumar/Cermaq envían facturas en Excel)
    - PDF: clasifica por contenido
    Retorna None si no puede clasificar.
    """
    ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
    if ext in ("xlsx", "xls"):
        return "factura"

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            texto = "\n".join(
                p.extract_text() or "" for p in pdf.pages[:2]
            ).upper()

        if not texto.strip():
            return None

        score_guia = sum(1 for k in [
            "GUIA DE DESPACHO", "GUÍA DE DESPACHO",
            "PESO BRUTO", "PESO NETO", "PATENTE",
            "BULTOS", "N° DE GUIA", "NRO. GUIA"
        ] if k in texto)

        score_factura = sum(1 for k in [
            "FACTURA", "INCOTERM", "CURRENCY", "INVOICE",
            "TOTAL USD", "TOTAL CNY", "EXPORTACION",
            "COMMERCIAL INVOICE", "FACTURA DE EXPORTACION"
        ] if k in texto)

        if score_guia == 0 and score_factura == 0:
            return None
        return "guia" if score_guia >= score_factura else "factura"

    except Exception:
        return None


# Alias para compatibilidad con código que aún usa clasificar_pdf
def clasificar_pdf(pdf_bytes: bytes) -> Optional[str]:
    return clasificar_documento(pdf_bytes, "archivo.pdf")


# ── Extractor ─────────────────────────────────────────────────────────────────
def extraer_documento(file_bytes: bytes, tipo: str, nombre: str) -> Optional[dict]:
    """Extrae datos del documento (PDF o Excel) según tipo ('guia' o 'factura')."""
    ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else "pdf"
    sufijo = f".{ext}"
    with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        if tipo == "guia":
            return extraer_datos_guia(tmp_path)
        elif tipo == "factura":
            return extraer_datos_factura(tmp_path)
        return None
    except Exception as e:
        print(f"[orchestrator] Error extrayendo {tipo}: {e}")
        return None
    finally:
        os.unlink(tmp_path)


# Alias para compatibilidad
def extraer_pdf(pdf_bytes: bytes, tipo: str) -> Optional[dict]:
    return extraer_documento(pdf_bytes, tipo, "archivo.pdf")


# ── Matching ──────────────────────────────────────────────────────────────────
def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.upper(), b.upper()).ratio()


def _normalizar_num(v) -> Optional[str]:
    """Extrae solo dígitos de un valor, para comparación numérica limpia."""
    if not v:
        return None
    nums = re.findall(r'\d+', str(v))
    return "".join(nums) if nums else None


def detectar_discrepancias(guia_datos: dict, factura_datos: dict) -> list[str]:
    """
    Compara campos logísticos entre guía y factura ya matcheadas.
    Retorna lista de strings de advertencia (vacía si todo coincide).
    El valor monetario NO se verifica — solo manda la factura.
    """
    avisos = []
    num_g = guia_datos.get("numero_guia", "?")
    num_f = factura_datos.get("numero_factura", "?")

    # Bultos
    bultos_g = guia_datos.get("bultos")
    bultos_f = factura_datos.get("bultos")
    if bultos_g is not None and bultos_f is not None:
        try:
            if int(bultos_g) != int(bultos_f):
                avisos.append(
                    f"Discrepancia bultos — Guía {num_g}: {bultos_g} cajas "
                    f"vs Factura {num_f}: {bultos_f} cajas."
                )
        except (TypeError, ValueError):
            pass

    # Peso bruto
    pb_g = guia_datos.get("peso_bruto")
    pb_f = factura_datos.get("peso_bruto")
    if pb_g is not None and pb_f is not None:
        try:
            if abs(float(pb_g) - float(pb_f)) > 1.0:   # tolerancia 1 kg
                avisos.append(
                    f"Discrepancia peso bruto — Guía {num_g}: {pb_g} kg "
                    f"vs Factura {num_f}: {pb_f} kg."
                )
        except (TypeError, ValueError):
            pass

    # Peso neto
    pn_g = guia_datos.get("peso_neto")
    pn_f = factura_datos.get("peso_neto")
    if pn_g is not None and pn_f is not None:
        try:
            if abs(float(pn_g) - float(pn_f)) > 1.0:
                avisos.append(
                    f"Discrepancia peso neto — Guía {num_g}: {pn_g} kg "
                    f"vs Factura {num_f}: {pn_f} kg."
                )
        except (TypeError, ValueError):
            pass

    return avisos


def buscar_match_guia(factura_datos: dict, crts: dict) -> Optional[str]:
    """
    Busca CRT en FALTA_FACTURA que matchee con la factura recibida.
    4 capas en orden de confianza:
      0. orden_venta (guía) == numero_factura  ← más confiable
      1. Certificado sanitario exacto
      2. Destinatario por similitud (≥ 0.50)
      3. Misma pesquera + único candidato
    """
    # Capa 0: ref_pedido (factura) == orden_venta (guía)
    # ref_pedido es el campo específico de la factura que cruza con la guía
    # (ej: "PV:" en Multi X, "SELLER'S REFERENCE" en Blumar, "Order Ref" en Cermaq)
    ref_f = _normalizar_num(factura_datos.get("ref_pedido"))
    if ref_f:
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_FACTURA:
                continue
            ov_g = _normalizar_num(crt.get("guia_datos", {}).get("orden_venta"))
            if ov_g and ov_g == ref_f:
                return crt_id

    # Capa 1: cert_sanitario exacto
    cert_f = (factura_datos.get("cert_sanitario") or "").strip()
    if cert_f:
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_FACTURA:
                continue
            cert_g = (crt.get("guia_datos", {}).get("cert_sanitario") or "").strip()
            if cert_g and cert_g == cert_f:
                return crt_id

    # Capa 2: destinatario por similitud
    dest_f = (factura_datos.get("destinatario") or "").strip()
    if dest_f:
        mejor_id, mejor_ratio = None, 0.0
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_FACTURA:
                continue
            dest_g = (crt.get("guia_datos", {}).get("destinatario") or "").strip()
            r = _ratio(dest_f, dest_g)
            if r >= MATCH_THRESHOLD and r > mejor_ratio:
                mejor_ratio, mejor_id = r, crt_id
        if mejor_id:
            return mejor_id

    # Capa 3: misma pesquera + único candidato
    pesquera_f = factura_datos.get("pesquera", "DESCONOCIDA")
    if pesquera_f != "DESCONOCIDA":
        candidatos = [
            crt_id for crt_id, crt in crts.items()
            if crt.get("estado") == ESTADO_FALTA_FACTURA
            and crt.get("pesquera") == pesquera_f
        ]
        if len(candidatos) == 1:
            return candidatos[0]

    return None


def buscar_match_factura(guia_datos: dict, crts: dict) -> Optional[str]:
    """
    Busca CRT en FALTA_GUIA que matchee con la guía recibida.
    4 capas en orden de confianza:
      0. orden_venta (guía) == numero_factura  ← más confiable
      1. Certificado sanitario exacto
      2. Destinatario por similitud (≥ 0.50)
      3. Misma pesquera + único candidato
    """
    # Capa 0: orden_venta (guía) == ref_pedido (factura en espera)
    ov_g = _normalizar_num(guia_datos.get("orden_venta"))
    if ov_g:
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_GUIA:
                continue
            ref_f = _normalizar_num(crt.get("factura_datos", {}).get("ref_pedido"))
            if ref_f and ref_f == ov_g:
                return crt_id

    # Capa 1: cert_sanitario exacto
    cert_g = (guia_datos.get("cert_sanitario") or "").strip()
    if cert_g:
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_GUIA:
                continue
            cert_f = (crt.get("factura_datos", {}).get("cert_sanitario") or "").strip()
            if cert_f and cert_f == cert_g:
                return crt_id

    # Capa 2: destinatario por similitud
    dest_g = (guia_datos.get("destinatario") or "").strip()
    if dest_g:
        mejor_id, mejor_ratio = None, 0.0
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_FALTA_GUIA:
                continue
            dest_f = (crt.get("factura_datos", {}).get("destinatario") or "").strip()
            r = _ratio(dest_g, dest_f)
            if r >= MATCH_THRESHOLD and r > mejor_ratio:
                mejor_ratio, mejor_id = r, crt_id
        if mejor_id:
            return mejor_id

    # Capa 3: misma pesquera + único candidato
    pesquera_g = guia_datos.get("pesquera", "DESCONOCIDA")
    if pesquera_g != "DESCONOCIDA":
        candidatos = [
            crt_id for crt_id, crt in crts.items()
            if crt.get("estado") == ESTADO_FALTA_GUIA
            and crt.get("pesquera") == pesquera_g
        ]
        if len(candidatos) == 1:
            return candidatos[0]

    return None


# ── Prorrateo de fletes ───────────────────────────────────────────────────────
def recalcular_fletes(crts: dict) -> dict:
    """Prorratea el flete por peso bruto entre CRTs del mismo camión (patente)."""
    try:
        from collections import defaultdict
        grupos = defaultdict(list)
        for crt_id, crt in crts.items():
            if crt.get("estado") != ESTADO_COMPLETO:
                continue
            patente = (crt.get("guia_datos", {}).get("patente_tracto") or "SIN_PATENTE")
            grupos[patente].append(crt_id)

        for patente, ids in grupos.items():
            peso_total = sum(
                float(crts[i].get("guia_datos", {}).get("peso_bruto") or 0)
                for i in ids
            )
            if peso_total <= 0:
                continue
            for crt_id in ids:
                pb = float(crts[crt_id].get("guia_datos", {}).get("peso_bruto") or 0)
                tarifa = (crts[crt_id].get("config") or CONFIG_ACTIVO).get("tarifa_flete", 4400)
                fletes = calcular_fletes(pb, peso_total, tarifa)
                crts[crt_id]["fletes"] = fletes
                if crts[crt_id].get("form_data"):
                    fd = crts[crt_id]["form_data"]
                    fd["f_flete_origen"]   = f"{fletes.get('flete_origen_frontera', 0):.2f}"
                    fd["f_flete_frontera"] = f"{fletes.get('flete_frontera_destino', 0):.2f}"
                    fd["f_flete_usd"]      = f"{fletes.get('flete_prorrateado', 0):.2f}"
    except Exception as e:
        print(f"[orchestrator] Error recalculando fletes: {e}")
    return crts


# ── Builder de form_data ──────────────────────────────────────────────────────
def construir_form_data(crt: dict) -> dict:
    """Construye el dict f_* para el generador de PDF."""
    guia    = crt.get("guia_datos")    or {}
    factura = crt.get("factura_datos") or {}
    fletes  = crt.get("fletes")        or {}
    textos  = crt.get("textos")        or {}
    config  = crt.get("config") or CONFIG_ACTIVO

    def fmt(v):
        if v is None:
            return ""
        try:
            return (
                f"{float(str(v).replace(',', '.')):,.2f}"
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )
        except Exception:
            return str(v)

    productos = guia.get("productos") or []
    desc1 = kn1 = desc2 = kn2 = ""
    if len(productos) > 0:
        p     = productos[0]
        desc1 = (f"{p.get('cajas_totales', '')} CAJAS CON SALMON DEL ATLANTICO "
                 f"CRUDO Enfriado Refrigerado {p.get('familia', '')}")
        kn1   = fmt(p.get("kilos_totales"))
    if len(productos) > 1:
        p     = productos[1]
        desc2 = (f"{p.get('cajas_totales', '')} CAJAS CON SALMON DEL ATLANTICO "
                 f"CRUDO Enfriado Refrigerado {p.get('familia', '')}")
        kn2   = fmt(p.get("kilos_totales"))

    return {
        "f_remitente":            config.get("remitente", ""),
        "f_dir_remitente":        config.get("dir_remitente", ""),
        "f_transportista":        config.get("transportista", "TRANSPORTES VESPRINI S.A"),
        "f_lugar_emision":        config.get("lugar_emision", "PUERTO NATALES - CHILE"),
        "f_numero_crt":           textos.get("correlativo_casilla_2", ""),
        "f_destinatario":         factura.get("destinatario", ""),
        "f_dir_destinatario":     factura.get("direccion", ""),
        "f_consignatario":        factura.get("destinatario", ""),
        "f_dir_consignatario":    factura.get("direccion", ""),
        "f_notificar":            factura.get("destinatario", ""),
        "f_dir_notificar":        factura.get("direccion", ""),
        "f_lugar_recepcion":      config.get("lugar_emision", "") + ".",
        "f_fecha_documento":      guia.get("fecha", ""),
        "f_fecha_emision":        guia.get("fecha", ""),
        "f_lugar_entrega":        textos.get("texto_casilla_8", ""),
        "f_destino_final":        f"ARGENTINA - DESTINO FINAL {factura.get('pais_destino', 'USA')}",
        "f_descripcion_1":        desc1,
        "f_kilos_netos_1":        kn1,
        "f_descripcion_2":        desc2,
        "f_kilos_netos_2":        kn2,
        "f_peso_bruto":           fmt(guia.get("peso_bruto")),
        "f_peso_neto":            fmt(guia.get("peso_neto")),
        "f_total_cajas":          str(guia.get("bultos", "")),
        "f_valor_mercaderia":     factura.get("total", ""),
        "f_incoterm":             factura.get("incoterm", ""),
        "f_flete_origen":         fmt(fletes.get("flete_origen_frontera")),
        "f_flete_frontera":       fmt(fletes.get("flete_frontera_destino")),
        "f_flete_usd":            fmt(fletes.get("flete_prorrateado")),
        "f_num_factura":          str(factura.get("numero_factura", "")),
        "f_guias_despacho":       str(guia.get("numero_guia", "")),
        "f_cert_sanitario":       str(factura.get("cert_sanitario") or guia.get("cert_sanitario", "")),
        "f_instrucciones_aduana": textos.get("texto_casilla_18", ""),
        "f_conductor":            guia.get("conductor", ""),
        "f_patente_camion":       guia.get("patente_tracto", ""),
        "f_patente_rampla":       guia.get("patente_semi", ""),
    }


# ── Función principal ─────────────────────────────────────────────────────────
def procesar_documentos(
    store_actual: dict,
    archivos: list[tuple[str, bytes]],
) -> tuple[dict, list[str]]:
    """
    Punto de entrada único. Recibe documentos de cualquier fuente
    (frontend manual o Gmail automático) y actualiza el store.

    Parámetros:
        store_actual: {"crts": {...}, "next_numero": int}
        archivos:     [(nombre_archivo, pdf_bytes), ...]

    Retorna:
        (store_actualizado, lista_errores)
    """
    crts     = store_actual.get("crts", {})
    next_num = store_actual.get("next_numero", 5000)
    errores  = []

    for nombre, pdf_bytes in archivos:
        try:
            # 1. Clasificar por tipo de archivo y contenido
            tipo = clasificar_documento(pdf_bytes, nombre)
            if tipo is None:
                errores.append(
                    f"No se pudo clasificar '{nombre}' — no parece ser guía ni factura."
                )
                continue

            # 2. Extraer datos (PDF o Excel)
            datos = extraer_documento(pdf_bytes, tipo, nombre)
            if datos is None:
                errores.append(f"Error extrayendo datos de '{nombre}'.")
                continue

            # 3. Detectar pesquera y cargar config desde el texto del PDF
            texto_raw          = _extraer_texto_raw(pdf_bytes)
            clave_pesquera, config_pesquera = get_config_desde_texto(texto_raw)

            # 4. Matching y actualización del store
            if tipo == "guia":
                match_id = buscar_match_factura(datos, crts)
                if match_id:
                    crts[match_id]["guia_datos"]  = datos
                    crts[match_id]["guia_nombre"]  = nombre
                    crts[match_id]["nombre_guia"]  = nombre
                    crts[match_id]["estado"]        = ESTADO_COMPLETO
                    # Preferir la config detectada en la guía (tiene el remitente)
                    crts[match_id]["pesquera"]      = clave_pesquera
                    crts[match_id]["config"]        = config_pesquera
                    pais = crts[match_id]["factura_datos"].get("pais_destino", "USA")
                    tx   = generar_textos_crt(pais_destino=pais, numero_base=next_num)
                    crts[match_id]["textos"]        = tx
                    crts[match_id]["correlativo"]   = tx.get("correlativo_casilla_2")
                    crts[match_id]["form_data"]     = construir_form_data(crts[match_id])
                    # Advertencias de discrepancia logística
                    avisos = detectar_discrepancias(datos, crts[match_id]["factura_datos"])
                    errores.extend(f"DISCREPANCIA:{a}" for a in avisos)
                    next_num += 1
                else:
                    crt_id = str(uuid.uuid4())
                    crts[crt_id] = {
                        "id":             crt_id,
                        "estado":         ESTADO_FALTA_FACTURA,
                        "guia_datos":     datos,
                        "guia_nombre":    nombre,
                        "factura_datos":  None,
                        "fletes":         None,
                        "textos":         None,
                        "form_data":      None,
                        "correlativo":    None,
                        "destinatario":   datos.get("destinatario") or datos.get("cliente") or "—",
                        "pesquera":       clave_pesquera,
                        "config":         config_pesquera,
                        "nombre_guia":    nombre,
                        "nombre_factura": None,
                    }
                    crts[crt_id]["form_data"] = construir_form_data(crts[crt_id])

            elif tipo == "factura":
                match_id = buscar_match_guia(datos, crts)
                if match_id:
                    crts[match_id]["factura_datos"]   = datos
                    crts[match_id]["factura_nombre"]  = nombre
                    crts[match_id]["nombre_factura"]  = nombre
                    crts[match_id]["destinatario"]    = datos.get("destinatario", "—")
                    crts[match_id]["estado"]           = ESTADO_COMPLETO
                    # Mantener la config de la guía si ya se cargó; si no, usar la de la factura
                    if not crts[match_id].get("config"):
                        crts[match_id]["pesquera"] = clave_pesquera
                        crts[match_id]["config"]   = config_pesquera
                    pais = datos.get("pais_destino", "USA")
                    tx   = generar_textos_crt(pais_destino=pais, numero_base=next_num)
                    crts[match_id]["textos"]           = tx
                    crts[match_id]["correlativo"]      = tx.get("correlativo_casilla_2")
                    crts[match_id]["form_data"]        = construir_form_data(crts[match_id])
                    # Advertencias de discrepancia logística
                    avisos = detectar_discrepancias(crts[match_id]["guia_datos"], datos)
                    errores.extend(f"DISCREPANCIA:{a}" for a in avisos)
                    next_num += 1
                else:
                    crt_id = str(uuid.uuid4())
                    crts[crt_id] = {
                        "id":             crt_id,
                        "estado":         ESTADO_FALTA_GUIA,
                        "factura_datos":  datos,
                        "factura_nombre": nombre,
                        "guia_datos":     None,
                        "fletes":         None,
                        "textos":         None,
                        "form_data":      None,
                        "correlativo":    None,
                        "destinatario":   datos.get("destinatario", "—"),
                        "pesquera":       clave_pesquera,
                        "config":         config_pesquera,
                        "nombre_guia":    None,
                        "nombre_factura": nombre,
                    }
                    crts[crt_id]["form_data"] = construir_form_data(crts[crt_id])

        except Exception as e:
            errores.append(f"Error procesando '{nombre}': {e}")
            continue

    # 5. Recalcular fletes para todos los CRTs completos
    crts = recalcular_fletes(crts)

    return {"crts": crts, "next_numero": next_num}, errores
