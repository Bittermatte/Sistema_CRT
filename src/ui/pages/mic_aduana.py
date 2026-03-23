"""
Fase 2 stub — MIC / Integración Aduanera.
Implementará: conexión con el portal de Aduana via RPA o API,
generación automática de MICs a partir de CRTs consolidados,
login en sistema gubernamental y seguimiento de estado.
"""

import streamlit as st


def render_mic_aduana():
    st.header("MIC / Aduana")
    st.info(
        "Esta funcionalidad estará disponible en la **Fase 2**.",
        icon="🚧",
    )
    st.caption(
        "Fase 2 implementará: traspaso automático de datos consolidados de CRTs "
        "hacia el Manifiesto Internacional de Carga (MIC) en el portal aduanero, "
        "mediante integración RPA o API con el sistema gubernamental."
    )
