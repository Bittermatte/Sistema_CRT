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
from modulos.config_cliente     import CONFIG_ACTIVO, get_config_desde_texto, get_config
from modulos.motor_agrupacion   import Documento, agrupar_documentos, consolidar_productos_australis

# ── Constantes ────────────────────────────────────────────────────────────────
MATCH_THRESHOLD      = 0.80
ESTADO_COMPLETO      = "COMPLETO"
ESTADO_FALTA_FACTURA = "FALTA_FACTURA"
ESTADO_FALTA_GUIA    = "FALTA_GUIA"

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

                # Tarifa especial para MARDI y AGRO COMERCIAL DEL CARMEN: 4.250 USD fijos
                dest = (crts[crt_id].get("factura_datos", {}) or {}).get("destinatario", "")
                dest_up = dest.upper() if dest else ""
                if "MARDI" in dest_up or "AGRO COMERCIAL DEL CARMEN" in dest_up:
                    tarifa = 4250
                else:
                    tarifa = (crts[crt_id].get("config") or CONFIG_ACTIVO).get("tarifa_flete", 4400)

                fletes = calcular_fletes(pb, peso_total, tarifa)
                crts[crt_id]["fletes"] = fletes
                if crts[crt_id].get("form_data"):
                    fd = crts[crt_id]["form_data"]
                    # Usar _fmt_es (formato español) para consistencia con construir_form_data
                    # Importante: excel_pdf_builder convierte esperando punto=miles, coma=decimal
                    fd["f_flete_origen"]   = _fmt_es(fletes.get("flete_origen_frontera", 0))
                    fd["f_flete_frontera"] = _fmt_es(fletes.get("flete_frontera_destino", 0))
                    fd["f_flete_usd"]      = _fmt_es(fletes.get("flete_prorrateado", 0))
    except Exception as e:
        print(f"[orchestrator] Error recalculando fletes: {e}")
    return crts


# ── Builder de form_data ──────────────────────────────────────────────────────

