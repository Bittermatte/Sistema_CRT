"""
Página principal — Elaborar CRT
Upload → clasificación → extracción → matching → kanban → vista detalle → PDF
"""

import base64
import io
import zipfile

from dash import html, dcc, callback, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.dash_ui.theme import COLORS, CARD_STYLE
from src.services.pdf_service import generate_crt_pdf
from src.services.audit_log import log_descarga
from modulos.config_cliente import CONFIG_ACTIVO

ESTADO_AMBIGUO = "AMBIGUO"

# ---------------------------------------------------------------------------
# Estilos locales reutilizables
# ---------------------------------------------------------------------------
_SECTION_LABEL = {
    "fontWeight":    "700",
    "fontSize":      "11px",
    "color":         COLORS["text_secondary"],
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
    "marginBottom":  "12px",
}

_CARD = {**CARD_STYLE, "marginBottom": 0}


# ---------------------------------------------------------------------------
# Helpers — formateo
# ---------------------------------------------------------------------------
def _fmt_cl(val) -> str:
    """1827.48 → '1.827,48'"""
    if val is None:
        return "—"
    try:
        v = float(val)
        if v == 0:
            return "—"
        s = f"{v:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(val) if val else "—"


# ---------------------------------------------------------------------------
# Helpers — UI / badges y kanban
# ---------------------------------------------------------------------------
def _badge(estado: str) -> html.Span:
    cfg = {
        "COMPLETO":      (COLORS["success"], "✅ COMPLETO"),
        "FALTA_FACTURA": (COLORS["warning"], "⚠️ FALTA FACTURA"),
        "FALTA_GUIA":    (COLORS["warning"], "⚠️ FALTA GUÍA"),
        "AMBIGUO":       ("#d97706",         "? AMBIGUO — Requiere selección"),
    }
    color, text = cfg.get(estado, ("#aaa", estado))
    return html.Span(text, style={
        "backgroundColor": color + "22",
        "color":           color,
        "border":          f"1px solid {color}66",
        "borderRadius":    "20px",
        "fontSize":        "10px",
        "fontWeight":      "600",
        "padding":         "2px 8px",
        "display":         "inline-block",
        "whiteSpace":      "nowrap",
    })


def _kanban_card(crt: dict, selected_id: str | None) -> html.Div:
    crt_id      = crt["id"]
    is_selected = crt_id == selected_id
    correlativo = crt.get("correlativo") or "Pendiente…"
    destinatario = (crt.get("destinatario") or "—")[:40]

    return html.Div(
        id={"type": "select-crt", "index": crt_id},
        n_clicks=0,
        style={
            "padding":         "10px 12px",
            "borderRadius":    "10px",
            "border":          f"2px solid {COLORS['accent'] if is_selected else COLORS['border']}",
            "backgroundColor": "#f0f3ff" if is_selected else COLORS["bg_card"],
            "marginBottom":    "8px",
            "cursor":          "pointer",
            "transition":      "all 0.15s",
            "userSelect":      "none",
        },
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "flex-start", "gap": "6px", "marginBottom": "4px"},
                children=[
                    html.Span(correlativo, style={
                        "fontWeight": "700", "fontSize": "12px",
                        "color": COLORS["text_primary"],
                    }),
                    _badge(crt["estado"]),
                ],
            ),
            html.P(destinatario, style={
                "fontSize": "11px", "color": COLORS["text_secondary"],
                "margin": 0, "overflow": "hidden",
                "textOverflow": "ellipsis", "whiteSpace": "nowrap",
            }),
        ],
    )


def _render_kanban_children(crts: dict, selected_id: str | None) -> list:
    if not crts:
        return [html.Div(
            style={"textAlign": "center", "padding": "24px 8px"},
            children=[
                html.Div("📂", style={"fontSize": "24px", "marginBottom": "6px"}),
                html.P("Sube documentos para empezar",
                       style={"color": COLORS["text_secondary"], "fontSize": "12px", "margin": 0}),
            ],
        )]
    return [_kanban_card(crt, selected_id) for crt in crts.values()]


