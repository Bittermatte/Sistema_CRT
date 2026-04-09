# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (entry point activo)
python3 app_dash.py          # Dash, puerto 8051

# Run legacy Streamlit (solo referencia)
streamlit run app.py

# Install dependencies
python3 -m pip install -r requirements.txt
# Dependencias clave: pdfplumber, openpyxl, dash, dash-bootstrap-components,
#                     reportlab, pypdfium2, pillow

# Diagnóstico de extracción (reemplazar con ruta real)
python3 -c "from modulos.extractor_guias import extraer_datos_guia; import pprint; pprint.pprint(extraer_datos_guia('ruta/guia.pdf'))"
python3 -c "from modulos.extractor_facturas import extraer_datos_factura; import pprint; pprint.pprint(extraer_datos_factura('ruta/factura.pdf'))"

# Run tests
pytest
pytest tests/test_pdf_service.py -v
pytest --cov=src tests/
```

---

## Estado actual del proyecto (2026-04-08)

### Entry point activo

`app_dash.py` — Dash app, puerto 8051. `app.py` (Streamlit) conservado solo como referencia.

### Flujo principal

```
Usuario sube PDF/Excel
  → clasificar_documento()              # por extensión (.xlsx → factura) o contenido (PDF)
  → extraer_documento()                 # llama extractor guía o factura
  → agrupar_documentos()                # motor_agrupacion: agrupa por pesquera/destinatario
  → consolidar_productos_australis()    # Australis: consolida líneas idénticas de factura
  → matching contra store               # 4 capas de matching
  → construir_form_data()               # genera dict f_* por pesquera (casilla 11, 9, etc.)
  → generate_crt_pdf()                  # PDF vía Excel+LibreOffice o ReportLab fallback
  → kanban + vista previa               # visible inmediatamente
