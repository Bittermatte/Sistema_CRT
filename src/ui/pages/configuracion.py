"""
Fase 3 stub — Configuración API / App Móvil.
Implementará: gestión de tokens JWT para la app móvil, configuración
de endpoints REST, permisos de usuarios en terreno y parámetros de conexión.
"""

import streamlit as st


def render_configuracion():
    st.header("Configuración API — App Móvil")
    st.info(
        "Esta funcionalidad estará disponible en la **Fase 3**.",
        icon="🚧",
    )
    st.caption(
        "Fase 3 implementará: endpoints REST para la app móvil (visualización, "
        "revisión y aprobación de CRTs y MICs en terreno), autenticación JWT, "
        "y configuración de permisos por usuario."
    )
