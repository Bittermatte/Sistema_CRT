"""
Sistema CRT — Módulo 6: Aplicación principal Streamlit.
Orquesta los Módulos 1-5 con un espacio de trabajo persistente que admite
documentación incompleta (guía sin factura, o viceversa).

# TODO (Fase 2): Convertir a app multipágina para añadir el Buscador de CRTs,
#                Historial y Modificar. Ver docs/roadmap.md para el plan completo.
"""

import base64
import io
import os
import re
import sys
import tempfile
import zipfile
from difflib import SequenceMatcher

import pdfplumber
import streamlit as st

# ── Asegurar que los módulos sean importables desde cualquier directorio ───────
DIR_PROYECTO = os.path.dirname(os.path.abspath(__file__))
DIR_MODULOS  = os.path.join(DIR_PROYECTO, "modulos")
if DIR_MODULOS not in sys.path:
    sys.path.insert(0, DIR_MODULOS)

from extractor_facturas import extraer_datos_factura
from extractor_guias    import extraer_datos_guia
from motor_calculos     import calcular_fletes
from generador_glosas   import generar_textos_crt
from creador_crt        import generar_pdf_crt

PLANTILLA_CRT = os.path.join(DIR_PROYECTO, "plantillas", "crt_blanco.pdf")

# Estados posibles de una entrada del espacio de trabajo
COMPLETO       = "COMPLETO"
FALTA_FACTURA  = "FALTA_FACTURA"
FALTA_GUIA     = "FALTA_GUIA"


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers generales
# ══════════════════════════════════════════════════════════════════════════════

def _guardar_temp_bytes(data: bytes, suffix: str = ".pdf") -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        return tmp.name


def _generar_pdf_bytes(datos_completos: dict) -> bytes:
    ruta_salida = _guardar_temp_bytes(b"", suffix=".pdf")
    generar_pdf_crt(datos_completos, PLANTILLA_CRT, ruta_salida)
    with open(ruta_salida, "rb") as f:
        contenido = f.read()
    os.unlink(ruta_salida)
    return contenido


def _descripcion_carga(productos: list) -> str:
    partes = [
        f"{p['familia']} {p['cajas_totales']} CAJAS / {p['kilos_totales']} KG"
        for p in (productos or [])
    ]
    return " | ".join(partes)


def _visor_pdf(pdf_bytes: bytes, height: int = 850) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    html = (
        f'<iframe src="data:application/pdf;base64,{b64}'
        f'#toolbar=0&navpanes=0&scrollbar=0&view=FitH" '
        f'width="100%" height="{height}" type="application/pdf" '
        f'style="border: none;"></iframe>'
    )
    st.components.v1.html(html, height=height + 10, scrolling=False)


def _zip_todos(entradas: list) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for e in entradas:
            if e.get("pdf_bytes"):
                zf.writestr(e["pdf_nombre"], e["pdf_bytes"])
    buffer.seek(0)
    return buffer.read()


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a.upper().strip(), b.upper().strip()).ratio()


def _normalizar(nombre: str) -> str:
    """Clave de búsqueda normalizada para espacio_trabajo."""
    if not nombre:
        return "__sin_nombre__"
    s = re.sub(r"\s+", " ", nombre.upper().strip())
    return s.rstrip(".,;:")


# ══════════════════════════════════════════════════════════════════════════════
#  Clasificación automática de PDFs
# ══════════════════════════════════════════════════════════════════════════════

def clasificar_pdfs(archivos_subidos: list) -> tuple:
    """
    Lee la primera página de cada PDF y lo clasifica en guía o factura.

    Retorna:
        guias          — [{"name": str, "bytes": bytes, "cliente": str}]
        facturas       — [{"name": str, "bytes": bytes}]
        sin_clasificar — [str]
    """
    guias, facturas, sin_clasificar = [], [], []

    for archivo in archivos_subidos:
        datos = archivo.read()
        with pdfplumber.open(io.BytesIO(datos)) as pdf:
            texto = pdf.pages[0].extract_text() or ""

        texto_upper = texto.upper()

        if "GUIA DE DESPACHO" in texto_upper:
            m = re.search(r"CLIENTE\s*:\s*(.+?)\s+CANTIDAD", texto, re.IGNORECASE)
            cliente = m.group(1).strip() if m else ""
            guias.append({"name": archivo.name, "bytes": datos, "cliente": cliente})

        elif "FACTURA" in texto_upper:
            facturas.append({"name": archivo.name, "bytes": datos})

        else:
            sin_clasificar.append(archivo.name)

    return guias, facturas, sin_clasificar


