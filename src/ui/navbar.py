"""Barra de navegación superior horizontal."""

import streamlit as st

_NAV_PAGES = [
    ("Buscar",    "buscar"),
    ("Historia",  "historial"),
    ("Modificar", "modificar"),
    ("Crear",     "elaborar_crt"),
]


def render_navbar() -> None:
    """Renderiza el navbar: marca 'CRT' a la izquierda + botones de navegación."""

    # Contenedor con la clase CSS .crt-navbar
    st.markdown('<div class="crt-navbar">', unsafe_allow_html=True)

    brand_col, *btn_cols = st.columns([1, 1, 1, 1, 1])

    with brand_col:
        st.markdown(
            '<p class="crt-brand">&#x25B6;&nbsp;CRT</p>',
            unsafe_allow_html=True,
        )

    current = st.session_state.get("current_page", "elaborar_crt")

    for col, (label, page_key) in zip(btn_cols, _NAV_PAGES):
        with col:
            btn_type = "primary" if current == page_key else "secondary"
            if st.button(label, key=f"nav_{page_key}", use_container_width=True, type=btn_type):
                st.session_state["current_page"] = page_key
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