# ---------------------------------------------------------------------------
# Helpers — paneles de detalle y preview
# ---------------------------------------------------------------------------
def _detail_row(label: str, value) -> html.Div | None:
    if value is None or str(value).strip() in ("", "—"):
        return None
    return html.Div(
        style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {COLORS['border']}",
        },
        children=[
            html.Span(label, style={"color": COLORS["text_secondary"], "fontSize": "11px"}),
            html.Span(str(value), style={
                "color": COLORS["text_primary"], "fontSize": "12px",
                "fontWeight": "600", "textAlign": "right", "maxWidth": "60%",
            }),
        ],
    )


def _section_hdr(title: str) -> html.P:
    return html.P(title, style={
        "color":         COLORS["text_secondary"],
        "fontSize":      "10px",
        "fontWeight":    "700",
        "textTransform": "uppercase",
        "letterSpacing": "0.5px",
        "marginTop":     "14px",
        "marginBottom":  "6px",
    })


def _render_crt_detail(crt: dict) -> html.Div:
    g  = crt.get("guia_datos")    or {}
    f  = crt.get("factura_datos") or {}
    fl = crt.get("fletes")        or {}

    def rows(*pairs):
        return [r for r in [_detail_row(k, v) for k, v in pairs] if r]

    r_resumen = rows(
        ("Correlativo",    crt.get("correlativo")),
        ("Cliente",        crt.get("destinatario")),
        ("Patente Tracto", g.get("patente_tracto")),
        ("Semi",           g.get("patente_semi")),
    )
    r_carga = rows(
        ("Bultos",     str(g["bultos"]) if g.get("bultos") else None),
        ("Peso Neto",  f"{_fmt_cl(g.get('peso_neto'))} kg"  if g.get("peso_neto")  else None),
        ("Peso Bruto", f"{_fmt_cl(g.get('peso_bruto'))} kg" if g.get("peso_bruto") else None),
    )
    r_fletes = rows(
        ("Total", f"USD {_fmt_cl(fl.get('flete_prorrateado'))}"      if fl.get("flete_prorrateado")      else None),
        ("8%",   f"USD {_fmt_cl(fl.get('flete_origen_frontera'))}"   if fl.get("flete_origen_frontera")  else None),
        ("92%",  f"USD {_fmt_cl(fl.get('flete_frontera_destino'))}"  if fl.get("flete_frontera_destino") else None),
    ) if fl else []
    r_comercial = rows(
        ("Incoterm", f.get("incoterm")),
        ("Moneda",   f.get("moneda")),
        ("Valor",    f.get("total")),
    )

    doc_items = []
    for label, key in [("Guía", "nombre_guia"), ("Factura", "nombre_factura")]:
        if crt.get(key):
            doc_items.append(html.Div([
                html.Span("📄 ", style={"color": COLORS["accent"]}),
                html.Span(f"{label}: {crt[key]}",
                          style={"fontSize": "11px", "color": COLORS["text_primary"]}),
            ], style={"padding": "2px 0"}))

    children = [_badge(crt["estado"]), html.Br()]
    if r_resumen:
        children += [_section_hdr("Resumen"), *r_resumen]
    if r_carga:
        children += [_section_hdr("Carga"), *r_carga]
    if r_fletes:
        children += [_section_hdr("Fletes"), *r_fletes]
    if r_comercial:
        children += [_section_hdr("Condiciones Comerciales"), *r_comercial]
    if doc_items:
        children += [_section_hdr("Documentos"), *doc_items]

    # ── Panel AMBIGUO: lista de sugerencias con botones de acción ────────────
    if crt["estado"] == ESTADO_AMBIGUO:
        sugerencias = crt.get("sugerencias") or []
        sug_items = []
        for idx, sug in enumerate(sugerencias):
            tipo      = sug.get("tipo", "documento")
            datos     = sug.get("datos") or {}
            nombre_a  = sug.get("nombre_archivo") or "—"
            dest      = datos.get("destinatario") or "—"
            num       = datos.get("numero_factura") or datos.get("numero_guia") or "—"
            pesquera  = datos.get("pesquera") or "—"
            btn_id    = {"type": "btn-confirmar-sugerencia", "index": f"{crt['id']}__{idx}"}
            sug_items.append(html.Div(
                style={
                    "border":        f"1px solid #d97706",
                    "borderRadius":  "8px",
                    "padding":       "8px 10px",
                    "marginBottom":  "6px",
                    "backgroundColor": "#fffbeb",
                },
                children=[
                    html.Div([
                        html.Span(f"📄 {nombre_a}",
                                  style={"fontSize": "11px", "fontWeight": "700",
                                         "color": "#92400e", "display": "block",
                                         "marginBottom": "4px"}),
                        html.Span(f"Destinatario: {dest}",
                                  style={"fontSize": "10px", "color": "#555",
                                         "display": "block"}),
                        html.Span(f"N°: {num} | Pesquera: {pesquera}",
                                  style={"fontSize": "10px", "color": "#777",
                                         "display": "block", "marginBottom": "6px"}),
                    ]),
                    dbc.Button(
                        f"✔ Confirmar esta {tipo}",
                        id=btn_id,
                        size="sm",
                        style={
                            "width":           "100%",
                            "borderRadius":    "6px",
                            "backgroundColor": "#d97706",
                            "border":          "none",
                            "color":           "#fff",
                            "fontWeight":      "600",
                            "fontSize":        "11px",
                        },
                    ),
                ],
            ))
        children += [
            _section_hdr("Selecciona el documento correcto"),
            html.Div(
                style={"backgroundColor": "#fffbeb", "borderRadius": "8px",
                       "padding": "8px", "marginBottom": "6px",
                       "border": "1px solid #fcd34d", "fontSize": "11px",
                       "color": "#92400e"},
                children="El sistema encontró un posible match por pesquera (Capa 3). "
                         "Confirma si es el documento correcto o descártalo.",
            ),
            *sug_items,
            dbc.Button(
                "✖ Descartar sugerencias",
                id={"type": "btn-descartar-sugerencias", "index": crt["id"]},
                size="sm",
                style={
                    "width":           "100%",
                    "borderRadius":    "6px",
                    "border":          f"1px solid {COLORS['danger']}",
                    "color":           COLORS["danger"],
                    "backgroundColor": "transparent",
                    "fontWeight":      "600",
                    "fontSize":        "11px",
                    "marginTop":       "4px",
                },
            ),
        ]

    children += [
        html.Hr(style={"borderColor": COLORS["border"], "margin": "12px 0"}),
        dbc.Button(
            "⬇ Descargar borrador" if crt["estado"] != "COMPLETO" else "⬇ Descargar CRT",
            id="btn-descargar-crt",
            disabled=not crt.get("form_data"),
            style={
                "width":           "100%",
                "borderRadius":    "8px",
                "fontWeight":      "600",
                "fontSize":        "13px",
                "border":          "none",
                "backgroundColor": COLORS["accent"]   if crt["estado"] == "COMPLETO"
                                   else COLORS["warning"] if crt.get("form_data")
                                   else COLORS["border"],
                "color":           "#ffffff"           if crt.get("form_data") else COLORS["text_secondary"],
            },
        ),
    ]
    return html.Div(children)