# ══════════════════════════════════════════════════════════════════════════════
#  Recálculo del espacio de trabajo
# ══════════════════════════════════════════════════════════════════════════════

def _recalcular(tarifa: float, pais_destino: str) -> None:
    """
    Recorre todo el espacio_trabajo y:
    1. Agrupa el peso_bruto por patente para obtener el peso total del camión.
    2. Recalcula los fletes de cada entrada que tenga guía.
    3. Genera las glosas y el PDF para cada entrada (blancos incluidos).
    """
    et = st.session_state.espacio_trabajo

    # ── Paso 1: peso total por patente ────────────────────────────────────
    peso_por_patente: dict = {}
    for entry in et.values():
        if entry["guia"]:
            pt = entry["guia"].get("patente_tracto") or "SIN_PATENTE"
            peso_por_patente[pt] = (
                peso_por_patente.get(pt, 0.0)
                + (entry["guia"].get("peso_bruto") or 0.0)
            )

    # ── Paso 2 y 3: calcular y generar PDF para cada entrada ──────────────
    for entry in et.values():
        num = entry["correlativo"]

        # Glosas siempre se generan (usan pais_destino del usuario)
        glosas = generar_textos_crt(pais_destino, num)
        entry["glosas"]    = glosas
        entry["numero_crt"]  = glosas["correlativo_casilla_2"]
        entry["pdf_nombre"]  = (
            f"CRT_{glosas['correlativo_casilla_2'].replace('/', '-')}.pdf"
        )

        # Fletes solo si hay guía
        if entry["guia"]:
            pt = entry["guia"].get("patente_tracto") or "SIN_PATENTE"
            peso_total = peso_por_patente.get(
                pt, entry["guia"].get("peso_bruto") or 0.0
            )
            entry["fletes"] = calcular_fletes(
                peso_bruto_cliente      = entry["guia"].get("peso_bruto") or 0.0,
                peso_bruto_total_camion = peso_total,
                tarifa_base_viaje       = tarifa,
            )
        else:
            entry["fletes"] = None

        # Construir datos_completos (campos ausentes quedan vacíos → tolerancia M5)
        guia    = entry.get("guia")    or {}
        factura = entry.get("factura") or {}
        fletes  = entry.get("fletes")  or {}

        datos_completos = {
            "numero_crt":        glosas.get("correlativo_casilla_2") or "",
            "remitente":         "EMPRESAS AQUACHILE S.A.",
            "destinatario":      factura.get("destinatario") or "",
            "direccion":         factura.get("direccion") or "",
            "pais_destino":      pais_destino.upper(),
            "casilla_8":         glosas.get("texto_casilla_8") or "",
            "descripcion_carga": _descripcion_carga(guia.get("productos")),
            "bultos":            str(guia.get("bultos") or ""),
            "peso_neto":         str(guia.get("peso_neto") or ""),
            "peso_bruto":        str(guia.get("peso_bruto") or ""),
            "flete_total":  f"USD {fletes['flete_prorrateado']}"    if fletes else "",
            "flete_8_pct":  f"USD {fletes['flete_origen_frontera']}" if fletes else "",
            "flete_92_pct": f"USD {fletes['flete_frontera_destino']}" if fletes else "",
            "patente_tracto":    guia.get("patente_tracto") or "",
            "patente_semi":      guia.get("patente_semi") or "",
            "casilla_18":        glosas.get("texto_casilla_18") or "",
        }

        try:
            entry["pdf_bytes"] = _generar_pdf_bytes(datos_completos)
        except Exception as exc:
            entry["pdf_bytes"]  = None
            entry["pdf_error"]  = str(exc)


