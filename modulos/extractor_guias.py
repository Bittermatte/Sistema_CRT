import re
import pdfplumber
from typing import Optional

# ── Patrones reales extraídos de 3.198 CRTs históricos ───────────────────────

# Número de guía — 5 variantes reales encontradas
PATRONES_GUIA = [
    r"GUIAS?\s+DE\s+DESPACHO\s+NROS?\s*[.:]\s*([\d,\s\.]+)",
    r"GUIAS?\s+DE\s+DESPACHO\s*[.:]\s*([\d,\s\.]+)",
    r"GUIA\s+DE\s+DESPACHO\s+NRO?\s*[.:]\s*([\d,\s\.]+)",
    r"GUIA\s+DE\s+DESPACHO\s*[.:]\s*([\d]+)",
    r"N[°º]\s+DE\s+GUIA\s*[.:]\s*([\d]+)",
    # Formato SII: "Nº 497318\nS.I.I."
    r"N[°º]\s+(\d+)\s*\n\s*S\.I\.I\.",
]

# Peso bruto — variantes reales
PATRONES_PESO_BRUTO = [
    r"PESO\s+BRUTO\s*:\s*([\d.,]+)\s+Son:",   # formato SII estándar
    r"PESO\s+BRUTO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"BRUTO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"GROSS\s+WEIGHT\s*[.:]\s*([\d.,]+)",
    r"P\.?\s*BRUTO\s*[.:]\s*([\d.,]+)",
]

# Peso neto
PATRONES_PESO_NETO = [
    r"PESO\s+NETO\s*:\s*([\d.,]+)\s+Son:",    # formato SII estándar
    r"PESO\s+NETO\s*[.:]\s*([\d.,]+)\s*(?:KG|KILOS?)?",
    r"NET\s+WEIGHT\s*[.:]\s*([\d.,]+)",
    r"P\.?\s*NETO\s*[.:]\s*([\d.,]+)",
]

# Bultos/cajas
PATRONES_BULTOS = [
    r"CANTIDAD\s+DE\s+BULTOS\s*:\s*([\d.,]+)\s+Son:",  # formato SII estándar
    r"BULTOS\s*[.:]\s*(\d+)",
    r"TOTAL\s+CAJAS\s*[.:]\s*(\d+)",
    r"N[°º]\s+BULTOS\s*[.:]\s*(\d+)",
    r"CANTIDAD\s+BULTOS\s*[.:]\s*(\d+)",
    r"(\d+)\s+CAJAS",
]

# Patente — formato chileno nuevo (AB123CD), viejo (AB1234) y argentino (AB123CD)
PATRON_PATENTE_TRACTO = [
    r"CAM[IÍ][OÓ]N\s+PATENTE(.*?)HORA\s+LLEGADA",  # bloque SII con dos placas
    r"PATENTE\s+(?:CAMION|TRACTO|TRACTOR)\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"TRACTO\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"CAMION\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
]

PATRON_PATENTE_SEMI = [
    r"PATENTE\s+(?:RAMPLA|SEMI|REMOLQUE)\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"RAMPLA\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
    r"SEMI\s*[.:/]\s*([A-Z]{2,3}\d{3,4}[A-Z]{0,2})",
]

# Conductor
PATRONES_CONDUCTOR = [
    r"CONDUCTOR\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|RUT|DNI|$)",
    r"CHOFER\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|RUT|$)",
    r"TRANSPORTISTA\s*[.:/]\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\n|PATENTE|$)",
]

# Certificado sanitario / Codaut / RUCE / NEPPEX
PATRONES_CERT = [
    r"CERTIFICADO\s+SANITARIO\s*(?:NRO?|N[°º])\s*[.:/]?\s*(\d+)",
    r"CERT(?:IFICADO)?\s+SANITARIO\s*[.:/]\s*(\d+)",
    r"N[°º]\s+CODAUT\s*[.:/]\s*(\d+)",
    r"CODAUT\s*[.:/]\s*(\d+)",
    r"N[°º]\s+RUCE\s*[.:/]\s*(\d+)",
    r"RUCE\s*/\s*NEPPEX\s*[.:/]\s*(\d+)",
    r"NEPPEX\s*[.:/]\s*(\d+)",
]