def _render_empty_detail() -> html.Div:
    return html.Div(
        style={"textAlign": "center", "padding": "32px 12px"},
        children=[
            html.Div("📋", style={"fontSize": "36px", "marginBottom": "10px"}),
            html.P("Selecciona un CRT del panel inferior para ver su detalle",
                   style={"color": COLORS["text_secondary"], "fontSize": "12px",
                          "lineHeight": "1.5"}),
        ],
    )


def _render_empty_preview() -> html.Div:
    return html.Div(
        style={
            "height":          "calc(100vh - 200px)",
            "display":         "flex",
            "alignItems":      "center",
            "justifyContent":  "center",
            "backgroundColor": COLORS["bg_main"],
            "borderRadius":    "12px",
            "border":          f"1px solid {COLORS['border']}",
        },
        children=html.Div(
            style={"textAlign": "center"},
            children=[
                html.Div("📄", style={"fontSize": "48px", "marginBottom": "12px"}),
                html.P("La vista previa aparecerá aquí",
                       style={"color": COLORS["text_secondary"], "fontSize": "14px",
                              "fontWeight": "600", "marginBottom": "4px"}),
                html.P("Selecciona un CRT completado del panel izquierdo",
                       style={"color": COLORS["text_secondary"], "fontSize": "12px"}),
            ],
        ),
    )