# ══════════════════════════════════════════════════════════════════════════════
#  Lógica de ingesta (el embudo)
# ══════════════════════════════════════════════════════════════════════════════

def ingestar(archivos_subidos, correlativo_base, tarifa, pais_destino):
    """
    Clasifica los PDFs nuevos, actualiza el espacio_trabajo y recalcula.
    NO borra entradas previas; solo las actualiza o añade nuevas.
    """
    et = st.session_state.espacio_trabajo

    # Inicializar el contador de correlativo solo la primera vez
    if "correlativo_contador" not in st.session_state:
        st.session_state.correlativo_contador = correlativo_base

    sin_cls_nombres = []
    avisos = []

    # ── Paso 1: clasificar ────────────────────────────────────────────────
    guias_raw, facturas_raw, sin_cls = clasificar_pdfs(archivos_subidos)
    sin_cls_nombres = sin_cls

    # ── Paso 2: procesar guías (Módulo 2) ─────────────────────────────────
    for g in guias_raw:
        ruta = _guardar_temp_bytes(g["bytes"])
        try:
            datos = extraer_datos_guia(ruta)
            datos["_cliente_raw"] = g["cliente"]
            datos["_nombre_pdf"]  = g["name"]
            key = _normalizar(g["cliente"])

            if key not in et:
                num = st.session_state.correlativo_contador
                st.session_state.correlativo_contador += 1
                et[key] = {
                    "estado":          FALTA_FACTURA,
                    "cliente_display": g["cliente"] or "(desconocido)",
                    "correlativo":     num,
                    "numero_crt":      None,
                    "guia":            datos,
                    "guia_nombre":     g["name"],
                    "factura":         None,
                    "factura_nombre":  None,
                    "fletes":          None,
                    "glosas":          None,
                    "pdf_bytes":       None,
                    "pdf_nombre":      None,
                }
            else:
                # Actualizar guía en entrada existente
                et[key]["guia"]       = datos
                et[key]["guia_nombre"] = g["name"]
                et[key]["estado"] = (
                    COMPLETO if et[key]["factura"] else FALTA_FACTURA
                )
        finally:
            os.unlink(ruta)

    # ── Paso 3: procesar facturas (Módulo 1) ──────────────────────────────
    for f in facturas_raw:
        ruta = _guardar_temp_bytes(f["bytes"])
        try:
            datos = extraer_datos_factura(ruta)
            datos["_nombre_pdf"] = f["name"]
            destinatario = datos.get("destinatario") or ""

            # Buscar coincidencia en TODO el espacio_trabajo (incluye FALTA_FACTURA previas)
            mejor_key   = None
            mejor_score = 0.0
            for key, entry in et.items():
                score = _similitud(destinatario, entry["cliente_display"])
                if score > mejor_score:
                    mejor_score = score
                    mejor_key   = key

            if mejor_key and mejor_score >= 0.5:
                et[mejor_key]["factura"]       = datos
                et[mejor_key]["factura_nombre"] = f["name"]
                et[mejor_key]["estado"] = (
                    COMPLETO if et[mejor_key]["guia"] else FALTA_GUIA
                )
            else:
                # Sin guía aún — crear entrada de espera
                key = _normalizar(destinatario or f["name"])
                if key not in et:
                    num = st.session_state.correlativo_contador
                    st.session_state.correlativo_contador += 1
                    et[key] = {
                        "estado":          FALTA_GUIA,
                        "cliente_display": destinatario or "(desconocido)",
                        "correlativo":     num,
                        "numero_crt":      None,
                        "guia":            None,
                        "guia_nombre":     None,
                        "factura":         datos,
                        "factura_nombre":  f["name"],
                        "fletes":          None,
                        "glosas":          None,
                        "pdf_bytes":       None,
                        "pdf_nombre":      None,
                    }
                else:
                    et[key]["factura"]       = datos
                    et[key]["factura_nombre"] = f["name"]
                    et[key]["estado"] = (
                        COMPLETO if et[key]["guia"] else FALTA_GUIA
                    )
                avisos.append(
                    f"Factura de '{destinatario}' sin guía coincidente (score "
                    f"{mejor_score:.0%}). Queda en espera."
                )
        finally:
            os.unlink(ruta)

    # ── Paso 4: recalcular todo el espacio_trabajo ────────────────────────
    _recalcular(tarifa, pais_destino)

    # Reportar resultados al usuario
    if sin_cls_nombres:
        st.warning(f"Sin clasificar: {', '.join(sin_cls_nombres)}")
    for av in avisos:
        st.info(av)


