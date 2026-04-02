import dash
import dash_bootstrap_components as dbc

from src.dash_ui.layout import serve_layout, register_callbacks
from src.dash_ui.theme import COLORS

GLOBAL_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background-color: {COLORS["bg_main"]};
    color: {COLORS["text_primary"]};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}
a {{ color: {COLORS["accent"]}; }}
a:hover {{ opacity: 0.85; }}

/* Sidebar y navbar: texto oscuro sobre fondo claro */
.sidebar-label {{
    color: {COLORS["text_secondary"]};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* Accordion claro */
.accordion-button {{
    color: {COLORS["text_primary"]} !important;
    background-color: {COLORS["bg_card"]} !important;
    font-weight: 600;
    font-size: 13px;
}}
.accordion-button:not(.collapsed) {{
    color: {COLORS["accent"]} !important;
    background-color: #f0f3ff !important;
    box-shadow: none !important;
}}
.accordion-item {{
    background-color: {COLORS["bg_card"]};
    border-color: {COLORS["border"]};
}}
.accordion-body {{
    background-color: {COLORS["bg_card"]};
    padding: 16px;
}}

/* Inputs */
input, textarea, select {{
    color: {COLORS["text_primary"]} !important;
    background-color: #ffffff !important;
}}
input::placeholder, textarea::placeholder {{
    color: {COLORS["text_secondary"]};
}}

/* Animación de cambio de página */
#page-content {{
    animation: fadeIn 0.2s ease-in;
}}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {COLORS["bg_main"]}; }}
::-webkit-scrollbar-thumb {{ background: {COLORS["border"]}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {COLORS["accent"]}; }}

/* Responsive */
@media (max-width: 768px) {{
    #sidebar-container {{ display: none; }}
    #page-content {{ margin-left: 0 !important; }}
}}
"""

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
    ],
    suppress_callback_exceptions=True,
    title="Sistema CRT",
)

app.index_string = app.index_string.replace(
    "</head>",
    f"<style>{GLOBAL_CSS}</style></head>",
)

app.layout = serve_layout
register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, port=8051, host="0.0.0.0")