def _render_pdf_iframe(pdf_src: str) -> html.Iframe:
    return html.Iframe(
        src=pdf_src,
        style={
            "width":        "100%",
            "height":       "calc(100vh - 200px)",
            "border":       "none",
            "borderRadius": "12px",
        },
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    return html.Div([

        # ── Elementos invisibles (stores, downloads) ──────────────────────
        dcc.Store(id="store-crts",        storage_type="session",
                  data={"crts": {}, "next_numero": 5098}),
        dcc.Store(id="store-selected-id", storage_type="session"),
        dcc.Store(id="store-pdf-pending", storage_type="memory"),
        dcc.Download(id="download-crt"),
        dcc.Download(id="download-zip"),

        # ── Modal: advertencia PDF fallback ───────────────────────────────
        dbc.Modal(
            id="modal-fallback-pdf",
            is_open=False,
            centered=True,
            children=[
                dbc.ModalHeader(
                    html.Span("⚠️ Documento no oficial", style={"color": "#b91c1c", "fontWeight": "700"}),
                    close_button=True,
                ),
                dbc.ModalBody([
                    html.P(
                        "LibreOffice no está disponible. El PDF fue generado con el motor "
                        "de respaldo (ReportLab), que usa coordenadas aproximadas.",
                        style={"marginBottom": "10px", "fontSize": "13px"},
                    ),
                    html.Div(
                        "Un CRT con coordenadas incorrectas puede ser rechazado en Aduana. "
                        "Se ha estampado la marca 'BORRADOR NO OFICIAL' para indicar que este "
                        "documento no es el formato definitivo.",
                        style={
                            "backgroundColor": "#fef2f2",
                            "border":          "1px solid #fca5a5",
                            "borderRadius":    "6px",
                            "padding":         "10px",
                            "fontSize":        "12px",
                            "color":           "#7f1d1d",
                        },
                    ),
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        "Descargar igual (bajo mi responsabilidad)",
                        id="btn-modal-confirmar-fallback",
                        style={
                            "backgroundColor": "#b91c1c",
                            "border":          "none",
                            "color":           "#fff",
                            "fontWeight":      "600",
                            "fontSize":        "12px",
                        },
                    ),
                    dbc.Button(
                        "Cancelar",
                        id="btn-modal-cancelar-fallback",
                        style={
                            "backgroundColor": "transparent",
                            "border":          f"1px solid {COLORS['border']}",
                            "color":           COLORS["text_secondary"],
                            "fontSize":        "12px",
                        },
                    ),
                ]),
            ],
        ),

        # ── Alertas ───────────────────────────────────────────────────────
        html.Div(id="alert-container", style={"marginBottom": "12px"}),

        # ── Zona A: Upload (ancho completo) ───────────────────────────────
        dcc.Upload(
            id="upload-docs",
            accept=".pdf,.xlsx,.xls",
            multiple=True,
            children=html.Div([
                html.I(className="fas fa-cloud-upload-alt",
                       style={"fontSize": "28px", "color": "#5e72e4"}),
                html.P("Arrastra aquí las Guías de Despacho y Facturas",
                       style={"color": "#8898aa", "marginTop": "8px", "marginBottom": "2px",
                              "fontWeight": "600"}),
                html.P("PDF o Excel (.xlsx) — se clasifican y emparejan automáticamente",
                       style={"fontSize": "12px", "color": "#adb5bd"}),
            ]),
            style={
                "border":          "2px dashed #5e72e4",
                "borderRadius":    "12px",
                "padding":         "32px",
                "textAlign":       "center",
                "backgroundColor": "#f0f3ff",
                "cursor":          "pointer",
                "marginBottom":    "16px",
            },
        ),

        # ── Zona B: Layout de dos columnas ────────────────────────────────
        html.Div(
            style={
                "display":     "flex",
                "gap":         "16px",
                "alignItems":  "flex-start",
            },
            children=[

                # ── Columna izquierda (30%) ───────────────────────────────
                html.Div(
                    style={
                        "width":     "30%",
                        "minWidth":  "280px",
                        "flexShrink": 0,
                        "overflowY": "auto",
                        "height":    "calc(100vh - 200px)",
                        "display":   "flex",
                        "flexDirection": "column",
                        "gap":       "12px",
                    },
                    children=[

                        # Panel: DETALLE DEL CRT
                        html.Div(
                            style=_CARD,
                            children=[
                                html.P("Detalle del CRT", style=_SECTION_LABEL),
                                html.Div(
                                    id="panel-resumen",
                                    children=_render_empty_detail(),
                                ),
                            ],
                        ),

                        # Panel: CRTs EN PROCESO (kanban)
                        html.Div(
                            style={**_CARD, "flex": "1"},
                            children=[
                                html.P("CRTs en proceso", style=_SECTION_LABEL),
                                html.Div(
                                    id="sidebar-kanban",
                                    style={"maxHeight": "40vh", "overflowY": "auto"},
                                    children=_render_kanban_children({}, None),
                                ),
                                html.Hr(style={"borderColor": COLORS["border"],
                                               "margin": "10px 0"}),
                                dbc.Button(
                                    "⬇ Descargar ZIP",
                                    id="btn-descargar-zip",
                                    size="sm",
                                    style={
                                        "width":           "100%",
                                        "borderRadius":    "8px",
                                        "marginBottom":    "6px",
                                        "border":          f"1px solid {COLORS['accent']}",
                                        "color":           COLORS["accent"],
                                        "backgroundColor": "transparent",
                                        "fontWeight":      "600",
                                    },
                                ),
                                dbc.Button(
                                    "🗑 Limpiar todo",
                                    id="btn-limpiar",
                                    size="sm",
                                    style={
                                        "width":           "100%",
                                        "borderRadius":    "8px",
                                        "border":          f"1px solid {COLORS['danger']}",
                                        "color":           COLORS["danger"],
                                        "backgroundColor": "transparent",
                                        "fontWeight":      "600",
                                    },
                                ),
                            ],
                        ),
                    ],
                ),

                # ── Columna derecha (70%) — Vista previa PDF ──────────────
                html.Div(
                    style={"flex": "1", "minWidth": 0},
                    children=html.Div(
                        style=_CARD,
                        children=[
                            html.P("Vista previa PDF", style=_SECTION_LABEL),
                            html.Div(
                                id="preview-area",
                                children=_render_empty_preview(),
                            ),
                        ],
                    ),
                ),
            ],
        ),
    ])


