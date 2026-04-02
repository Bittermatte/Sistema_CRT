from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import dash_iconify as di

from src.dash_ui.theme import COLORS, CARD_STYLE

_TABLE_STYLE = dict(
    style_table={
        "overflowX":       "auto",
        "borderRadius":    "8px",
        "border":          f"1px solid {COLORS['border']}",
    },
    style_header={
        "backgroundColor": COLORS["bg_card"],
        "color":           COLORS["text_primary"],
        "fontWeight":      "600",
        "fontSize":        "12px",
        "textTransform":   "uppercase",
        "letterSpacing":   "0.5px",
        "border":          f"1px solid {COLORS['border']}",
    },
    style_data={
        "backgroundColor": COLORS["bg_main"],
        "color":           COLORS["text_primary"],
        "border":          f"1px solid {COLORS['border']}",
        "fontSize":        "13px",
    },
    style_data_conditional=[
        {"if": {"row_index": "odd"}, "backgroundColor": COLORS["bg_card"]},
    ],
)

COLUMNS = [
    {"name": "Número CRT",  "id": "numero_crt"},
    {"name": "Remitente",   "id": "remitente"},
    {"name": "Destinatario","id": "destinatario"},
    {"name": "Fecha",       "id": "fecha"},
    {"name": "Acciones",    "id": "acciones"},
]


def layout():
    return html.Div([
        html.H4("Buscar CRT", style={"color": COLORS["text_primary"], "marginBottom": "20px"}),

        # Barra de búsqueda
        html.Div(
            style=CARD_STYLE,
            children=html.Div(
                style={"display": "flex", "gap": "12px", "alignItems": "center"},
                children=[
                    html.Div(
                        style={
                            "flex":            "1",
                            "display":         "flex",
                            "alignItems":      "center",
                            "gap":             "8px",
                            "backgroundColor": COLORS["bg_main"],
                            "border":          f"1px solid {COLORS['border']}",
                            "borderRadius":    "8px",
                            "padding":         "8px 14px",
                        },
                        children=[
                            di.DashIconify(icon="mdi:magnify", width=16, color=COLORS["text_secondary"]),
                            dcc.Input(
                                placeholder="Buscar por número CRT, remitente, destinatario...",
                                type="text",
                                debounce=True,
                                style={
                                    "background":  "transparent",
                                    "border":      "none",
                                    "outline":     "none",
                                    "color":       COLORS["text_primary"],
                                    "fontSize":    "13px",
                                    "width":       "100%",
                                },
                            ),
                        ],
                    ),
                    dbc.Button(
                        "Buscar",
                        style={
                            "backgroundColor": COLORS["accent"],
                            "border":          "none",
                            "borderRadius":    "8px",
                            "fontWeight":      "600",
                            "padding":         "8px 24px",
                        },
                    ),
                ],
            ),
        ),

        # Tabla
        html.Div(
            style=CARD_STYLE,
            children=[
                dash_table.DataTable(
                    columns=COLUMNS,
                    data=[],
                    **_TABLE_STYLE,
                ),
                html.P(
                    "Búsqueda disponible en Fase 2",
                    style={
                        "color":      COLORS["text_secondary"],
                        "fontSize":   "13px",
                        "textAlign":  "center",
                        "marginTop":  "20px",
                        "marginBottom": "0",
                    },
                ),
            ],
        ),
    ])
