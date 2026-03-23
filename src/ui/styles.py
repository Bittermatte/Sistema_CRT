"""CSS global inyectado vía st.markdown."""

import streamlit as st

GLOBAL_CSS = """
<style>
    /* ── Fuentes Apple ──────────────────────────────────────────────────────── */
    html, body, [class*="css"], .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                     "Helvetica Neue", Arial, sans-serif !important;
    }

    /* ── Ocultar sidebar completamente ─────────────────────────────────────── */
    [data-testid="stSidebar"]        { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* ── Fondo general ──────────────────────────────────────────────────────── */
    .stApp { background-color: #F5F5F7 !important; }

    /* ── Contenedor principal ───────────────────────────────────────────────── */
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }

    /* ── Navbar ─────────────────────────────────────────────────────────────── */
    .crt-navbar {
        position: sticky;
        top: 0;
        z-index: 999;
        background: rgba(245, 245, 247, 0.85);
        backdrop-filter: saturate(180%) blur(20px);
        -webkit-backdrop-filter: saturate(180%) blur(20px);
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        padding: 0.55rem 0;
        margin-bottom: 1.5rem;
    }
    .crt-brand {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                     "Helvetica Neue", sans-serif !important;
        font-size: 1.4rem;
        font-weight: 700;
        color: #1D1D1F;
        letter-spacing: -0.01em;
        line-height: 1;
        margin: 0;
        padding-top: 4px;
    }

    /* ── Botones Streamlit ───────────────────────────────────────────────────── */
    .stButton > button {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                     "Helvetica Neue", sans-serif !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        border-radius: 980px !important;
        padding: 0.35rem 1.1rem !important;
        transition: all 0.18s ease !important;
        border: none !important;
        letter-spacing: -0.01em;
    }

    /* Botón secundario (nav inactivo, Limpiar) */
    .stButton > button[kind="secondary"] {
        background: rgba(0, 0, 0, 0.06) !important;
        color: #1D1D1F !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(0, 0, 0, 0.10) !important;
    }

    /* Botón primario (nav activo, Guardar) */
    .stButton > button[kind="primary"] {
        background: #0071E3 !important;
        color: #FFFFFF !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #0077ED !important;
        box-shadow: 0 2px 8px rgba(0, 113, 227, 0.35) !important;
    }

    /* ── Inputs de texto ─────────────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                     "Helvetica Neue", sans-serif !important;
        font-size: 0.9rem !important;
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        border-radius: 10px !important;
        padding: 0.5rem 0.75rem !important;
        color: #1D1D1F !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
        box-shadow: none !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #0071E3 !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
        outline: none !important;
    }
    .stTextInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: #AEAEB2 !important;
    }

    /* ── Selectbox ───────────────────────────────────────────────────────────── */
    .stSelectbox > div > div {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        border-radius: 10px !important;
        font-size: 0.9rem !important;
    }

    /* ── Date input ──────────────────────────────────────────────────────────── */
    .stDateInput > div > div > input {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        border-radius: 10px !important;
        font-size: 0.9rem !important;
    }

    /* ── Etiquetas de campos ─────────────────────────────────────────────────── */
    .stTextInput > label,
    .stTextArea > label,
    .stNumberInput > label,
    .stSelectbox > label,
    .stDateInput > label {
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: #6E6E73 !important;
        letter-spacing: 0 !important;
        margin-bottom: 3px !important;
    }

    /* ── Expanders (tarjetas de sección) ─────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.07) !important;
        border-radius: 14px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
        margin-bottom: 0.6rem !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] > details > summary {
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        color: #1D1D1F !important;
        padding: 0.7rem 1rem !important;
        letter-spacing: -0.01em;
    }
    [data-testid="stExpander"] > details > summary:hover {
        background: rgba(0, 0, 0, 0.02) !important;
    }
    [data-testid="stExpander"] > details[open] > summary {
        border-bottom: 1px solid rgba(0, 0, 0, 0.06) !important;
    }
    [data-testid="stExpander"] > details > div {
        padding: 0.75rem 1rem 0.9rem !important;
    }

    /* ── Zona de carga de archivos ───────────────────────────────────────────── */
    [data-testid="stFileUploadDropzone"] {
        background: #FFFFFF !important;
        border: 1.5px dashed rgba(0, 113, 227, 0.35) !important;
        border-radius: 12px !important;
        transition: border-color 0.15s ease, background 0.15s ease !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #0071E3 !important;
        background: rgba(0, 113, 227, 0.03) !important;
    }

    /* ── Subheaders ──────────────────────────────────────────────────────────── */
    h3, .stSubheader {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                     "Helvetica Neue", sans-serif !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #1D1D1F !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 0.75rem !important;
    }

    /* ── Divisores ───────────────────────────────────────────────────────────── */
    hr, [data-testid="stDivider"] > hr {
        border: none !important;
        border-top: 1px solid rgba(0, 0, 0, 0.08) !important;
        margin: 0.75rem 0 !important;
    }

    /* ── Mensajes de éxito / warning ─────────────────────────────────────────── */
    [data-testid="stAlert"] {
        border-radius: 10px !important;
        font-size: 0.875rem !important;
    }

    /* ── Caption / texto secundario ──────────────────────────────────────────── */
    .stCaption, small, caption {
        color: #6E6E73 !important;
        font-size: 0.8rem !important;
    }

    /* ── Scrollbar sutil ──────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.28); }
</style>
"""


def inject_global_styles() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