# ---------------------------------------------------------------------------
# Callback 1 — Reducer: upload + limpiar (único Output de store-crts)
# ---------------------------------------------------------------------------
@callback(
    Output("store-crts",      "data"),
    Output("alert-container", "children"),
    Input("upload-docs",      "contents"),
    Input("btn-limpiar",      "n_clicks"),
    State("upload-docs",      "filename"),
    State("store-crts",       "data"),
    prevent_initial_call=True,
)
def update_store(list_of_contents, _limpiar, list_of_names, store_data):
    from src.services.orchestrator import procesar_documentos

    if ctx.triggered_id == "btn-limpiar":
        return {"crts": {}, "next_numero": 5098}, []

    if not list_of_contents:
        raise PreventUpdate

    store_data = store_data or {"crts": {}, "next_numero": 5098}

    archivos = []
    for content, nombre in zip(list_of_contents, list_of_names):
        try:
            _, data = content.split(",", 1)
            archivos.append((nombre, base64.b64decode(data)))
        except Exception:
            continue

    store_nuevo, errores = procesar_documentos(store_data, archivos)

    alerts = []
    for err in errores:
        if err.startswith("DISCREPANCIA:"):
            msg = err[len("DISCREPANCIA:"):]
            alerts.append(dbc.Alert(
                [html.Strong("⚠ Discrepancia: "), msg],
                color="warning", dismissable=True,
                style={"fontSize": "13px"},
            ))
        else:
            alerts.append(dbc.Alert(
                [html.Strong("Aviso: "), err],
                color="danger", dismissable=True,
                style={"fontSize": "13px"},
            ))
    return store_nuevo, alerts


