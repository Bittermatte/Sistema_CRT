# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
streamlit run app.py

# Install dependencies
python3 -m pip install -r requirements.txt

# Run tests
pytest

# Run a single test file
pytest tests/test_pdf_service.py -v

# Run with coverage
pytest --cov=src tests/
```

## Architecture

**Sistema CRT** is a Streamlit web app for generating *Cartas de Porte Internacional* (CRT) — international road freight documents under the ALADI standard. The app follows a 3-phase roadmap; only Phase 1 is implemented.

### Request/render flow

Every widget interaction triggers a Streamlit rerun. `app.py` reads `st.session_state["current_page"]` and dispatches to the matching page function. On the `elaborar_crt` page, `render_pdf_with_overlay(dict(st.session_state))` is called on every rerun: it takes the cached base PNG of `plantillas/crt_blanco.pdf` and uses Pillow to draw the current form values at calibrated pixel coordinates, returning a fresh PNG for `st.image()`.

### Key files

| File | Role |
|------|------|
| `app.py` | Entry point: page config, session state init, navbar, page dispatch |
| `src/ui/navbar.py` | Top navbar with brand + 4 nav buttons via `st.columns` |
| `src/ui/styles.py` | All CSS injected via `st.markdown(unsafe_allow_html=True)` — Apple-style theme |
| `src/ui/pages/elaborar_crt.py` | Main Phase 1 page: file upload zone, 24-field form (6 expanders), live PDF preview |
| `src/services/pdf_service.py` | PDF rendering engine — the most critical file |
| `src/models/crt.py` | Pydantic v2 `CRTDocument` with all 24 ALADI casillas |
| `src/utils/constants.py` | `INCOTERM_OPTIONS`, `EMBALAJE_TYPES`, `COUNTRIES` |

### PDF overlay system (`pdf_service.py`)

- `_render_base_png()` — renders `plantillas/crt_blanco.pdf` as PNG bytes using `pypdfium2` at `RENDER_SCALE = 2.0` (612×1008 pts → 1224×2016 px). Cached with `@st.cache_data`.
- `render_pdf_with_overlay(form_data)` — not cached; opens the base PNG, white-fills `_ALWAYS_CLEAR` zones (template sample data), then iterates `OVERLAY_MAP` to clear and draw each field.
- `OVERLAY_MAP` — list of dicts mapping `f_*` session state keys to `(tx, ty)` coordinates in **PDF points** (multiplied by `RENDER_SCALE` internally). Changing coordinates here repositions text on the rendered preview.
- Casilla 5 special logic: `f_lugar_emision` and `f_fecha_emision` are combined into one line since the cell is only ~18 pts tall.

### Session state conventions

- All form fields use keys prefixed `f_` (e.g. `f_remitente`, `f_numero_crt`).
- Page routing uses `st.session_state["current_page"]` with values matching `PAGE_MAP` keys in `app.py`.
- `_limpiar_formulario()` deletes all `f_*` keys to reset the form.

### Phase roadmap

- **Phase 1** (current): form UI + live PDF preview + PDF generation
- **Phase 2**: PostgreSQL/SQLAlchemy persistence, MIC customs integration, document history
- **Phase 3**: FastAPI REST layer for a mobile app

Stub files exist for Phase 2–3 features: `src/services/db_service.py`, `src/services/customs_service.py`, `src/api/routes.py`, and stub pages `buscar`, `historial`, `modificar`, `mic_aduana`, `configuracion`.

## Estado de la Transición

- `app_dash.py` → entry point activo (Dash, puerto 8051)
- `app.py` → legacy Streamlit, conservado como referencia durante transición
- `src/ui/` → código Streamlit legacy, no activo
- `src/dash_ui/` → frontend activo
- `modulos/creador_crt.py` → generador PDF legacy (referencia de coordenadas)
- `src/services/pdf_service.py` → generador PDF canónico activo
- `src/models/crt.py` → reservado para Fase 2 (validación con BD)
- `src/services/db_service.py`, `customs_service.py`, `src/api/routes.py` → stubs Fase 2/3

### Business rules (Phase 1 scope)

- **Freight proration (Casilla 15)**: `flete_usd = (peso_bruto_CRT × tarifa) / peso_bruto_camión`. Tariffs: Puerto Natales 4,400 USD | Punta Arenas 4,250 USD.
- **Special destinatario overrides**: `MARDI S.A.` and `AGRO COMERCIAL DEL CARMEN S.A.` use fixed rate 4,250 USD (split: 340 USD origin/border + 3,910 USD border/destination).