# ══════════════════════════════════════════════════════════════════════════════
#  Vista 1: Formulario de carga
# ══════════════════════════════════════════════════════════════════════════════

def render_formulario():
    st.title("Sistema CRT — AquaChile")
    st.caption("Generación automatizada de Cartas de Porte Internacional (ALADI)")
    st.markdown("---")

    col_a, col_b = st.columns([1.4, 1])

    with col_a:
        st.subheader("Documentos del camión")
        archivos_subidos = st.file_uploader(
            "Arrastra aquí TODAS las Guías y Facturas del camión",
            type="pdf",
            accept_multiple_files=True,
            key="up_todos",
            help="Mezcla guías y facturas en cualquier orden. El sistema los clasifica automáticamente.",
        )

        # Preview de clasificación en tiempo real
        if archivos_subidos:
            preview = []
            for a in archivos_subidos:
                datos = a.read()
                a.seek(0)
                class _F:
                    def __init__(self, name, data):
                        self.name = name
                        self._data = data
                    def read(self): return self._data
                preview.append(_F(a.name, datos))

            with st.spinner("Clasificando…"):
                g_raw, f_raw, sin = clasificar_pdfs(preview)

            c1, c2, c3 = st.columns(3)
            c1.metric("Guías", len(g_raw))
            c2.metric("Facturas", len(f_raw))
            c3.metric("Sin clasificar", len(sin), delta_color="inverse")
            if sin:
                st.warning(f"No clasificados: {', '.join(sin)}")

    with col_b:
        st.subheader("Parámetros del viaje")
        correlativo_inicial = st.number_input(
            "Correlativo inicial (primer CRT)",
            min_value=1, value=5098, step=1,
        )
        tarifa = st.number_input(
            "Tarifa base del viaje (USD)",
            min_value=0.0, value=4400.0, step=50.0, format="%.2f",
        )
        pais_destino = st.text_input(
            "País de destino final",
            value="China",
            placeholder="ej. China, Mexico, Brasil",
        )
        st.text_input("N° Certificado / Referencia", placeholder="Opcional")

    st.markdown("---")

    listo = archivos_subidos and pais_destino.strip()
    if not listo:
        st.info("Sube los PDFs del camión e indica el país de destino para continuar.")

    if st.button("🚛  Procesar Camión", type="primary", disabled=not listo):
        for a in archivos_subidos:
            a.seek(0)
        with st.spinner("Clasificando, extrayendo datos y generando CRTs…"):
            ingestar(
                archivos_subidos = archivos_subidos,
                correlativo_base = int(correlativo_inicial),
                tarifa           = float(tarifa),
                pais_destino     = pais_destino.strip(),
            )
        if st.session_state.espacio_trabajo:
            st.session_state.indice_actual = 0
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  Vista 2: Visor interactivo con espacio de trabajo
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_key(k: str) -> str:
    """'peso_neto' → 'Peso Neto'"""
    return k.replace("_", " ").title()


def _render_seccion(titulo: str, datos: dict, omitir: set = None) -> None:
    omitir = omitir or set()
    filas = [
        (k, v) for k, v in datos.items()
        if not k.startswith("_") and k not in omitir and v not in (None, "", [], {})
    ]
    if not filas:
        return
    st.markdown(f"**{titulo}**")
    for k, v in filas:
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    partes = "  ·  ".join(f"{_fmt_key(ik)}: {iv}" for ik, iv in item.items())
                    st.markdown(f"- {partes}")
                else:
                    st.markdown(f"- {item}")
        else:
            st.markdown(f"- **{_fmt_key(k)}:** {v}")