# ---------------------------------------------------------------------------
# Callback 2 — Re-render kanban cuando cambia store o selección
# ---------------------------------------------------------------------------
@callback(
    Output("sidebar-kanban",   "children"),
    Input("store-crts",        "data"),
    Input("store-selected-id", "data"),
)
def render_kanban(store_data, selected_id):
    crts = (store_data or {}).get("crts", {})
    return _render_kanban_children(crts, selected_id)


# ---------------------------------------------------------------------------
# Callback 3 — Seleccionar CRT → detalle + preview
# ---------------------------------------------------------------------------
@callback(
    Output("panel-resumen",    "children"),
    Output("preview-area",     "children"),
    Output("store-selected-id","data"),
    Input({"type": "select-crt", "index": ALL}, "n_clicks"),
    State("store-crts", "data"),
    prevent_initial_call=True,
)
def seleccionar_crt(n_clicks_list, store_data):
    if not any(n_clicks_list):
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate

    crt_id = triggered["index"]
    crts   = (store_data or {}).get("crts", {})
    crt    = crts.get(crt_id)
    if not crt:
        raise PreventUpdate

    detail  = _render_crt_detail(crt)
    preview = _render_empty_preview()

    if crt.get("form_data"):
        try:
            pdf_bytes, is_fallback = generate_crt_pdf(crt["form_data"])
            if pdf_bytes:
                b64     = base64.b64encode(pdf_bytes).decode()
                pdf_src = (
                    f"data:application/pdf;base64,{b64}"
                    "#toolbar=0&navpanes=0&scrollbar=0&view=FitH"
                )
                preview_children = [_render_pdf_iframe(pdf_src)]
                if is_fallback:
                    preview_children.insert(0, dbc.Alert(
                        "⚠️ Vista previa generada con motor de respaldo (ReportLab). "
                        "Coordenadas aproximadas — no apto para Aduana.",
                        color="warning",
                        style={"fontSize": "12px", "marginBottom": "6px", "padding": "8px 12px"},
                        dismissable=True,
                    ))
                preview = html.Div(preview_children)
        except Exception:
            pass

    return detail, preview, crt_id


# ---------------------------------------------------------------------------
# Callback 4 — Descargar CRT individual
# Si is_fallback: guarda PDF en store-pdf-pending y abre modal de advertencia
# Si no: descarga directamente y loguea en audit log
# ---------------------------------------------------------------------------
@callback(
    Output("download-crt",        "data"),
    Output("modal-fallback-pdf",  "is_open"),
    Output("store-pdf-pending",   "data"),
    Input("btn-descargar-crt",    "n_clicks"),
    State("store-selected-id",    "data"),
    State("store-crts",           "data"),
    prevent_initial_call=True,
)
def descargar_crt(n_clicks, selected_id, store_data):
    if not selected_id:
        raise PreventUpdate
    crts = (store_data or {}).get("crts", {})
    crt  = crts.get(selected_id)
    if not crt or not crt.get("form_data"):
        raise PreventUpdate
    pdf_bytes, is_fallback = generate_crt_pdf(crt["form_data"])
    if not pdf_bytes:
        raise PreventUpdate
    correlativo = (crt.get("correlativo") or "borrador").replace("/", "-")
    sufijo      = "" if crt["estado"] == "COMPLETO" else "_borrador"
    filename    = f"CRT_{correlativo}{sufijo}.pdf"

    if is_fallback:
        # Guardar en store pendiente y mostrar modal — no descargar todavía
        pending = {
            "pdf_b64":  base64.b64encode(pdf_bytes).decode(),
            "filename": filename,
        }
        return None, True, pending

    # Descarga directa + audit log
    log_descarga(
        crt_id=selected_id,
        correlativo=crt.get("correlativo"),
        estado=crt["estado"],
        form_data_final=crt.get("form_data") or {},
        guia_datos=crt.get("guia_datos"),
        factura_datos=crt.get("factura_datos"),
        is_fallback=False,
    )
    return dcc.send_bytes(pdf_bytes, filename), False, None


