"""
Página principal — Elaborar CRT
Upload → clasificación → extracción → matching → kanban → vista detalle → PDF
"""

import base64
import difflib
import io
import os
import re
import tempfile
import uuid
import zipfile

from dash import html, dcc, callback, Input, Output, State, ctx, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_iconify as di

from src.dash_ui.theme import COLORS, CARD_STYLE
from src.services.pdf_service import generate_crt_pdf
from modulos.extractor_guias import extraer_datos_guia
from modulos.extractor_facturas import extraer_datos_factura
from modulos.motor_calculos import calcular_fletes
from modulos.generador_glosas import generar_textos_crt
from modulos.config_cliente import CONFIG_ACTIVO

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


def _detect_pais(direccion: str | None) -> str:
    if not direccion:
        return "MEXICO"
    d = direccion.upper()
    for key, val in {
        "CHINA": "CHINA", "MEXICO": "MEXICO",
        "ESTADOS UNIDOS": "USA", " USA": "USA",
        "BRASIL": "BRASIL", "COLOMBIA": "COLOMBIA",
        "JAPON": "JAPON", "COREA": "COREA",
        "PERU": "PERU",
    }.items():
        if key in d:
            return val
    return "MEXICO"


# ---------------------------------------------------------------------------
# Helpers — clasificación y extracción
# ---------------------------------------------------------------------------
def _classify_pdf(pdf_bytes: bytes) -> str | None:
    """Retorna 'guia', 'factura', o None si el PDF no es legible."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages[:2])
        if not text.strip():
            return None
        if re.search(r"GUIA\s+DE\s+DESPACHO|GU[IÍ]A\s+ELECTR[OÓ]NICA", text, re.IGNORECASE):
            return "guia"
        return "factura"
    except Exception:
        return None


def _extract_pdf(pdf_bytes: bytes, tipo: str) -> dict:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(pdf_bytes)
            tmp_path = f.name
        if tipo == "guia":
            return extraer_datos_guia(tmp_path)
        else:
            return extraer_datos_factura(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Helpers — lógica de CRTs
# ---------------------------------------------------------------------------
def _find_matching_crt(crts: dict, nombre: str, buscando_tipo: str) -> str | None:
    """Busca el CRT incompleto cuyo documento existente sea más similar (difflib ≥ 0.50)."""
    estado_necesario = "FALTA_GUIA" if buscando_tipo == "guia" else "FALTA_FACTURA"
    nombre_clean = nombre.lower().replace(".pdf", "")
    best_ratio, best_id = 0.0, None
    for crt_id, crt in crts.items():
        if crt["estado"] != estado_necesario:
            continue
        existing = (
            crt.get("nombre_guia") or crt.get("nombre_factura") or ""
        ).lower().replace(".pdf", "")
        ratio = difflib.SequenceMatcher(None, nombre_clean, existing).ratio()
        if ratio >= 0.50 and ratio > best_ratio:
            best_ratio, best_id = ratio, crt_id
    return best_id


def _build_form_data(crt: dict) -> dict:
    # IMPORTANTE: las fechas deben entrar como strings "YYYY-MM-DD", nunca como datetime.date
    # El dcc.Store serializa a JSON y datetime.date no es serializable
    g  = crt.get("guia_datos")    or {}
    f  = crt.get("factura_datos") or {}
    fl = crt.get("fletes")        or {}
    tx = crt.get("textos")        or {}

    productos = g.get("productos") or []
    desc1 = kilos1 = desc2 = kilos2 = ""
    if len(productos) > 0:
        p = productos[0]
        desc1  = f"{p['cajas_totales']} CAJAS CON SALMON DEL ATLANTICO {p['familia']}"
        kilos1 = _fmt_cl(p["kilos_totales"])
    if len(productos) > 1:
        p = productos[1]
        desc2  = f"{p['cajas_totales']} CAJAS CON SALMON DEL ATLANTICO {p['familia']}"
        kilos2 = _fmt_cl(p["kilos_totales"])

    def _s(v) -> str:
        return str(v) if v is not None and v != "" else ""

    return {
        "f_numero_crt":           crt.get("correlativo", ""),
        "f_remitente":            CONFIG_ACTIVO["remitente"],
        "f_dir_remitente":        "CAMINO LOS PINOS S/N\nPUERTO MONTT - CHILE",
        "f_transportista":        CONFIG_ACTIVO["transportista"],
        "f_destinatario":         f.get("destinatario", ""),
        "f_dir_destinatario":     f.get("direccion", ""),
        "f_consignatario":        f.get("destinatario", ""),
        "f_dir_consignatario":    f.get("direccion", ""),
        "f_notificar":            f.get("destinatario", ""),
        "f_dir_notificar":        f.get("direccion", ""),
        "f_lugar_emision":        CONFIG_ACTIVO["lugar_emision"],
        "f_lugar_recepcion":      "PUERTO NATALES - CHILE",
        "f_lugar_entrega":        tx.get("texto_casilla_8", ""),
        "f_destino_final":        tx.get("texto_casilla_8", ""),
        "f_instrucciones_aduana": tx.get("texto_casilla_18", ""),
        "f_incoterm":             f.get("incoterm", ""),
        "f_valor_mercaderia":     f.get("total", ""),
        "f_flete_usd":            _s(fl.get("flete_prorrateado")),
        "f_flete_origen":         _s(fl.get("flete_origen_frontera")),
        "f_flete_frontera":       _s(fl.get("flete_frontera_destino")),
        "f_num_factura":          crt.get("nombre_factura", ""),
        "f_guias_despacho":       _s(g.get("numero_guia")),
        "f_peso_neto":            g.get("peso_neto"),
        "f_peso_bruto":           g.get("peso_bruto"),
        "f_total_cajas":          g.get("bultos"),
        "f_patente_camion":       g.get("patente_tracto", ""),
        "f_patente_rampla":       g.get("patente_semi", ""),
        "f_descripcion_1":        desc1,
        "f_kilos_netos_1":        kilos1,
        "f_descripcion_2":        desc2,
        "f_kilos_netos_2":        kilos2,
        "f_conductor":            "",
        "f_fecha_emision":        None,  # string "YYYY-MM-DD" cuando se implemente
        "f_fecha_documento":      None,
        "f_fecha_entrega":        None,
    }


def _recalculate_fletes(crts: dict, tarifa: float = CONFIG_ACTIVO["tarifa_flete"]) -> dict:
    """
    Agrupa CRTs completos por patente_tracto y prorratea el flete entre todos
    los que comparten camión, usando la suma de pesos como denominador.
    """
    groups: dict[str, list[str]] = {}
    for crt_id, crt in crts.items():
        if crt["estado"] != "COMPLETO" or not crt.get("guia_datos"):
            continue
        tracto = crt["guia_datos"].get("patente_tracto") or "SIN_PATENTE"
        groups.setdefault(tracto, []).append(crt_id)

    for tracto, ids in groups.items():
        total_pb = sum(
            float(crts[cid]["guia_datos"].get("peso_bruto") or 0)
            for cid in ids
        )
        if total_pb <= 0:
            continue
        for cid in ids:
            pb = float(crts[cid]["guia_datos"].get("peso_bruto") or 0)
            crts[cid]["fletes"]    = calcular_fletes(pb, total_pb, tarifa)
            crts[cid]["form_data"] = _build_form_data(crts[cid])

    return crts


# ---------------------------------------------------------------------------
# Helpers — UI / badges y kanban
# ---------------------------------------------------------------------------
def _badge(estado: str) -> html.Span:
    cfg = {
        "COMPLETO":      (COLORS["success"], "✅ COMPLETO"),
        "FALTA_FACTURA": (COLORS["warning"], "⚠️ FALTA FACTURA"),
        "FALTA_GUIA":    (COLORS["warning"], "⚠️ FALTA GUÍA"),
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
        dcc.Store(id="store-crts",        storage_type="memory",
                  data={"crts": {}, "next_numero": 5098}),
        dcc.Store(id="store-selected-id", storage_type="memory"),
        dcc.Download(id="download-crt"),
        dcc.Download(id="download-zip"),

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
            pdf_bytes = generate_crt_pdf(crt["form_data"])
            if pdf_bytes:
                b64     = base64.b64encode(pdf_bytes).decode()
                pdf_src = (
                    f"data:application/pdf;base64,{b64}"
                    "#toolbar=0&navpanes=0&scrollbar=0&view=FitH"
                )
                preview = _render_pdf_iframe(pdf_src)
        except Exception:
            pass

    return detail, preview, crt_id


# ---------------------------------------------------------------------------
# Callback 4 — Descargar CRT individual
# ---------------------------------------------------------------------------
@callback(
    Output("download-crt",  "data"),
    Input("btn-descargar-crt", "n_clicks"),
    State("store-selected-id", "data"),
    State("store-crts",        "data"),
    prevent_initial_call=True,
)
def descargar_crt(n_clicks, selected_id, store_data):
    if not selected_id:
        raise PreventUpdate
    crts = (store_data or {}).get("crts", {})
    crt  = crts.get(selected_id)
    if not crt or not crt.get("form_data"):
        raise PreventUpdate
    pdf_bytes = generate_crt_pdf(crt["form_data"])
    if not pdf_bytes:
        raise PreventUpdate
    correlativo = (crt.get("correlativo") or "borrador").replace("/", "-")
    sufijo = "" if crt["estado"] == "COMPLETO" else "_borrador"
    return dcc.send_bytes(pdf_bytes, f"CRT_{correlativo}{sufijo}.pdf")


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
                pdf_bytes = generate_crt_pdf(crt["form_data"])
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
