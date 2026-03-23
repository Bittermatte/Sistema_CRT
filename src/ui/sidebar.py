import streamlit as st


def render_sidebar():
    with st.sidebar:
        st.title("Sistema CRT")
        st.caption("Plataforma B2B de Logística Internacional")
        st.divider()

        # ── Fase 1 — Activa ───────────────────────────────────────────────
        st.subheader("Fase 1 — Documentos")
        if st.button("Elaborar CRT", key="nav_elaborar_crt", use_container_width=True):
            st.session_state["current_page"] = "elaborar_crt"

        st.divider()

        # ── Fase 2 — Próximamente ─────────────────────────────────────────
        st.subheader("Fase 2 — Gestión", help="Disponible próximamente")
        st.button(
            "Historial de CRTs",
            key="nav_historial",
            disabled=True,
            use_container_width=True,
        )
        st.button(
            "MIC / Aduana",
            key="nav_mic_aduana",
            disabled=True,
            use_container_width=True,
        )

        st.divider()

        # ── Fase 3 — Próximamente ─────────────────────────────────────────
        st.subheader("Fase 3 — App Móvil", help="Disponible próximamente")
        st.button(
            "Configuración API",
            key="nav_configuracion",
            disabled=True,
            use_container_width=True,
        )

        st.divider()
        st.caption("v0.1.0  |  Fase 1")