# ---------------------------------------------------------------------------
# Callback 4b — Confirmar descarga fallback desde modal
# ---------------------------------------------------------------------------
@callback(
    Output("download-crt",       "data",    allow_duplicate=True),
    Output("modal-fallback-pdf", "is_open", allow_duplicate=True),
    Input("btn-modal-confirmar-fallback", "n_clicks"),
    State("store-pdf-pending",   "data"),
    State("store-selected-id",   "data"),
    State("store-crts",          "data"),
    prevent_initial_call=True,
)
def confirmar_descarga_fallback(n_clicks, pending, selected_id, store_data):
    if not pending or not pending.get("pdf_b64"):
        raise PreventUpdate
    pdf_bytes = base64.b64decode(pending["pdf_b64"])
    filename  = pending.get("filename", "CRT_borrador.pdf")

    # Audit log con is_fallback=True
    crts = (store_data or {}).get("crts", {})
    crt  = crts.get(selected_id) if selected_id else None
    if crt:
        log_descarga(
            crt_id=selected_id,
            correlativo=crt.get("correlativo"),
            estado=crt["estado"],
            form_data_final=crt.get("form_data") or {},
            guia_datos=crt.get("guia_datos"),
            factura_datos=crt.get("factura_datos"),
            is_fallback=True,
        )
    return dcc.send_bytes(pdf_bytes, filename), False


# ---------------------------------------------------------------------------
# Callback 4c — Cancelar modal fallback
# ---------------------------------------------------------------------------
@callback(
    Output("modal-fallback-pdf", "is_open", allow_duplicate=True),
    Input("btn-modal-cancelar-fallback", "n_clicks"),
    prevent_initial_call=True,
)
def cancelar_modal_fallback(_):
    return False


# ---------------------------------------------------------------------------
# Callback 5 — Descargar ZIP con todos los CRTs completos
# ---------------------------------------------------------------------------
@callback(
    Output("download-zip", "data"),
    Input("btn-descargar-zip", "n_clicks"),
    State("store-crts", "data"),
    prevent_initial_call=True,
)
def descargar_zip(n_clicks, store_data):
    crts  = (store_data or {}).get("crts", {})
    buf   = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for crt in crts.values():
            if crt["estado"] != "COMPLETO" or not crt.get("form_data"):
                continue
            try:
                pdf_bytes, _ = generate_crt_pdf(crt["form_data"])
                if pdf_bytes:
                    fname = f"CRT_{(crt.get('correlativo') or 'sin_numero').replace('/', '-')}.pdf"
                    zf.writestr(fname, pdf_bytes)
                    count += 1
            except Exception:
                pass
    if count == 0:
        raise PreventUpdate
    buf.seek(0)
    return dcc.send_bytes(buf.read(), "CRTs_Vesprini.zip")


# ---------------------------------------------------------------------------
# Callback 6 — Limpiar workspace (UI secundario)
# ---------------------------------------------------------------------------
@callback(
    Output("store-selected-id", "data",     allow_duplicate=True),
    Output("preview-area",      "children", allow_duplicate=True),
    Output("panel-resumen",     "children", allow_duplicate=True),
    Input("btn-limpiar", "n_clicks"),
    prevent_initial_call=True,
)
def limpiar_ui(_):
    return None, _render_empty_preview(), _render_empty_detail()


