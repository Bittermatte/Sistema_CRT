"""Página Buscar — stub Fase 2."""

import streamlit as st


def render_buscar() -> None:
    st.header("Buscar CRT")
    st.info("Búsqueda disponible en la **Fase 2**.", icon="🔍")
    st.caption(
        "Fase 2 implementará: búsqueda por número de CRT, remitente, "
        "destinatario, rango de fechas y estado del documento."
    )
