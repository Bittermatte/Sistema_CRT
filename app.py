"""
Sistema CRT — Punto de entrada principal Streamlit.
Responsabilidades: config de página, session state, navbar y despacho de páginas.
"""

import streamlit as st
from dotenv import load_dotenv

from src.ui.navbar import render_navbar
from src.ui.styles import inject_global_styles
from src.ui.pages.elaborar_crt import render_elaborar_crt
from src.ui.pages.buscar import render_buscar
from src.ui.pages.historial import render_historial
from src.ui.pages.modificar import render_modificar

load_dotenv()

st.set_page_config(
    page_title="CRT",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_styles()

DEFAULTS: dict = {
    "current_page": "elaborar_crt",
    "crt_form_data": {},
    "crt_submitted": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

render_navbar()

PAGE_MAP = {
    "elaborar_crt": render_elaborar_crt,
    "buscar":        render_buscar,
    "historial":     render_historial,
    "modificar":     render_modificar,
}

PAGE_MAP.get(st.session_state["current_page"], render_elaborar_crt)()
