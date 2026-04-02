COLORS = {
    "bg_main":        "#f8f9fe",
    "bg_sidebar":     "#ffffff",
    "bg_card":        "#ffffff",
    "accent":         "#5e72e4",
    "accent_hover":   "#4a5cd0",
    "text_primary":   "#32325d",
    "text_secondary": "#8898aa",
    "border":         "#e9ecef",
    "success":        "#2dce89",
    "warning":        "#fb6340",
    "danger":         "#f5365c",
}

CARD_STYLE = {
    "backgroundColor": COLORS["bg_card"],
    "border":          f"1px solid {COLORS['border']}",
    "borderRadius":    "12px",
    "padding":         "24px",
    "marginBottom":    "16px",
    "boxShadow":       "0 1px 3px rgba(50,50,93,.1), 0 1px 0 rgba(0,0,0,.02)",
}

SIDEBAR_STYLE = {
    "position":        "fixed",
    "top": 0, "left": 0, "bottom": 0,
    "width":           "250px",
    "backgroundColor": COLORS["bg_sidebar"],
    "borderRight":     f"1px solid {COLORS['border']}",
    "padding":         "24px 16px",
    "overflowY":       "auto",
    "boxShadow":       "0 0 2rem 0 rgba(136,152,170,.15)",
}

CONTENT_STYLE = {
    "marginLeft":      "250px",
    "backgroundColor": COLORS["bg_main"],
    "minHeight":       "100vh",
    "padding":         "24px 32px",
}

INPUT_STYLE = {
    "backgroundColor": "#ffffff",
    "color":           "#32325d",
    "border":          f"1px solid {COLORS['border']}",
    "borderRadius":    "8px",
    "fontSize":        "14px",
    "width":           "100%",
}
