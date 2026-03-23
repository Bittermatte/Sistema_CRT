"""
Fase 2 stub — Historial de CRTs emitidos.
Implementará: consulta a PostgreSQL, st.dataframe interactivo con filtros
por fecha/destinatario, botón de descarga PDF, modificación de CRTs existentes.
"""

import streamlit as st


def render_historial():
    st.header("Historial de CRTs")
    st.info(
        "Esta funcionalidad estará disponible en la **Fase 2**.",
        icon="🚧",
    )
    st.caption(
        "Fase 2 implementará: listado completo de CRTs emitidos, búsqueda por "
        "fecha / remitente / destinatario, descarga de PDF, y modificación de "
        "documentos existentes con integración a base de datos PostgreSQL."
    )