# Destinatario
PATRONES_DESTINATARIO = [
    r"DESTINATARIO\s*[.:/]\s*(.+?)(?:\n|DIRECCION|DIR\.|RUT)",
    r"CONSIGNATARIO\s*[.:/]\s*(.+?)(?:\n|DIRECCION)",
    r"CLIENTE\s*[.:/]\s*(.+?)(?:\n|RUT|DIRECCION)",
]

# Orden de venta / referencia cruzada con la factura — por pesquera
# El número extraído aquí debe coincidir con ref_pedido en la factura
PATRONES_ORDEN_VENTA_PESQUERA = {
    # Multi X: guía dice "N° Pedido: 12345" — factura dice "PV: 12345"
    "multix":           [r"N[°º]\s*PEDIDO\s*[.:]\s*(\d+)"],
    # AquaChile: guía dice "PEDIDO EXPORTACION 12345"
    "aquachile":        [r"PEDIDO\s+EXPORTACION\s*[.:/]?\s*(\d+)"],
    # Blumar: guía dice "PO: 12345"
    "blumar":           [r"PO\s*[.:]\s*(\d+)"],
    "blumar_magallanes":[r"PO\s*[.:]\s*(\d+)"],
    # Cermaq: guía dice "CO - CLIENTE: 12345 TEXTO" — solo el número
    "cermaq":           [r"CO\s*[-\u2013]\s*CLIENTE\s*[.:]\s*(\d+)"],
    # Australis: fallback genérico (sin patrón específico conocido aún)
    "australis":        [r"ORDEN\s+(?:DE\s+)?VENTA\s*[.:/]\s*(\d+)",
                         r"PURCHASE\s+ORDER\s*[.:/]?\s*(?:N[°º])?\s*(\d+)"],
}