def _fmt_es(v) -> str:
    """Formatea número en formato español: 1.234,56 (punto miles, coma decimal).
    Retorna '' para None o 0 (no mostrar ceros en el PDF)."""
    if v is None:
        return ""
    try:
        f_val = float(str(v).replace(",", "."))
        if f_val == 0.0:
            return ""
        return (
            f"{f_val:,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except Exception:
        return str(v) if v else ""


def _construir_lineas_casilla11(pesquera: str, guia: dict, factura: dict) -> list[tuple[str, str]]:
    """
    Construye las líneas de producto para la casilla 11 del CRT.

    Retorna lista de tuplas (descripcion, kilos_netos_formateado).
    El numero de tuplas es variable (1 a 5).

    Reglas por pesquera:
      aquachile      — 1 línea por tipo de producto, "CON: X KG NETOS" en campo kilos
      blumar /
      blumar_magallanes — 1 línea consolidada, talla eliminada, sin kilos aparte
      australis      — productos de la factura en inglés, inline "CON: X KG NETOS"
      cermaq         — 1 línea consolidada de todo
      multix         — 1 línea por categoría, "CON: X NETOS" / "CON: X KG NETOS"
    """
    productos_guia    = guia.get("productos") or []
    productos_factura = factura.get("productos") or []

    # ── AUSTRALIS: productos vienen de la factura en inglés ───────────────────
    if pesquera == "australis":
        lineas = []
        for p in productos_factura[:5]:
            desc  = p.get("descripcion") or p.get("familia") or ""
            cajas = p.get("cajas_totales", 0)
            kg    = p.get("kilos_totales", 0.0)
            if desc and cajas:
                lineas.append((
                    f"{cajas} CAJAS CON {desc}, CON: {_fmt_es(kg)} KG NETOS",
                    "",  # kilos inline en la descripción
                ))
        return lineas or [("", "")]

    # ── BLUMAR / BLUMAR MAGALLANES: 1 línea consolidada, sin talla ────────────
    if pesquera in ("blumar", "blumar_magallanes"):
        if not productos_guia:
            return [("", "")]
        total_cajas = sum(p.get("cajas_totales", 0) for p in productos_guia)
        # Extraer tipo de corte de la primera línea (FILETE, ENTERO, etc.)
        primera_desc = (productos_guia[0].get("descripcion") or "").upper()
        # Limpiar: conservar solo "SALMON ATLANTICO [TIPO] ENFRIADO REFRIGERADO"
        corte_m = re.search(
            r'(?:SALMON\s+ATLANTICO\s+)?(\w[\w\s/]*?)\s+ENFRIADO\s+REFRIGERADO',
            primera_desc, re.IGNORECASE
        )
        corte = corte_m.group(1).strip() if corte_m else "FILETE"
        # Quitar palabras de especie que pudieran haber quedado
        corte = re.sub(r'\b(?:SALMON|ATLANTICO|CRUDO)\b', '', corte, flags=re.IGNORECASE)
        corte = re.sub(r'\s+', ' ', corte).strip()
        desc = f"{total_cajas} CAJAS CON SALMON ATLANTICO {corte} ENFRIADO REFRIGERADO."
        return [(desc, "")]

    # ── CERMAQ: 1 línea consolidada ───────────────────────────────────────────
    if pesquera == "cermaq":
        if not productos_guia:
            return [("", "")]
        total_cajas = sum(p.get("cajas_totales", 0) for p in productos_guia)
        # La descripción ya viene limpiada por _limpiar_desc_cermaq en extractor_guias
        # Usar la primera (normalmente todas son lo mismo consolidado)
        primera_desc = (productos_guia[0].get("descripcion") or "").upper().strip()
        # Si no tiene "SALMON DEL ATLANTICO" como prefijo, añadirlo
        if not primera_desc.startswith("SALMON DEL ATLANTICO"):
            primera_desc = "SALMON DEL ATLANTICO " + primera_desc
        desc = f"{total_cajas} CAJAS CON {primera_desc}"
        return [(desc, "")]

    # ── MULTI X: 1 línea por categoría, kilos inline ─────────────────────────
    if pesquera == "multix":
        if not productos_guia:
            return [("", "")]
        lineas = []
        for p in productos_guia[:5]:
            desc_raw = (p.get("familia") or p.get("descripcion") or "").upper()
            cajas    = p.get("cajas_totales", 0)
            kg       = p.get("kilos_totales", 0.0)
            if not desc_raw or not cajas:
                continue
            # Quitar prefijo redundante si extractor lo dejó completo
            desc_raw = re.sub(
                r'^(?:SALMON\s+DEL\s+ATLANTICO\s+CRUDO\s+)?(?:Enfriado\s+Refrigerado\s+)?',
                '', desc_raw, flags=re.IGNORECASE
            ).strip()
            # Determinar sufijo de kilos: primera línea "NETOS", resto "KG NETOS" / "KILOS NETOS"
            sufijo_kg = "NETOS" if not lineas else "KG NETOS"
            lineas.append((
                f"{cajas} CAJAS CON SALMON ATLANTICO {desc_raw}, CON: {_fmt_es(kg)} {sufijo_kg}",
                "",
            ))
        return lineas or [("", "")]

    # ── AQUACHILE (default): 1 línea por producto, kilos en campo separado ────
    if not productos_guia:
        return [("", "")]
    lineas = []
    for p in productos_guia[:5]:
        familia = (p.get("familia") or p.get("descripcion") or "").strip()
        cajas   = p.get("cajas_totales", 0)
        kg      = p.get("kilos_totales", 0.0)
        if not familia or not cajas:
            continue
        lineas.append((
            f"{cajas} CAJAS CON SALMON DEL ATLANTICO CRUDO {familia}",
            f"CON: {_fmt_es(kg)} KG NETOS",
        ))
    return lineas or [("", "")]


def construir_form_data(crt: dict) -> dict:
    """
    Construye el dict f_* para el generador de PDF.

    Casilla 11: lógica por pesquera (ver _construir_lineas_casilla11)
    Casilla 9 (notificar): según config["notificar"] → destinatario o Alpha Brokers
    """
    from modulos.config_cliente import ALPHA_BROKERS

    guia    = crt.get("guia_datos")    or {}
    factura = crt.get("factura_datos") or {}
    fletes  = crt.get("fletes")        or {}
    textos  = crt.get("textos")        or {}
    config  = crt.get("config") or CONFIG_ACTIVO
    pesquera = crt.get("pesquera") or config.get("clave", "aquachile")

    # ── Casilla 9: notificar ──────────────────────────────────────────────────
    notificar_regla = config.get("notificar", "destinatario")
    if notificar_regla == "alpha_brokers":
        f_notificar     = ALPHA_BROKERS["nombre"]
        f_dir_notificar = f"{ALPHA_BROKERS['direccion']}\n{ALPHA_BROKERS['telefono']}"
    else:
        f_notificar     = factura.get("destinatario", "")
        f_dir_notificar = factura.get("direccion", "")

    # ── Casilla 11: descripción de mercadería ─────────────────────────────────
    lineas = _construir_lineas_casilla11(pesquera, guia, factura)

    # Poblar f_descripcion_1..5 y f_kilos_netos_1..5
    desc_fields = {}
    for i in range(1, 6):
        idx = i - 1
        if idx < len(lineas):
            desc_fields[f"f_descripcion_{i}"] = lineas[idx][0]
            desc_fields[f"f_kilos_netos_{i}"] = lineas[idx][1]
        else:
            desc_fields[f"f_descripcion_{i}"] = ""
            desc_fields[f"f_kilos_netos_{i}"] = ""

    return {
        "f_remitente":            config.get("remitente", ""),
        "f_dir_remitente":        config.get("dir_remitente", ""),
        "f_transportista":        config.get("transportista", "TRANSPORTES VESPRINI S.A"),
        "f_dir_transportista":    config.get("dir_transportista", "Avda Colon 1761 Bahia Blanca BS - AS\nARGENTINA"),
        "f_firma_remitente":      config.get("firma_remitente", ""),
        "f_lugar_emision":        config.get("lugar_emision", "PUERTO NATALES - CHILE"),
        "f_numero_crt":           textos.get("correlativo_casilla_2", ""),
        "f_destinatario":         factura.get("destinatario", ""),
        "f_dir_destinatario":     factura.get("direccion", ""),
        "f_consignatario":        factura.get("destinatario", ""),
        "f_dir_consignatario":    factura.get("direccion", ""),
        "f_notificar":            f_notificar,
        "f_dir_notificar":        f_dir_notificar,
        "f_lugar_recepcion":      config.get("lugar_emision", "") + ".",
        "f_fecha_documento":      factura.get("fecha") or guia.get("fecha", ""),
        "f_fecha_emision":        factura.get("fecha") or guia.get("fecha", ""),
        "f_lugar_entrega":        textos.get("texto_casilla_8", ""),
        "f_destino_final":        f"ARGENTINA - DESTINO FINAL {factura.get('pais_destino', 'USA')}",
        **desc_fields,
        "f_peso_bruto":           _fmt_es(guia.get("peso_bruto")),
        "f_peso_neto":            _fmt_es(guia.get("peso_neto")),
        "f_total_cajas":          str(guia.get("bultos") or ""),
        "f_valor_mercaderia":     factura.get("total", ""),
        "f_incoterm":             factura.get("incoterm", ""),
        "f_flete_origen":         _fmt_es(fletes.get("flete_origen_frontera")),
        "f_flete_frontera":       _fmt_es(fletes.get("flete_frontera_destino")),
        "f_flete_usd":            _fmt_es(fletes.get("flete_prorrateado")),
        "f_num_factura":          str(factura.get("numero_factura", "")),
        "f_guias_despacho":       str(guia.get("numero_guia", "")),
        "f_cert_sanitario":       str(factura.get("cert_sanitario") or guia.get("cert_sanitario", "")),
        "f_instrucciones_aduana": textos.get("texto_casilla_18", ""),
        "f_conductor":            guia.get("conductor", ""),
        "f_patente_camion":       guia.get("patente_tracto", ""),
        "f_patente_rampla":       guia.get("patente_semi", ""),
    }


# ── Helpers de merge para grupos con múltiples documentos ────────────────────

def _merge_guias(guias) -> dict:
    """Fusiona datos de múltiples Documento(tipo=guia) en un único dict."""
    if not guias:
        return {}
    if len(guias) == 1:
        return dict(guias[0].datos)

    base = dict(guias[0].datos)

    # Concatenar números de guía
    nums = [g.datos.get("numero_guia") or "" for g in guias]
    base["numero_guia"] = ", ".join(n for n in nums if n) or None

    # Sumar pesos y bultos
    for campo in ("peso_bruto", "peso_neto"):
        total = sum(float(g.datos.get(campo) or 0) for g in guias)
        base[campo] = total if total > 0 else None
    bultos = sum(int(g.datos.get("bultos") or 0) for g in guias)
    base["bultos"] = bultos if bultos > 0 else None

    # Productos concatenados
    prods = []
    for g in guias:
        prods.extend(g.datos.get("productos") or [])
    base["productos"] = prods

    return base


def _merge_facturas(facturas) -> dict:
    """Fusiona datos de múltiples Documento(tipo=factura) en un único dict."""
    if not facturas:
        return {}
    if len(facturas) == 1:
        return dict(facturas[0].datos)

    base = dict(facturas[0].datos)

    # Concatenar números de factura
    nums = [str(f.datos.get("numero_factura") or "") for f in facturas]
    base["numero_factura"] = ", ".join(n for n in nums if n) or None

    # Sumar totales monetarios si son numéricos
    try:
        total = sum(
            float(str(f.datos.get("total") or 0).replace(",", ""))
            for f in facturas
        )
        base["total"] = f"{total:.2f}" if total > 0 else base.get("total")
    except (TypeError, ValueError):
        pass

    # Concatenar productos (necesario para Australis multi-factura)
    prods = []
    for f in facturas:
        prods.extend(f.datos.get("productos") or [])
    base["productos"] = prods

    return base


# ── Función principal ─────────────────────────────────────────────────────────
def procesar_documentos(
    store_actual: dict,
    archivos: list[tuple[str, bytes]],
) -> tuple[dict, list[str]]:
    """
    Punto de entrada único. Recibe documentos de cualquier fuente
    (frontend manual o Gmail automático) y actualiza el store.

    Flujo:
      FASE 1 — Clasificar y extraer todos los documentos del lote → list[Documento]
      FASE 2 — agrupar_documentos() → list[GrupoCRT]  (motor_agrupacion)
      FASE 3 — Convertir cada GrupoCRT a una entrada del store;
               para grupos incompletos se intenta matching con el store existente.

    Parámetros:
        store_actual: {"crts": {...}, "next_numero": int}
        archivos:     [(nombre_archivo, file_bytes), ...]

    Retorna:
        (store_actualizado, lista_errores)
    """
    crts     = store_actual.get("crts", {})
    next_num = store_actual.get("next_numero", 5000)
    errores  = []

    # ── FASE 1: Clasificar y extraer ─────────────────────────────────────────
    nuevos_docs: list = []       # list[Documento]
    nombres_doc: dict = {}       # id(Documento) → nombre_archivo

    for nombre, file_bytes in archivos:
        try:
            tipo = clasificar_documento(file_bytes, nombre)
            if tipo is None:
                errores.append(
                    f"No se pudo clasificar '{nombre}' — no parece ser guía ni factura."
                )
                continue

            datos = extraer_documento(file_bytes, tipo, nombre)
            if datos is None:
                errores.append(f"Error extrayendo datos de '{nombre}'.")
                continue

            # Enriquecer pesquera desde texto bruto si extractor no la detectó
            texto_raw = _extraer_texto_raw(file_bytes)
            clave_raw, _ = get_config_desde_texto(texto_raw)
            if not datos.get("pesquera") or datos["pesquera"] == "DESCONOCIDA":
                datos["pesquera"] = clave_raw

            doc = Documento(
                tipo=tipo,
                pesquera=datos.get("pesquera") or clave_raw or "DESCONOCIDA",
                numero=str(datos.get("numero_guia") or datos.get("numero_factura") or ""),
                destinatario=(datos.get("destinatario") or ""),
                ciudad_destino=(datos.get("ciudad_destino") or ""),
                datos=datos,
                pdf_bytes=file_bytes,
            )
            nuevos_docs.append(doc)
            nombres_doc[id(doc)] = nombre

        except Exception as e:
            errores.append(f"Error procesando '{nombre}': {e}")

    if not nuevos_docs:
        return {"crts": crts, "next_numero": next_num}, errores

    # ── FASE 2: Agrupar con motor_agrupacion ─────────────────────────────────
    grupos = agrupar_documentos(nuevos_docs)
    # Consolidar productos idénticos de Australis antes de convertir a store
    grupos = consolidar_productos_australis(grupos)

    # ── FASE 3: Convertir grupos a entradas del store ────────────────────────
    for grupo in grupos:
        try:
            guia_datos    = _merge_guias(grupo.guias)      if grupo.guias    else None
            factura_datos = _merge_facturas(grupo.facturas) if grupo.facturas else None

            nombre_guia    = nombres_doc.get(id(grupo.guias[0]))    if grupo.guias    else None
            nombre_factura = nombres_doc.get(id(grupo.facturas[0])) if grupo.facturas else None

            clave_pesquera  = grupo.pesquera
            config_pesquera = get_config(clave_pesquera) or CONFIG_ACTIVO

            if grupo.completo:
                # ── Grupo con guías Y facturas → CRT completo directo ────────
                crt_id = str(uuid.uuid4())
                pais = factura_datos.get("pais_destino", "USA")
                tx   = generar_textos_crt(
                    pais_destino=pais,
                    numero_base=next_num,
                    paso_frontera=config_pesquera.get("paso_frontera", "MONTE AYMOND"),
                    aeropuerto=config_pesquera.get("aeropuerto", "MINISTRO PISTARINI"),
                )
                crts[crt_id] = {
                    "id":             crt_id,
                    "estado":         ESTADO_COMPLETO,
                    "guia_datos":     guia_datos,
                    "factura_datos":  factura_datos,
                    "fletes":         None,
                    "textos":         tx,
                    "form_data":      None,
                    "correlativo":    tx.get("correlativo_casilla_2"),
                    "destinatario":   (factura_datos.get("destinatario")
                                       or guia_datos.get("destinatario") or "—"),
                    "pesquera":       clave_pesquera,
                    "config":         config_pesquera,
                    "nombre_guia":    nombre_guia,
                    "nombre_factura": nombre_factura,
                }
                crts[crt_id]["form_data"] = construir_form_data(crts[crt_id])
                avisos = detectar_discrepancias(guia_datos, factura_datos)
                errores.extend(f"DISCREPANCIA:{a}" for a in avisos)
                next_num += 1

            elif grupo.guias and not grupo.facturas:
                # ── Solo guías — buscar factura huérfana en el store ─────────
                match_id = buscar_match_factura(guia_datos, crts)
                if match_id:
                    crts[match_id]["guia_datos"]    = guia_datos
                    crts[match_id]["nombre_guia"]   = nombre_guia
                    crts[match_id]["estado"]         = ESTADO_COMPLETO
                    crts[match_id]["pesquera"]       = clave_pesquera
                    crts[match_id]["config"]         = config_pesquera
                    pais = crts[match_id]["factura_datos"].get("pais_destino", "USA")
                    tx   = generar_textos_crt(
                        pais_destino=pais,
                        numero_base=next_num,
                        paso_frontera=config_pesquera.get("paso_frontera", "MONTE AYMOND"),
                        aeropuerto=config_pesquera.get("aeropuerto", "MINISTRO PISTARINI"),
                    )
                    crts[match_id]["textos"]         = tx
                    crts[match_id]["correlativo"]    = tx.get("correlativo_casilla_2")
                    crts[match_id]["form_data"]      = construir_form_data(crts[match_id])
                    avisos = detectar_discrepancias(guia_datos, crts[match_id]["factura_datos"])
                    errores.extend(f"DISCREPANCIA:{a}" for a in avisos)
                    next_num += 1
                else:
                    crt_id = str(uuid.uuid4())
                    crts[crt_id] = {
                        "id":             crt_id,
                        "estado":         ESTADO_FALTA_FACTURA,
                        "guia_datos":     guia_datos,
                        "factura_datos":  None,
                        "fletes":         None,
                        "textos":         None,
                        "form_data":      None,
                        "correlativo":    None,
                        "destinatario":   guia_datos.get("destinatario") or "—",
                        "pesquera":       clave_pesquera,
                        "config":         config_pesquera,
                        "nombre_guia":    nombre_guia,
                        "nombre_factura": None,
                    }
                    crts[crt_id]["form_data"] = construir_form_data(crts[crt_id])

            elif grupo.facturas and not grupo.guias:
                # ── Solo facturas — buscar guía huérfana en el store ─────────
                match_id = buscar_match_guia(factura_datos, crts)
                if match_id:
                    crts[match_id]["factura_datos"]   = factura_datos
                    crts[match_id]["nombre_factura"]  = nombre_factura
                    crts[match_id]["destinatario"]    = factura_datos.get("destinatario", "—")
                    crts[match_id]["estado"]           = ESTADO_COMPLETO
                    if not crts[match_id].get("config"):
                        crts[match_id]["pesquera"] = clave_pesquera
                        crts[match_id]["config"]   = config_pesquera
                    pais = factura_datos.get("pais_destino", "USA")
                    tx   = generar_textos_crt(
                        pais_destino=pais,
                        numero_base=next_num,
                        paso_frontera=config_pesquera.get("paso_frontera", "MONTE AYMOND"),
                        aeropuerto=config_pesquera.get("aeropuerto", "MINISTRO PISTARINI"),
                    )
                    crts[match_id]["textos"]           = tx
                    crts[match_id]["correlativo"]      = tx.get("correlativo_casilla_2")
                    crts[match_id]["form_data"]        = construir_form_data(crts[match_id])
                    avisos = detectar_discrepancias(crts[match_id]["guia_datos"], factura_datos)
                    errores.extend(f"DISCREPANCIA:{a}" for a in avisos)
                    next_num += 1
                else:
                    crt_id = str(uuid.uuid4())
                    crts[crt_id] = {
                        "id":             crt_id,
                        "estado":         ESTADO_FALTA_GUIA,
                        "factura_datos":  factura_datos,
                        "guia_datos":     None,
                        "fletes":         None,
                        "textos":         None,
                        "form_data":      None,
                        "correlativo":    None,
                        "destinatario":   factura_datos.get("destinatario", "—"),
                        "pesquera":       clave_pesquera,
                        "config":         config_pesquera,
                        "nombre_guia":    None,
                        "nombre_factura": nombre_factura,
                    }
                    crts[crt_id]["form_data"] = construir_form_data(crts[crt_id])

        except Exception as e:
            errores.append(f"Error procesando grupo ({grupo.pesquera}): {e}")

    # ── Recalcular fletes para todos los CRTs completos ──────────────────────
    crts = recalcular_fletes(crts)

    return {"crts": crts, "next_numero": next_num}, errores
