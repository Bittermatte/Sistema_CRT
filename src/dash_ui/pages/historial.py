from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc

from src.dash_ui.theme import COLORS, CARD_STYLE

_TABLE_STYLE = dict(
    style_table={
        "overflowX":    "auto",
        "borderRadius": "8px",
        "border":       f"1px solid {COLORS['border']}",
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
    {"name": "Número CRT",    "id": "numero_crt"},
    {"name": "Remitente",     "id": "remitente"},
    {"name": "Destinatario",  "id": "destinatario"},
    {"name": "Fecha Emisión", "id": "fecha_emision"},
    {"name": "Estado",        "id": "estado"},
]

_DROPDOWN_STYLE = {
    "backgroundColor": COLORS["bg_main"],
    "color":           COLORS["text_primary"],
    "border":          f"1px solid {COLORS['border']}",
    "borderRadius":    "8px",
}


def layout():
    return html.Div([
        html.H4("Historial de CRTs", style={"color": COLORS["text_primary"], "marginBottom": "20px"}),

        # Card de filtros
        html.Div(
            style=CARD_STYLE,
            children=[
                html.P("Filtros", style={
                    "color":       COLORS["text_secondary"],
                    "fontSize":    "11px",
                    "fontWeight":  "600",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.5px",
                    "marginBottom": "12px",
                }),
                html.Div(
                    style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "flexWrap": "wrap"},
                    children=[
                        html.Div(
                            style={"minWidth": "160px"},
                            children=[
                                html.Label("Mes", style={
                                    "color":       COLORS["text_secondary"],
                                    "fontSize":    "11px",
                                    "fontWeight":  "600",
                                    "display":     "block",
                                    "marginBottom": "4px",
                                }),
                                dcc.Dropdown(
                                    options=[],
                                    placeholder="Todos los meses",
                                    style=_DROPDOWN_STYLE,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "160px"},
                            children=[
                                html.Label("Estado", style={
                                    "color":       COLORS["text_secondary"],
                                    "fontSize":    "11px",
                                    "fontWeight":  "600",
                                    "display":     "block",
                                    "marginBottom": "4px",
                                }),
                                dcc.Dropdown(
                                    options=[],
                                    placeholder="Todos los estados",
                                    style=_DROPDOWN_STYLE,
                                ),
                            ],
                        ),
                        dbc.Button(
                            "Filtrar",
                            style={
                                "backgroundColor": COLORS["accent"],
                                "border":          "none",
                                "borderRadius":    "8px",
                                "fontWeight":      "600",
                                "padding":         "8px 24px",
                                "alignSelf":       "flex-end",
                            },
                        ),
                    ],
                ),
            ],
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
                    "Historial disponible en Fase 2",
                    style={
                        "color":        COLORS["text_secondary"],
                        "fontSize":     "13px",
                        "textAlign":    "center",
                        "marginTop":    "20px",
                        "marginBottom": "0",
                    },
                ),
            ],
        ),
    ])