```

### Matching — 4 capas (orden de prioridad)

| Capa | Criterio | Confianza |
|------|----------|-----------|
| 0 | `orden_venta (guía)` == `ref_pedido (factura)` — referencia cruzada específica por pesquera | Máxima |
| 1 | `cert_sanitario` exacto en ambos documentos | Alta |
| 2 | `destinatario` por similitud de texto (≥ 0.50) | Media |
| 3 | Misma pesquera + único candidato en espera | Baja (fallback) |

---

## Mapa de archivos — estado de cada módulo

### Activos y canónicos

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `app_dash.py` | ✅ activo | Entry point Dash |
| `src/dash_ui/pages/elaborar_crt.py` | ✅ activo | UI principal: upload (PDF+Excel), kanban, detalle, preview, descarga |
| `src/dash_ui/theme.py` | ✅ activo | COLORS, CARD_STYLE |
| `src/dash_ui/layout.py` | ✅ activo | Layout base con navbar y page content |
| `src/services/orchestrator.py` | ✅ activo | Coordinador central: clasifica → extrae → agrupa → matchea → genera form_data |
| `src/services/pdf_service.py` | ✅ activo | `generate_crt_pdf()`: usa Excel+LibreOffice si disponible, ReportLab como fallback |
| `src/services/excel_pdf_builder.py` | ✅ activo | Generador primario: llena plantilla Excel → LibreOffice → PDF |
| `src/services/pdf_builder.py` | ✅ activo | Generador fallback: ReportLab desde cero (sin LibreOffice) |
| `modulos/config_cliente.py` | ✅ activo | Configs de 6 pesqueras + `ALPHA_BROKERS` + detección automática |
| `modulos/extractor_guias.py` | ✅ activo | Extrae datos de guías de despacho PDF (incluye tabla de productos por pesquera) |
| `modulos/extractor_facturas.py` | ✅ activo | Extrae datos de facturas PDF y Excel (.xlsx); extrae productos para Australis |
| `modulos/motor_calculos.py` | ✅ activo | Prorrateo de fletes |
| `modulos/motor_agrupacion.py` | ✅ activo | Reglas de agrupación + `consolidar_productos_australis()` |
| `modulos/generador_glosas.py` | ✅ activo | Genera textos casillas 8 y 18 del CRT (usa paso_frontera y aeropuerto del config) |

### Legacy / referencia

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `app.py` | 🗄 legacy | Streamlit — no usar, conservar |
| `src/ui/` | 🗄 legacy | Frontend Streamlit completo |
| `modulos/creador_crt.py` | 🗄 referencia | Generador PDF legacy — fuente de coordenadas |

### Stubs Fase 2/3 (no implementados)

`src/services/db_service.py`, `src/services/customs_service.py`, `src/api/routes.py`,
`src/models/crt.py`, `src/dash_ui/pages/buscar.py`, `src/dash_ui/pages/historial.py`

---

## Módulos detallados

### `modulos/config_cliente.py`

6 pesqueras: `aquachile`, `blumar_magallanes`, `blumar`, `multix`, `australis`, `cermaq`.

Cada config tiene: `remitente`, `dir_remitente`, `transportista`, `dir_transportista`,
`lugar_emision`, `tarifa_flete`, `firma_remitente`, `paso_frontera`, `aeropuerto`,
`notificar` ("destinatario" | "alpha_brokers"), `descripcion_fuente` ("guia" | "factura").

`ALPHA_BROKERS` — constante con nombre, dirección y teléfono (usado en casilla 9 para Blumar, Cermaq, Multi X).

```python
from modulos.config_cliente import detectar_pesquera, get_config, get_config_desde_texto, ALPHA_BROKERS
clave, config = get_config_desde_texto(texto_pdf)
```

### `modulos/extractor_guias.py`

Extrae de guías PDF: `numero_guia`, `orden_venta`, `peso_bruto`, `peso_neto`, `bultos`,
`patente_tracto`, `patente_semi`, `conductor`, `cert_sanitario`, `destinatario`, `pesquera`,
`fecha`, `productos`.

`productos` — lista de dicts `{descripcion, familia, cajas_totales, kilos_totales}`.

Parsers de tabla por pesquera:
- **AquaChile / Multi X**: `_parsear_tabla_productos()` — columnas `CODIGO|PRODUCTOS|KILOS|CAJAS`
- **Blumar / Blumar Magallanes**: `_parsear_tabla_blumar()` — columnas `CANTIDAD|DETALLE`
- **Cermaq**: parser estándar + `_limpiar_desc_cermaq()` (strip `[Salmo Salar]`, `58 Lbs`, `Poliestireno`, reorden)
- **Australis**: retorna `[]` — productos vienen de la factura

`orden_venta` usa patrón específico por pesquera (`PATRONES_ORDEN_VENTA_PESQUERA`):
- Multi X: `N° Pedido:`
- AquaChile: `PEDIDO EXPORTACION`
- Blumar: `PO:`
- Cermaq: `CO - CLIENTE:` (solo dígitos)
- Australis: fallback genérico

### `modulos/extractor_facturas.py`

Soporta **PDF y Excel (.xlsx)**. Detecta por extensión automáticamente.

Extrae: `numero_factura`, `ref_pedido`, `incoterm`, `moneda`, `total`, `destinatario`,
`direccion`, `pais_destino`, `cert_sanitario`, `pesquera`, `fecha`, `productos`.

`productos` — solo para Australis: lista de dicts `{descripcion, familia, cajas_totales, kilos_totales}` en inglés.

`ref_pedido` usa patrón específico por pesquera (`PATRONES_REF_PEDIDO_PESQUERA`):
- Multi X: `PV:`
- AquaChile: `N° PEDIDO / ORDER`
- Blumar: `SELLER'S REFERENCE No.`
- Cermaq: `Order Ref`

### `src/services/orchestrator.py`

Funciones clave:
- `procesar_documentos(store_actual, archivos)` — punto de entrada único (3 fases)
- `clasificar_documento(file_bytes, nombre)` — soporta PDF y Excel
- `detectar_discrepancias(guia_datos, factura_datos)` — compara bultos, peso bruto, peso neto
- `construir_form_data(crt)` — genera dict `f_*` para el PDF con lógica por pesquera
- `_construir_lineas_casilla11(pesquera, guia, factura)` — descripción de carga por pesquera
- `recalcular_fletes(crts)` — prorrata por peso; aplica tarifa especial MARDI/AGROCOMERCIAL

Discrepancias se prefijan con `"DISCREPANCIA:"` para que el callback las coloree en naranja.

`construir_form_data` genera los campos `f_descripcion_1..5` y `f_kilos_netos_1..5` según pesquera:
- **AquaChile**: 1 línea por producto + `CON: X KG NETOS` separado
- **Blumar/Blumar Magallanes**: 1 línea consolidada, sin talla, punto final
- **Cermaq**: 1 línea consolidada limpia
- **Multi X**: 1 línea por categoría, kilos inline
- **Australis**: desde factura en inglés, kilos inline