# Fallback genérico cuando la pesquera no tiene patrón específico
PATRONES_ORDEN_VENTA_GENERICO = [
    r"ORDEN\s+DE\s+VENTA\s*[.:/]\s*(\d+)",
    r"N[°º]\s*\.?\s*ORDEN\s+(?:DE\s+)?VENTA\s*[.:/]\s*(\d+)",
    r"PURCHASE\s+ORDER\s*[.:/]?\s*(?:N[°º])?\s*(\d+)",
    r"P\.?O\.?\s*[.:]\s*(\d+)",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _limpiar_numeros(texto: str) -> str:
    """Extrae y limpia lista de números: '545178, 545179' → '545178, 545179'"""
    if not texto:
        return ""
    nums = re.findall(r'\d+', texto)
    return ", ".join(nums) if nums else ""


def _primera_coincidencia(texto: str, patrones: list) -> Optional[str]:
    """Prueba lista de patrones y retorna la primera coincidencia limpia."""
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _extraer_float(texto: str) -> Optional[float]:
    """Convierte '1.234,56' o '1234.56' a float."""
    if not texto:
        return None
    # Formato chileno: punto miles, coma decimal
    t = texto.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        pass
    # Formato anglosajón
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def _extraer_patentes_sii(texto: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extrae tracto y semi del bloque SII 'CAMIÓN PATENTE … HORA LLEGADA'.
    Reconoce formato chileno (AB123CD) y argentino (AB1234 / AB123CD).
    """
    m = re.search(
        r"CAM[IÍ][OÓ]N\s+PATENTE(.*?)HORA\s+LLEGADA",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        placas = re.findall(r"\b([A-Z]{2,3}\d{3,4}[A-Z]{0,2})\b", m.group(1))
        tracto = placas[0] if len(placas) > 0 else None
        semi   = placas[1] if len(placas) > 1 else None
        return tracto, semi
    return None, None


# ── Parser de tabla de productos ─────────────────────────────────────────────
#
# Las guías SII tienen siempre la misma estructura de tabla:
#   CODIGO | PRODUCTOS | ... | KILOS | CAJAS | P. UNITARIO | TOTAL
#
# pdfplumber puede extraer la tabla como lista de filas.
# Cuando hay múltiples productos pdfplumber los colapsa en una sola fila
# con \n dentro de cada celda (así aparece en los documentos reales de AquaChile).
#
# La descripción sigue el patrón:
#   "SALMON DEL ATLANTICO CRUDO Enfriado Refrigerado <CORTE> <TALLA>"
#   "SALMO SALAR"   ← segunda línea (especie, se descarta)
#
# Columnas confirmadas en PDFs reales:
#   col[0]=CODIGO  col[1]=PRODUCTOS  col[5]=KILOS  col[6]=CAJAS  col[7]=P.UNIT  col[8]=TOTAL


def _extraer_float_guia(texto: str) -> Optional[float]:
    """Convierte '1.827,48' o '1827.48' a float."""
    if not texto:
        return None
    t = str(texto).strip().replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        try:
            return float(str(texto).replace(",", ""))
        except ValueError:
            return None


def _limpiar_desc_cermaq(desc: str) -> str:
    """
    Limpia la descripción de productos Cermaq para el CRT.

    Input:  "Enfriado Refrigerado Salmon del Atlantico [Salmo Salar]
             Eviscerado Entero c/agallas 58 Lbs Poliestireno"
    Output: "SALMON DEL ATLANTICO ENFRIADO REFRIGERADO EVISCERADO ENTERO C/AGALLAS"
    """
    d = desc.upper()
    # Eliminar especie entre corchetes
    d = re.sub(r'\[.*?\]', '', d)
    # Eliminar peso nominal (ej: "58 LBS", "12 KG")
    d = re.sub(r'\b\d+\s*(?:LBS?|KGS?)\b', '', d, flags=re.IGNORECASE)
    # Eliminar "POLIESTIRENO"
    d = re.sub(r'\bPOLIESTIRENO\b', '', d, flags=re.IGNORECASE)
    # Eliminar "SALMO SALAR" / "ONCORHYNCHUS MYKISS" si quedaron fuera de corchetes
    d = re.sub(r'\b(?:SALMO\s+SALAR|ONCORHYNCHUS\s+MYKISS)\b', '', d, flags=re.IGNORECASE)
    # Reordenar: sacar "ENFRIADO REFRIGERADO" al inicio si viene antes del nombre del salmón
    # Patrón: "ENFRIADO REFRIGERADO SALMON DEL ATLANTICO X Y" → "SALMON DEL ATLANTICO ENFRIADO REFRIGERADO X Y"
    m = re.match(
        r'^(ENFRIADO\s+REFRIGERADO)\s+(SALMON\s+DEL\s+ATLANTICO)\s+(.*)',
        d.strip(), re.IGNORECASE
    )
    if m:
        d = f"{m.group(2)} {m.group(1)} {m.group(3)}"
    # Normalizar espacios
    d = re.sub(r'\s+', ' ', d).strip()
    return d


def _parsear_tabla_blumar(pdf_path: str) -> list[dict]:
    """
    Parser para guías Blumar: columnas CANTIDAD | DETALLE.
    CANTIDAD = número de cajas.
    DETALLE = descripción del producto (puede incluir "(N CJS)" embebido).
    Los kilos netos se extraen del texto si aparece "KILOS NETOS" en el pie.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header = [str(c or "").upper().strip() for c in table[0]]
                    # Tabla Blumar tiene "CANTIDAD" y "DETALLE"
                    if "CANTIDAD" not in header or "DETALLE" not in header:
                        continue

                    idx_cant   = next(i for i, h in enumerate(header) if h == "CANTIDAD")
                    idx_det    = next(i for i, h in enumerate(header) if "DETALLE" in h)
                    idx_kilos  = next(
                        (i for i, h in enumerate(header) if "KILO" in h or "KG" in h),
                        None
                    )
                    idx_total  = next(
                        (i for i, h in enumerate(header) if "TOTAL" in h and i != idx_cant),
                        None
                    )

                    productos = []
                    for row in table[1:]:
                        if not row:
                            continue
                        det_raw  = str(row[idx_det] or "").strip()
                        cant_raw = str(row[idx_cant] or "").strip()

                        if not det_raw or not any(c.isalpha() for c in det_raw):
                            continue
                        if "TOTAL" in det_raw.upper() or "CONSTITUYE" in det_raw.upper():
                            continue
                        if not any(c.isdigit() for c in cant_raw):
                            continue

                        # Extraer cajas — puede estar en cant_raw o embebido "(N CJS)"
                        cjs_m = re.search(r'\((\d+)\s*CJS?\)', det_raw, re.IGNORECASE)
                        if cjs_m:
                            cajas = int(cjs_m.group(1))
                        else:
                            try:
                                cajas = int(float(cant_raw.replace(",", "").replace(".", "")))
                            except ValueError:
                                cajas = 0

                        # Kilos netos: desde columna si existe
                        kilos = None
                        if idx_kilos is not None and idx_kilos < len(row):
                            kilos = _extraer_float_guia(str(row[idx_kilos] or ""))
                        if kilos is None and idx_total is not None and idx_total < len(row):
                            kilos = _extraer_float_guia(str(row[idx_total] or ""))

                        # Limpiar descripción: quitar "(N CJS)", tallas (ej: "3-4 KG")
                        desc = re.sub(r'\(\d+\s*CJS?\)', '', det_raw, flags=re.IGNORECASE)
                        desc = re.sub(r'\b\d+[-–]\d+\s*(?:KG|LB|G)\b', '', desc, flags=re.IGNORECASE)
                        desc = re.sub(r'\s+', ' ', desc).strip().upper()

                        familia_m = re.search(
                            r'(?:Refrigerado|REFRIGERADO|CRUDO|ATLANTICO)\s+(.+)',
                            desc, re.IGNORECASE
                        )
                        familia = familia_m.group(1).strip() if familia_m else desc

                        if desc and cajas:
                            productos.append({
                                "descripcion":   desc,
                                "familia":       familia,
                                "kilos_totales": kilos or 0.0,
                                "cajas_totales": cajas,
                            })

                    if productos:
                        return productos

    except Exception as e:
        print(f"[extractor_guias] parser Blumar error: {e}")

    return []


def _parsear_tabla_productos(pdf_path: str, pesquera: str = "") -> list[dict]:
    """
    Extrae la tabla de productos de una guía SII usando pdfplumber.extract_table().

    Retorna lista de dicts con:
        descripcion    — texto completo del producto (ej: "ENTERO SIN VISCERAS/HON Premium 6-8KG")
        familia        — corte + talla concatenados
        cajas_totales  — int
        kilos_totales  — float (kilos netos de esa línea)

    Pesquera-specific:
        - blumar / blumar_magallanes → _parsear_tabla_blumar (CANTIDAD|DETALLE)
        - cermaq → parser estándar + _limpiar_desc_cermaq en cada descripción
        - australis → retorna [] (productos vienen de la factura)
        - aquachile / multix → parser estándar SII (CODIGO|PRODUCTOS|KILOS|CAJAS)

    Si extract_table() falla o no encuentra cabecera esperada,
    intenta el fallback por regex sobre el texto crudo.
    """
    # Australis: productos en la factura, no en la guía
    if pesquera == "australis":
        return []

    # Blumar: formato CANTIDAD|DETALLE
    if pesquera in ("blumar", "blumar_magallanes"):
        result = _parsear_tabla_blumar(pdf_path)
        if result:
            return result
        # Si falla, continúa con el parser genérico por si la guía tiene otro formato

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Verificar que la cabecera corresponde a una tabla de productos SII
                    header = [str(c or "").upper().strip() for c in table[0]]
                    if "PRODUCTOS" not in header and "KILOS" not in header:
                        continue

                    # Encontrar índices de columnas relevantes
                    try:
                        idx_prod  = next(i for i, h in enumerate(header) if "PRODUCTO" in h)
                        idx_kilos = next(i for i, h in enumerate(header) if "KILO" in h)
                        idx_cajas = next(i for i, h in enumerate(header) if "CAJA" in h)
                    except StopIteration:
                        continue

                    productos = []
                    for row in table[1:]:
                        if not row or len(row) <= max(idx_prod, idx_kilos, idx_cajas):
                            continue

                        prod_raw  = str(row[idx_prod] or "").strip()
                        kilos_raw = str(row[idx_kilos] or "").strip()
                        cajas_raw = str(row[idx_cajas] or "").strip()

                        # Saltar filas de totales o notas (sin contenido de producto)
                        if not prod_raw or not any(c.isdigit() for c in kilos_raw):
                            continue
                        # Saltar la fila de "No constituye Venta..."
                        if "CONSTITUYE" in prod_raw.upper() or "TOTAL" in prod_raw.upper()[:20]:
                            continue

                        # Separar líneas dentro de la celda (múltiples productos colapsados)
                        lineas_prod  = [l.strip() for l in prod_raw.split("\n") if l.strip()]
                        lineas_kilos = [l.strip() for l in kilos_raw.split("\n") if l.strip()]
                        lineas_cajas = [l.strip() for l in cajas_raw.split("\n") if l.strip()]

                        # Reconstruir descripciones completas:
                        # Las guías SII ponen la talla en la línea siguiente a la descripción.
                        # Agrupamos: si una línea no empieza con "SALMON" ni "SALMO SALAR"
                        # la pegamos a la descripción anterior.
                        lineas_desc = []
                        for l in lineas_prod:
                            if re.match(r'^SALMO\s+SALAR\s*$', l.upper()):
                                continue  # especie — descartar
                            if (lineas_desc
                                    and not l.upper().startswith("SALMON")
                                    and not re.match(r'^\d{4,}$', l)):
                                # talla o sufijo — pegar a la descripción anterior
                                lineas_desc[-1] = lineas_desc[-1] + " " + l
                            else:
                                lineas_desc.append(l)

                        n = len(lineas_desc)
                        for i in range(n):
                            desc = lineas_desc[i]

                            # Cermaq: limpiar descripción cruda de la guía
                            if pesquera == "cermaq":
                                desc = _limpiar_desc_cermaq(desc)

                            # Extraer familia: todo lo que sigue a "Refrigerado " o "CRUDO "
                            familia_m = re.search(
                                r'(?:Refrigerado|REFRIGERADO|CRUDO)\s+(.+)',
                                desc, re.IGNORECASE
                            )
                            familia = familia_m.group(1).strip() if familia_m else desc

                            kilos = _extraer_float_guia(
                                lineas_kilos[i] if i < len(lineas_kilos) else ""
                            )
                            cajas_str = lineas_cajas[i] if i < len(lineas_cajas) else ""
                            try:
                                cajas = int(float(cajas_str.replace(",", "").replace(".", "")))
                            except (ValueError, AttributeError):
                                cajas = 0

                            if desc and (kilos or cajas):
                                productos.append({
                                    "descripcion":   desc,
                                    "familia":       familia,
                                    "kilos_totales": kilos or 0.0,
                                    "cajas_totales": cajas,
                                })

                    if productos:
                        return productos

    except Exception as e:
        print(f"[extractor_guias] parser tabla error: {e}")

    # ── Fallback: regex sobre texto crudo ─────────────────────────────────────
    # Busca líneas con el patrón "descripcion kilos cajas precio total"
    # Cubre el caso de PDFs donde extract_table() no reconoce la tabla
    return _parsear_tabla_regex(pdf_path)


def _parsear_tabla_regex(pdf_path: str) -> list[dict]:
    """
    Fallback: extrae productos del texto crudo con regex.
    Patrón AquaChile/SII: DESCRIPCION <kilos> <cajas> <precio> <total>
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

        productos = []
        # Buscar líneas que contengan la descripción característica
        patron = re.compile(
            r'(SALMON[^\n]{5,80}?(?:KG|LB|G))'   # descripción hasta la talla
            r'\s*\n?'
            r'(?:SALMO\s+SALAR\s*\n?)?'            # especie opcional
            r'\s*([\d.,]+)'                          # kilos
            r'\s+([\d.,]+)'                          # cajas
            r'\s+[\d.,]+'                            # precio unitario (descartado)
            r'\s+[\d.,]+',                           # total (descartado)
            re.IGNORECASE
        )
        for m in patron.finditer(texto):
            desc   = m.group(1).strip()
            kilos  = _extraer_float_guia(m.group(2))
            try:
                cajas = int(float(m.group(3).replace(",", "").replace(".", "")))
            except ValueError:
                cajas = 0

            familia_m = re.search(
                r'(?:Refrigerado|REFRIGERADO|CRUDO)\s+(.+)', desc, re.IGNORECASE
            )
            familia = familia_m.group(1).strip() if familia_m else desc

            if desc and (kilos or cajas):
                productos.append({
                    "descripcion":   desc,
                    "familia":       familia,
                    "kilos_totales": kilos or 0.0,
                    "cajas_totales": cajas,
                })
        return productos

    except Exception as e:
        print(f"[extractor_guias] fallback regex error: {e}")
        return []


# ── Extractor principal ───────────────────────────────────────────────────────

def extraer_datos_guia(pdf_path: str) -> Optional[dict]:
    """
    Extrae datos de una guía de despacho.
    Retorna dict con campos normalizados o None si falla.
    """
    try:
        texto = ""
        with pdfplumber.open(pdf_path) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

        if not texto.strip():
            return None

        texto_up = texto.upper()

        # Número de guía
        raw_guia    = _primera_coincidencia(texto_up, PATRONES_GUIA)
        numero_guia = _limpiar_numeros(raw_guia) if raw_guia else None

        # Pesos
        raw_pb     = _primera_coincidencia(texto_up, PATRONES_PESO_BRUTO)
        raw_pn     = _primera_coincidencia(texto_up, PATRONES_PESO_NETO)
        peso_bruto = _extraer_float(raw_pb)
        peso_neto  = _extraer_float(raw_pn)

        # Bultos
        raw_bultos = _primera_coincidencia(texto_up, PATRONES_BULTOS)
        bultos = int(_extraer_float(raw_bultos) or 0) if raw_bultos else None
        if bultos == 0:
            bultos = None

        # Patentes — intentar bloque SII primero, luego patrones individuales
        patente_tracto, patente_semi = _extraer_patentes_sii(texto_up)
        if not patente_tracto:
            patente_tracto = _primera_coincidencia(texto_up, PATRON_PATENTE_TRACTO[1:])
        if not patente_semi:
            patente_semi = _primera_coincidencia(texto_up, PATRON_PATENTE_SEMI)

        # Conductor
        raw_cond  = _primera_coincidencia(texto, PATRONES_CONDUCTOR)
        conductor = raw_cond.strip().upper() if raw_cond else None

        # Certificado sanitario / Codaut
        raw_cert       = _primera_coincidencia(texto_up, PATRONES_CERT)
        cert_sanitario = raw_cert.strip() if raw_cert else None

        # Destinatario
        raw_dest     = _primera_coincidencia(texto, PATRONES_DESTINATARIO)
        destinatario = raw_dest.strip() if raw_dest else None

        # Detectar pesquera primero — necesario para elegir el patrón correcto
        from modulos.config_cliente import detectar_pesquera
        pesquera = detectar_pesquera(texto_up)

        # Orden de venta — patrón específico por pesquera, luego fallback genérico
        patrones_ov = (PATRONES_ORDEN_VENTA_PESQUERA.get(pesquera) or []) + PATRONES_ORDEN_VENTA_GENERICO
        raw_ov      = _primera_coincidencia(texto_up, patrones_ov)
        orden_venta = raw_ov.strip() if raw_ov else None

        # Tabla de productos (parser dedicado con fallback regex)
        productos = _parsear_tabla_productos(pdf_path, pesquera=pesquera)

        # Fecha del documento — reusar patrones de extractor_facturas
        from modulos.extractor_facturas import PATRONES_FECHA, _normalizar_fecha
        raw_fecha = _primera_coincidencia(texto_up, PATRONES_FECHA)
        fecha     = _normalizar_fecha(raw_fecha) if raw_fecha else None

        return {
            "tipo":           "guia",
            "pesquera":       pesquera,
            "numero_guia":    numero_guia,
            "orden_venta":    orden_venta,
            "peso_bruto":     peso_bruto,
            "peso_neto":      peso_neto,
            "bultos":         bultos,
            "patente_tracto": patente_tracto,
            "patente_semi":   patente_semi,
            "conductor":      conductor,
            "cert_sanitario": cert_sanitario,
            "destinatario":   destinatario,
            "fecha":          fecha,
            "texto_completo": texto,
            "productos":      productos,
        }

    except Exception as e:
        print(f"[extractor_guias] Error: {e}")
        return None
