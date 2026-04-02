from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

from src.dash_ui.theme import COLORS, CONTENT_STYLE, CARD_STYLE
from src.dash_ui.components.sidebar import sidebar
from src.dash_ui.components.navbar import navbar
from src.dash_ui.pages import elaborar_crt, buscar, historial

BREADCRUMBS = {
    "/":          "Dashboard",
    "/dashboard": "Dashboard",
    "/elaborar":  "Elaborar CRT",
    "/buscar":    "Buscar",
    "/historial": "Historial",
}


def serve_layout():
    return html.Div(
        style={"backgroundColor": COLORS["bg_main"], "fontFamily": "'Inter', sans-serif"},
        children=[
            dcc.Location(id="url"),
            html.Div(id="sidebar-container", children=sidebar("/")),
            html.Div(
                style=CONTENT_STYLE,
                children=[
                    navbar(),
                    html.Div(id="page-content"),
                ],
            ),
        ],
    )


def _dashboard():
    from src.dash_ui.components.stat_card import stat_card
    return html.Div([
        # Fila de stat cards
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "16px", "marginBottom": "32px"},
            children=[
                # TODO Fase 2: conectar a BD
                stat_card("Documentos hoy",   "—", "📄",  COLORS["accent"]),
                stat_card("Este mes",          "—", "📅",  COLORS["success"]),
                stat_card("Clientes activos",  "—", "🏢",  COLORS["warning"]),
            ],
        ),

        # Card central de bienvenida
        html.Div(
            style={
                **CARD_STYLE,
                "textAlign":       "center",
                "padding":         "48px 32px",
                "maxWidth":        "640px",
                "margin":          "0 auto",
            },
            children=[
                html.Div(
                    style={
                        "width":           "72px",
                        "height":          "72px",
                        "borderRadius":    "20px",
                        "backgroundColor": COLORS["accent"],
                        "display":         "flex",
                        "alignItems":      "center",
                        "justifyContent":  "center",
                        "fontSize":        "32px",
                        "margin":          "0 auto 24px",
                    },
                    children="📋",
                ),
                html.H3(
                    "Sistema CRT — Transportes Vesprini",
                    style={"color": COLORS["text_primary"], "fontWeight": "700", "marginBottom": "12px"},
                ),
                html.P(
                    "Generación automatizada de Cartas de Porte Internacional",
                    style={
                        "color":        COLORS["text_secondary"],
                        "fontSize":     "15px",
                        "marginBottom": "32px",
                        "lineHeight":   "1.6",
                    },
                ),
                dbc.Button(
                    "➕  Nuevo CRT",
                    href="/elaborar",
                    style={
                        "backgroundColor": COLORS["accent"],
                        "border":          "none",
                        "borderRadius":    "10px",
                        "padding":         "14px 36px",
                        "fontSize":        "15px",
                        "fontWeight":      "600",
                        "color":           "#fff",
                        "textDecoration":  "none",
                    },
                ),
            ],
        ),
    ])


def register_callbacks(app):
    @app.callback(
        Output("page-content",       "children"),
        Output("sidebar-container",  "children"),
        Output("page-breadcrumb",    "children"),
        Input("url", "pathname"),
    )
    def display_page(pathname):
        breadcrumb = BREADCRUMBS.get(pathname or "/", "—")

        if pathname in ("/", "/dashboard", None):
            page = _dashboard()
        elif pathname == "/elaborar":
            page = elaborar_crt.layout()
        elif pathname == "/buscar":
            page = buscar.layout()
        elif pathname == "/historial":
            page = historial.layout()
        else:
            page = html.Div(
                html.H5("404 — Página no encontrada", style={"color": COLORS["text_secondary"]}),
            )

        return page, sidebar(pathname or "/"), breadcrumb