Casilla 9 (notificar): si `config["notificar"] == "alpha_brokers"` usa `ALPHA_BROKERS`; si `"destinatario"` copia al destinatario.

### `src/dash_ui/pages/elaborar_crt.py`

- Upload acepta `.pdf,.xlsx,.xls`
- CRTs incompletos (FALTA_FACTURA / FALTA_GUIA) muestran borrador PDF inmediatamente
- Botón descarga: "Descargar borrador" (naranja) para incompletos, "Descargar CRT" (azul) para completos
- Alertas: naranja = discrepancia logística, rojo = error de procesamiento
- `dcc.Store` usa `storage_type="session"` — persiste durante la sesión del browser

### `src/services/excel_pdf_builder.py` (generador primario)

Llena `plantillas/crt_plantilla.xlsx` y convierte con LibreOffice headless.
Requiere LibreOffice instalado: `brew install --cask libreoffice`

Celdas clave del template:
- `A13-A15`: remitente + dirección
- `F16-F18`: transportista + dirección
- `A28-A29`: notificar (Alpha Brokers o destinatario)
- `A35-A39`: descripciones de producto (hasta 5 líneas dinámicas)
- `A40-A42`: totales cajas/kilos
- `A60`: firma remitente por pesquera
- `B47/B48/B52`: fletes origen, frontera, total

### `modulos/motor_agrupacion.py`

`CLIENTES_AGRUPAN` — destinatarios que consolidan múltiples GDs en un solo CRT:
- AquaChile: `AQUACHILE INC`
- Blumar/Blumar Magallanes: `BLUGLACIER`
- Multi X: `MULTI X INC`
- Australis: `TRAPANANDA SEAFARMS`, `COSTCO`, `PESCADERIA ATLANTICA`
- Cermaq: `CERMAQ US LLC`

`CLIENTES_NUNCA_AGRUPAN`: AquaChile + `AGROSUPER` → siempre 1 GD = 1 CRT.

`consolidar_productos_australis(grupos)` — consolida líneas de producto idénticas de múltiples facturas Australis. Se llama automáticamente en `procesar_documentos()`.

### `modulos/generador_glosas.py`

```python
generar_textos_crt(pais_destino, numero_base, paso_frontera, aeropuerto)
```
Los parámetros `paso_frontera` y `aeropuerto` vienen del config de la pesquera.
El orquestador los pasa automáticamente desde `config_pesquera`.

---

## Reglas de negocio

- **Prorrateo flete (Casilla 15)**: `flete_usd = (peso_bruto_CRT / peso_bruto_camión) × tarifa`
  - Tarifa por defecto: 4,400 USD por camión (configurable por pesquera en `config_cliente.py`)
  - Desglose: 8% origen→frontera, 92% frontera→destino
- **Destinatarios especiales** (en `recalcular_fletes`): `MARDI` y `AGRO COMERCIAL DEL CARMEN`
  usan tarifa fija 4,250 USD en vez de 4,400 USD
- **Correlativo CRT**: `{numero_base}/{año}VSP` — generado por `generador_glosas.py`
- **Valor mercadería**: solo se usa el de la factura — nunca el de la guía
- **Formato numérico**: siempre español (punto miles, coma decimal) — función `_fmt_es()`

---

## Pendientes en orden de prioridad

### P1 — Validación (necesario antes de producción con todas las pesqueras)

1. **Probar extractores con PDFs reales de cada pesquera**
   - Guías Blumar (CANTIDAD|DETALLE), Cermaq, Australis
   - Facturas Excel de Blumar y Cermaq
   - Comando: `python3 -c "from modulos.extractor_guias import extraer_datos_guia; import pprint; pprint.pprint(extraer_datos_guia('ruta/archivo.pdf'))"`

### P2 — Robustez

2. **Tests unitarios para extractores y orquestador**
   - No existen tests para `extractor_guias`, `extractor_facturas`, `orchestrator`
   - Mínimo: test con documentos reales de cada pesquera

3. **Manejo de múltiples guías con mismo `orden_venta`**
   - Capa 0 retorna el primero que matchea — si hay 2 guías con mismo PO, solo empareja la primera

### P3 — Fase 2 (base de datos)

4. **Persistencia en base de datos**
   - Stubs listos en `src/services/db_service.py` y `src/models/crt.py`
   - Requiere PostgreSQL + SQLAlchemy