# ---------------------------------------------------------------------------
# Callback 7 — Confirmar sugerencia AMBIGUO → COMPLETO
# ---------------------------------------------------------------------------
@callback(
    Output("store-crts",        "data",     allow_duplicate=True),
    Output("store-selected-id", "data",     allow_duplicate=True),
    Input({"type": "btn-confirmar-sugerencia", "index": ALL}, "n_clicks"),
    State("store-crts",         "data"),
    State("store-selected-id",  "data"),
    prevent_initial_call=True,
)
def confirmar_sugerencia(n_clicks_list, store_data, selected_id):
    from src.services.orchestrator import (
        construir_form_data, recalcular_fletes, ESTADO_COMPLETO, ESTADO_AMBIGUO
    )
    from modulos.generador_glosas import generar_textos_crt

    if not any(n_clicks_list):
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate

    # Parsear crt_id e idx del index compuesto "crt_id__idx"
    raw_index = triggered["index"]
    if "__" not in raw_index:
        raise PreventUpdate
    crt_id, idx_str = raw_index.rsplit("__", 1)
    try:
        idx = int(idx_str)
    except ValueError:
        raise PreventUpdate

    store_data = store_data or {"crts": {}, "next_numero": 5098}
    crts       = store_data.get("crts", {})
    crt        = crts.get(crt_id)
    if not crt or crt.get("estado") != ESTADO_AMBIGUO:
        raise PreventUpdate

    sugerencias = crt.get("sugerencias") or []
    if idx >= len(sugerencias):
        raise PreventUpdate

    sug      = sugerencias[idx]
    tipo     = sug.get("tipo")
    datos    = sug.get("datos") or {}
    nombre_a = sug.get("nombre_archivo")

    # Merge: la sugerencia completa el documento que faltaba
    if tipo == "factura":
        crt["factura_datos"]  = datos
        crt["nombre_factura"] = nombre_a
        pais = datos.get("pais_destino", "USA")
    elif tipo == "guia":
        crt["guia_datos"]  = datos
        crt["nombre_guia"] = nombre_a
        pais = (crt.get("factura_datos") or {}).get("pais_destino", "USA")
    else:
        raise PreventUpdate

    config  = crt.get("config") or {}
    next_num = store_data.get("next_numero", 5000)
    tx = generar_textos_crt(
        pais_destino=pais,
        numero_base=next_num,
        paso_frontera=config.get("paso_frontera", "MONTE AYMOND"),
        aeropuerto=config.get("aeropuerto", "MINISTRO PISTARINI"),
    )
    crt["textos"]      = tx
    crt["correlativo"] = tx.get("correlativo_casilla_2")
    crt["estado"]      = ESTADO_COMPLETO
    crt["sugerencias"] = []
    crts[crt_id]       = crt

    # Recalcular fletes para todos los CRTs del camión antes de generar form_data
    crts = recalcular_fletes(crts)
    crt["form_data"]   = construir_form_data(crts[crt_id])

    store_data["crts"]        = crts
    store_data["next_numero"] = next_num + 1
    return store_data, crt_id


# ---------------------------------------------------------------------------
# Callback 8 — Descartar sugerencias AMBIGUO → vuelve a FALTA_*
# ---------------------------------------------------------------------------
@callback(
    Output("store-crts", "data", allow_duplicate=True),
    Input({"type": "btn-descartar-sugerencias", "index": ALL}, "n_clicks"),
    State("store-crts",  "data"),
    prevent_initial_call=True,
)
def descartar_sugerencias(n_clicks_list, store_data):
    from src.services.orchestrator import ESTADO_FALTA_FACTURA, ESTADO_FALTA_GUIA

    if not any(n_clicks_list):
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate

    crt_id     = triggered["index"]
    store_data = store_data or {"crts": {}, "next_numero": 5098}
    crts       = store_data.get("crts", {})
    crt        = crts.get(crt_id)
    if not crt:
        raise PreventUpdate

    # Determinar a qué estado volver según qué documento ya tiene
    if crt.get("guia_datos") and not crt.get("factura_datos"):
        crt["estado"] = ESTADO_FALTA_FACTURA
    else:
        crt["estado"] = ESTADO_FALTA_GUIA

    crt["sugerencias"] = []
    crts[crt_id]       = crt
    store_data["crts"] = crts
    return store_data