def _render_datos_auditoria(entrada: dict) -> None:
    guia    = entrada.get("guia")    or {}
    factura = entrada.get("factura") or {}
    fletes  = entrada.get("fletes")  or {}
    glosas  = entrada.get("glosas")  or {}

    _render_seccion("Datos de la Guía",    guia,    omitir={"productos"})
    # Productos aparte para mostrarlos como lista clara
    if guia.get("productos"):
        st.markdown("**Productos**")
        for p in guia["productos"]:
            partes = "  ·  ".join(f"{_fmt_key(k)}: {v}" for k, v in p.items())
            st.markdown(f"- {partes}")

    _render_seccion("Datos de la Factura", factura)
    _render_seccion("Fletes Calculados",   fletes)
    _render_seccion("Glosas / Textos CRT", glosas)


def render_visor():
    et = st.session_state.espacio_trabajo

    # Lista ordenada por correlativo para la navegación
    entradas = sorted(et.values(), key=lambda e: e["correlativo"])
    total    = len(entradas)
    idx      = min(st.session_state.indice_actual, total - 1)
    entrada  = entradas[idx]

    # ── Sidebar: acciones globales ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Espacio de trabajo")
        for i, e in enumerate(entradas):
            icono = "✅" if e["estado"] == COMPLETO else "⚠️"
            etiqueta = e.get("numero_crt") or f"#{e['correlativo']}"
            if st.button(
                f"{icono} {etiqueta} — {e['cliente_display'][:22]}",
                key=f"nav_{i}",
                use_container_width=True,
            ):
                st.session_state.indice_actual = i
                st.rerun()

        st.markdown("---")
        if st.button("🗑 Limpiar Espacio de Trabajo", use_container_width=True, type="secondary"):
            st.session_state.espacio_trabajo  = {}
            st.session_state.indice_actual    = 0
            if "correlativo_contador" in st.session_state:
                del st.session_state["correlativo_contador"]
            st.rerun()

    # ── Barra de navegación ────────────────────────────────────────────────
    nav_izq, nav_centro, nav_der = st.columns([1, 3, 1])
    with nav_izq:
        if st.button("← Anterior", disabled=(idx == 0)):
            st.session_state.indice_actual -= 1
            st.rerun()
    with nav_centro:
        st.markdown(
            f"<h4 style='text-align:center; margin:0'>"
            f"Viendo CRT {idx + 1} de {total}</h4>",
            unsafe_allow_html=True,
        )
    with nav_der:
        if st.button("Siguiente →", disabled=(idx == total - 1)):
            st.session_state.indice_actual += 1
            st.rerun()

    st.markdown("---")

    # ── Pantalla dividida ──────────────────────────────────────────────────
    col_ctrl, col_pdf = st.columns([1, 1.5])

    with col_ctrl:
        # ── Indicador visual de estado ─────────────────────────────────
        if entrada["estado"] == COMPLETO:
            st.success("✅ COMPLETO — Todos los documentos recibidos")
        elif entrada["estado"] == FALTA_FACTURA:
            st.warning(
                "⚠️ PENDIENTE: FALTA FACTURA\n\n"
                "Los campos de valor (USD) y datos del destinatario estarán en blanco "
                "en el PDF de la derecha. Sube la factura para completar este CRT."
            )
        else:
            st.warning(
                "⚠️ PENDIENTE: FALTA GUÍA DE DESPACHO\n\n"
                "Los campos de carga (bultos, pesos, patentes) estarán en blanco. "
                "Sube la guía para completar este CRT."
            )

        st.subheader("Resumen")
        st.markdown(f"**Correlativo:** `{entrada.get('numero_crt') or entrada['correlativo']}`")
        st.markdown(f"**Cliente:** {entrada['cliente_display']}")

        guia    = entrada.get("guia")    or {}
        factura = entrada.get("factura") or {}
        fletes  = entrada.get("fletes")  or {}

        if guia:
            st.markdown(
                f"**Patente Tracto:** `{guia.get('patente_tracto') or '—'}`  "
                f"**Semi:** `{guia.get('patente_semi') or '—'}`"
            )
            st.markdown("**Carga**")
            c1, c2, c3 = st.columns(3)
            _neto   = guia.get("peso_neto")
            _bruto  = guia.get("peso_bruto")
            c1.metric("Bultos",   guia.get("bultos") or "—")
            c2.metric("P. Neto",  f"{float(_neto):.2f} kg"  if _neto  is not None else "—")
            c3.metric("P. Bruto", f"{float(_bruto):.2f} kg" if _bruto is not None else "—")

        if fletes:
            st.markdown("**Fletes**")
            st.markdown(f"- Total: **USD {fletes['flete_prorrateado']}**")
            st.markdown(f"- 8 %: USD {fletes['flete_origen_frontera']}")
            st.markdown(f"- 92 %: USD {fletes['flete_frontera_destino']}")

        if factura:
            st.markdown(
                f"**Incoterm:** {factura.get('incoterm') or '—'}  "
                f"**Moneda:** {factura.get('moneda') or '—'}"
            )

        # Archivos de origen
        if entrada.get("guia_nombre"):
            st.caption(f"📄 Guía: {entrada['guia_nombre']}")
        if entrada.get("factura_nombre"):
            st.caption(f"📄 Factura: {entrada['factura_nombre']}")

        # Auditoría: todos los datos extraídos
        with st.expander("Ver todos los datos extraídos", expanded=True):
            _render_datos_auditoria(entrada)

        st.markdown("---")

        # Botón de descarga individual
        if entrada.get("pdf_bytes"):
            st.download_button(
                label     = "⬇ Descargar este CRT",
                data      = entrada["pdf_bytes"],
                file_name = entrada.get("pdf_nombre", "crt.pdf"),
                mime      = "application/pdf",
                use_container_width=True,
            )
        else:
            st.button("⬇ PDF no disponible", disabled=True, use_container_width=True)

        if st.button("↩ Volver al formulario", use_container_width=True):
            st.session_state.indice_actual = 0
            st.rerun()

    with col_pdf:
        st.subheader("Vista previa del documento")
        if entrada.get("pdf_bytes"):
            _visor_pdf(entrada["pdf_bytes"], height=820)
        else:
            st.info("PDF no generado para esta entrada.")

    # ── Pie: descarga masiva ───────────────────────────────────────────────
    st.markdown("---")
    completos = [e for e in entradas if e["estado"] == COMPLETO and e.get("pdf_bytes")]
    todos     = [e for e in entradas if e.get("pdf_bytes")]

    c_left, c_right = st.columns(2)
    with c_left:
        st.caption(f"{len(completos)} CRT(s) completos · {total - len(completos)} pendiente(s)")
        if completos:
            st.download_button(
                label     = f"⬇ Descargar solo los COMPLETOS ({len(completos)}) en ZIP",
                data      = _zip_todos(completos),
                file_name = "CRTs_Completos_AquaChile.zip",
                mime      = "application/zip",
                use_container_width=True,
            )
    with c_right:
        if todos:
            st.download_button(
                label     = f"⬇ Descargar TODOS los CRTs ({len(todos)}) en ZIP",
                data      = _zip_todos(todos),
                file_name = "CRTs_AquaChile.zip",
                mime      = "application/zip",
                type      = "primary",
                use_container_width=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  Punto de entrada
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title            = "Sistema CRT — AquaChile",
    page_icon             = "🚛",
    layout                = "wide",
    initial_sidebar_state = "expanded",
)

# Inicializar session_state
for _k, _v in [("espacio_trabajo", {}), ("indice_actual", 0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

if st.session_state.espacio_trabajo:
    render_visor()
else:
    render_formulario()
