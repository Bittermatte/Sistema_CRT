from dash import html
import dash_iconify as di
from src.dash_ui.theme import COLORS, SIDEBAR_STYLE

NAV_ITEMS = [
    {"label": "Dashboard",    "href": "/",         "icon": "mdi:view-dashboard-outline"},
    {"label": "Elaborar CRT", "href": "/elaborar", "icon": "mdi:file-document-edit-outline"},
    {"label": "Buscar",       "href": "/buscar",   "icon": "mdi:magnify"},
    {"label": "Historial",    "href": "/historial","icon": "mdi:history"},
]


def _nav_link(item: dict, current_path: str):
    is_active = current_path == item["href"]
    return html.A(
        href=item["href"],
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "10px",
            "padding": "10px 12px",
            "borderRadius": "8px",
            "marginBottom": "4px",
            "textDecoration": "none",
            "color": "#ffffff" if is_active else COLORS["text_secondary"],
            "backgroundColor": COLORS["accent"] if is_active else "transparent",
            "fontWeight": "600" if is_active else "400",
            "fontSize": "14px",
            "transition": "background 0.2s",
        },
        children=[
            di.DashIconify(icon=item["icon"], width=18, color="#ffffff" if is_active else COLORS["text_secondary"]),
            item["label"],
        ],
    )


def sidebar(current_path: str = "/"):
    return html.Div(
        style=SIDEBAR_STYLE,
        children=[
            # Logo / nombre
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "32px"},
                children=[
                    di.DashIconify(icon="mdi:file-certificate-outline", width=28, color=COLORS["accent"]),
                    html.Span("Sistema CRT", style={
                        "color": COLORS["text_primary"],
                        "fontWeight": "700",
                        "fontSize": "16px",
                        "letterSpacing": "0.3px",
                    }),
                ],
            ),

            # Sección principal
            html.P("MENÚ", style={
                "color": COLORS["text_secondary"],
                "fontSize": "11px",
                "fontWeight": "600",
                "letterSpacing": "1px",
                "textTransform": "uppercase",
                "marginBottom": "8px",
                "paddingLeft": "12px",
            }),
            html.Div([_nav_link(item, current_path) for item in NAV_ITEMS]),

            # Separador
            html.Hr(style={"borderColor": COLORS["border"], "margin": "24px 0"}),

            # Sección secundaria
            html.P("SOPORTE", style={
                "color": COLORS["text_secondary"],
                "fontSize": "11px",
                "fontWeight": "600",
                "letterSpacing": "1px",
                "textTransform": "uppercase",
                "marginBottom": "8px",
                "paddingLeft": "12px",
            }),
            html.A(
                href="#",
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                    "padding": "10px 12px",
                    "borderRadius": "8px",
                    "textDecoration": "none",
                    "color": COLORS["text_secondary"],
                    "fontSize": "14px",
                },
                children=[
                    di.DashIconify(icon="mdi:book-open-outline", width=18, color=COLORS["text_secondary"]),
                    "Documentación",
                ],
            ),
        ],
    )
