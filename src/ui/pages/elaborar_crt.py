import streamlit as st

from src.services.pdf_service import render_pdf_with_overlay
from src.utils.constants import INCOTERM_OPTIONS, EMBALAJE_TYPES, COUNTRIES


def render_elaborar_crt():
    # ── Zona de carga de documentos origen ───────────────────────────────────
    with st.expander("📎  Cargar documentos origen  (Guías de Despacho / Facturas)", expanded=True):
        st.caption(
            "Arrastra los PDFs aquí o haz clic en **Browse files** para buscarlos. "
            "El sistema extraerá los datos y completará el formulario automáticamente. "
            "_(Extracción automática disponible próximamente)_"
        )
        uploaded_files = st.file_uploader(
            label="documentos",
            type=["pdf"],
            accept_multiple_files=True,
            key="uploaded_docs",
            label_visibility="collapsed",
        )
        if uploaded_files:
            for f in uploaded_files:
                st.success(f"**{f.name}**  —  {f.size / 1024:.1f} KB", icon="📄")

    st.divider()

    # ── Botonera ─────────────────────────────────────────────────────────────
    _, col_limpiar, col_guardar = st.columns([7, 1.2, 1.5])
    with col_limpiar:
        if st.button("Limpiar formulario", use_container_width=True):
            _limpiar_formulario()
    with col_guardar:
        st.button("Guardar CRT", use_container_width=True, type="primary")

    st.divider()

    # ── Pantalla dividida: formulario (55%) | preview (45%) ─────────────────
    col_form, col_preview = st.columns([11, 9], gap="large")

    with col_form:
        _render_crt_form()

    with col_preview:
        _render_pdf_preview()


# ── Formulario CRT — 24 Campos ───────────────────────────────────────────────

def _render_crt_form():
    st.subheader("Datos del CRT")

    # ── 1. Identificación del Documento ──────────────────────────────────────
    with st.expander("Identificación del Documento", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "1. Número de CRT",
                key="f_numero_crt",
                placeholder="Ej: CRT-2026-0001",
            )
        with c2:
            st.text_input(
                "2. Lugar de Emisión",
                key="f_lugar_emision",
                placeholder="Ej: Santiago, Chile",
            )
        c3, c4 = st.columns(2)
        with c3:
            st.date_input("3. Fecha de Emisión", key="f_fecha_emision")
        with c4:
            st.date_input(
                "5. Fecha del Documento",
                key="f_fecha_documento",
                help="Casilla 5: toma la fecha de la Factura origen.",
            )

    # ── 2. Remitente ──────────────────────────────────────────────────────────
    with st.expander("Remitente", expanded=True):
        st.text_input(
            "4. Remitente (Nombre / Razón Social)",
            key="f_remitente",
            placeholder="Ej: Comercial Andina SpA",
        )
        st.text_area(
            "6. Dirección del Remitente",
            key="f_dir_remitente",
            placeholder="Calle, número, ciudad, país",
            height=80,
        )

    # ── 3. Destinatario ───────────────────────────────────────────────────────
    with st.expander("Destinatario", expanded=True):
        st.text_input(
            "8. Destinatario (Nombre / Razón Social)",
            key="f_destinatario",
            placeholder="Ej: Importadora Sur SA",
        )
        st.text_area(
            "9. Dirección del Destinatario",
            key="f_dir_destinatario",
            placeholder="Calle, número, ciudad, país",
            height=80,
        )

    # ── 4. Transporte y Ruta ──────────────────────────────────────────────────
    with st.expander("Transporte y Ruta", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "10. Transportista",
                key="f_transportista",
                placeholder="Ej: Transportes del Sur Ltda",
            )
        with c2:
            st.date_input(
                "7. Fecha de Entrega Estimada",
                key="f_fecha_entrega",
                help="Casilla 7: fecha estimada de llegada al destino.",
            )
        c3, c4 = st.columns(2)
        with c3:
            st.selectbox("11. País de Origen", key="f_pais_origen", options=COUNTRIES)
        with c4:
            st.selectbox("12. País de Destino", key="f_pais_destino", options=COUNTRIES)
        c5, c6 = st.columns(2)
        with c5:
            st.text_input(
                "13. Lugar de Recepción",
                key="f_lugar_recepcion",
                placeholder="Ej: Puerto Natales",
            )
        with c6:
            st.text_input(
                "16. Lugar de Entrega",
                key="f_lugar_entrega",
                placeholder="Ej: Buenos Aires, Argentina",
            )

    # ── 5. Condiciones Comerciales ────────────────────────────────────────────
    with st.expander("Condiciones Comerciales", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox(
                "14. Incoterm",
                key="f_incoterm",
                options=INCOTERM_OPTIONS,
                help="Casilla 14: extraído de la Factura origen.",
            )
        with c2:
            st.number_input(
                "15. Valor del Flete (USD)",
                key="f_flete_usd",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                help="Casilla 15: resultado del prorrateo de flete.",
            )
        c3, c4 = st.columns(2)
        with c3:
            st.number_input(
                "17. Número de Bultos",
                key="f_num_bultos",
                min_value=0,
                step=1,
            )
        with c4:
            st.text_input(
                "24. Número de Factura Comercial",
                key="f_num_factura",
                placeholder="Ej: FAC-2026-00123",
            )
        st.text_area(
            "18. Instrucciones de Aduana",
            key="f_instrucciones_aduana",
            placeholder="Ej: DEPOSITO FISCAL FRIO DOCK...",
            height=80,
            help="Casilla 18: glosas especiales o código Codaut.",
        )

    # ── 6. Descripción de la Carga ────────────────────────────────────────────
    with st.expander("Descripción de la Carga", expanded=True):
        st.text_area(
            "20. Descripción de la Mercadería",
            key="f_descripcion",
            placeholder="Descripción detallada de los bienes transportados",
            height=100,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "21. Peso Neto (kg)",
                key="f_peso_neto",
                min_value=0.0,
                step=0.1,
                format="%.2f",
            )
        with c2:
            st.number_input(
                "22. Peso Bruto (kg)",
                key="f_peso_bruto",
                min_value=0.0,
                step=0.1,
                format="%.2f",
            )
        c3, c4 = st.columns(2)
        with c3:
            st.selectbox(
                "19. Tipo de Embalaje",
                key="f_tipo_embalaje",
                options=EMBALAJE_TYPES,
            )
        with c4:
            st.text_input(
                "23. Marcas y Números",
                key="f_marcas_numeros",
                placeholder="Ej: SIN MARCAS",
            )


# ── Live Preview PDF ─────────────────────────────────────────────────────────

def _render_pdf_preview():
    st.subheader("Vista Previa — Plantilla CRT")

    img_bytes = render_pdf_with_overlay(dict(st.session_state))

    if img_bytes is None:
        st.warning(
            "No se encontró `plantillas/crt_blanco.pdf`. "
            "Verifique que el archivo existe en el directorio del proyecto.",
            icon="⚠️",
        )
        return

    st.image(img_bytes, use_container_width=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _limpiar_formulario():
    """Elimina del session_state todos los keys del formulario (prefijo f_)."""
    keys_to_delete = [k for k in st.session_state if k.startswith("f_")]
    for k in keys_to_delete:
        del st.session_state[k]
