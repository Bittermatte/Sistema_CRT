from dash import html, dcc
import dash_iconify as di
from src.dash_ui.theme import COLORS


def navbar():
    return html.Div(
        style={
            "display":        "flex",
            "alignItems":     "center",
            "justifyContent": "space-between",
            "marginBottom":   "28px",
            "paddingBottom":  "16px",
            "borderBottom":   f"1px solid {COLORS['border']}",
        },
        children=[
            # Breadcrumb — izquierda
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "8px"},
                children=[
                    di.DashIconify(icon="mdi:home-outline", width=16, color=COLORS["text_secondary"]),
                    html.Span("/", style={"color": COLORS["text_secondary"], "fontSize": "13px"}),
                    html.Span(
                        id="page-breadcrumb",
                        style={
                            "color":      COLORS["text_primary"],
                            "fontSize":   "14px",
                            "fontWeight": "600",
                        },
                    ),
                ],
            ),

            # Derecha — búsqueda + usuario
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "16px"},
                children=[
                    html.Div(
                        style={
                            "display":         "flex",
                            "alignItems":      "center",
                            "gap":             "8px",
                            "backgroundColor": COLORS["bg_card"],
                            "border":          f"1px solid {COLORS['border']}",
                            "borderRadius":    "8px",
                            "padding":         "8px 14px",
                            "width":           "240px",
                        },
                        children=[
                            di.DashIconify(icon="mdi:magnify", width=16, color=COLORS["text_secondary"]),
                            dcc.Input(
                                placeholder="Buscar CRT...",
                                type="text",
                                style={
                                    "background": "transparent",
                                    "border":     "none",
                                    "outline":    "none",
                                    "color":      COLORS["text_primary"],
                                    "fontSize":   "13px",
                                    "width":      "100%",
                                },
                                debounce=True,
                            ),
                        ],
                    ),
                    di.DashIconify(icon="mdi:bell-outline", width=20, color=COLORS["text_secondary"]),
                    html.Div(
                        style={
                            "width":           "34px",
                            "height":          "34px",
                            "borderRadius":    "50%",
                            "backgroundColor": COLORS["accent"],
                            "display":         "flex",
                            "alignItems":      "center",
                            "justifyContent":  "center",
                            "color":           "#fff",
                            "fontWeight":      "600",
                            "fontSize":        "14px",
                            "cursor":          "pointer",
                        },
                        children="V",
                    ),
                ],
            ),
        ],
    )
