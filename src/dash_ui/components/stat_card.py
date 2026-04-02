from dash import html
from src.dash_ui.theme import CARD_STYLE, COLORS


def stat_card(title: str, value: str, icon: str = None, color: str = None):
    accent = color or COLORS["accent"]
    return html.Div(
        style=CARD_STYLE,
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=[
                    html.Div([
                        html.P(title, style={
                            "color": COLORS["text_secondary"],
                            "fontSize": "12px",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.5px",
                            "margin": "0 0 4px 0",
                        }),
                        html.H4(value, style={
                            "color": COLORS["text_primary"],
                            "margin": 0,
                            "fontSize": "24px",
                            "fontWeight": "600",
                        }),
                    ]),
                    html.Div(
                        style={
                            "width": "48px",
                            "height": "48px",
                            "borderRadius": "12px",
                            "backgroundColor": accent,
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "fontSize": "20px",
                        },
                        children=icon or "",
                    ),
                ],
            )
        ],
    )
