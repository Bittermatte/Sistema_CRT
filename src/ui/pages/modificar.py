"""Página Modificar — stub Fase 2."""

import streamlit as st


def render_modificar() -> None:
    st.header("Modificar CRT")
    st.info("Modificación disponible en la **Fase 2**.", icon="✏️")
    st.caption(
        "Fase 2 implementará: selección de un CRT existente desde el historial "
        "y edición de sus campos con revalidación de reglas de negocio."
    )
