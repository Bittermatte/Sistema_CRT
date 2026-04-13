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

## Estado actual del proyecto (2026-04-13)

### Etapa 1 — COMPLETA (branch: claude/add-ambiguous-state-kanban-G6LbR)

Todos los cambios de estabilización están implementados y pusheados. Ver sección "Pendientes" para Etapa 2.

### Entry point activo

`app_dash.py` — Dash app, puerto 8051. `app.py` (Streamlit) conservado solo como referencia.

### Flujo principal

```
Usuario sube PDF/Excel
  → clasificar_documento()              # por extensión (.xlsx → factura) o contenido (PDF)
  → extraer_documento()                 # llama extractor guía o factura
  → log_extraccion()                    # audit_log.py: JSONL append-only en logs/
  → agrupar_documentos()                # motor_agrupacion: agrupa por pesquera/destinatario
  → consolidar_productos_australis()    # Australis: consolida líneas idénticas de factura
  → matching contra store               # 4 capas de matching
  → construir_form_data()               # genera dict f_* por pesquera (casilla 11, 9, etc.)
  → generate_crt_pdf()                  # PDF: overlay+merge → LibreOffice → ReportLab fallback
  → kanban + vista previa               # visible inmediatamente
```

### Matching — 4 capas (orden de prioridad)

| Capa | Criterio | Confianza |
|------|----------|-----------|
| 0 | `orden_venta (guía)` == `ref_pedido (factura)` — referencia cruzada específica por pesquera | Máxima |
| 1 | `cert_sanitario` exacto en ambos documentos | Alta |
| 2 | `destinatario` por similitud de texto (≥ **0.80**, era 0.50) | Media |
| 3 | Misma pesquera → marca estado **AMBIGUO** (NO auto-matchea) | Requiere confirmación humana |

### Estados del CRT en el Kanban

| Estado | Badge | Descripción |
|--------|-------|-------------|
| `FALTA_FACTURA` | naranja | Solo guía subida, esperando factura |
| `FALTA_GUIA` | naranja | Solo factura subida, esperando guía |
| `AMBIGUO` | ámbar | Capa 3 encontró candidatos — requiere confirmación manual |
| `COMPLETO` | verde | Ambos documentos matcheados con confianza |
| `ERROR` | rojo | Extracción fallida |

### Generación PDF — orden de intentos en `generate_crt_pdf()`

1. **Overlay + merge** (`_build_overlay()` + pypdf + `crt_blanco.pdf`) — sin LibreOffice, `is_fallback=False`
2. **Excel + LibreOffice** (`excel_pdf_builder.py`) — si LibreOffice instalado, `is_fallback=False`
3. **ReportLab desde cero** (`pdf_builder.py`) — fallback con marca de agua "BORRADOR NO OFICIAL", `is_fallback=True`

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
| `src/services/pdf_service.py` | ✅ activo | `generate_crt_pdf()` → tupla `(bytes, is_fallback)`. Camino 1: overlay+merge; Camino 2: LibreOffice; Camino 3: ReportLab fallback |
| `src/services/audit_log.py` | ✅ activo | Audit log JSONL append-only (`logs/audit_YYYY-MM-DD.jsonl`). Eventos: `documento_extraido`, `crt_descargado` con diff |
| `src/services/excel_pdf_builder.py` | ✅ activo | Generador secundario: llena plantilla Excel → LibreOffice → PDF |
| `src/services/pdf_builder.py` | ✅ activo | Generador fallback (Camino 3): ReportLab desde cero, con marca de agua BORRADOR NO OFICIAL |
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

### `src/services/audit_log.py`

Audit log legal. Escribe en `logs/audit_YYYY-MM-DD.jsonl` (JSONL append-only, un evento por línea).

- `log_extraccion(nombre_archivo, tipo, pesquera, datos_extraidos)` — llamado tras cada `extraer_documento()`
- `log_descarga(crt_id, correlativo, estado, form_data_final, guia_datos, factura_datos, is_fallback)` — llamado en callback `descargar_crt`. Incluye **diff** entre datos extraídos y datos finales del PDF (prueba legal de edición manual).

### `src/services/pdf_service.py`

- `_build_overlay(form)` — genera capa ReportLab transparente con todos los campos f_* posicionados sobre `crt_blanco.pdf`. Soporta `f_descripcion_1..5`, `f_kilos_netos_1..5`, `f_firma_remitente`.
- `_generate_via_overlay(form_data)` — fusiona overlay con template via pypdf. Camino primario.
- `generate_crt_pdf(form_data)` → `tuple[bytes|None, bool]` — retorna `(pdf_bytes, is_fallback)`.
- `render_pdf_preview(form_data)` — deprecated (Streamlit). El frontend Dash usa `generate_crt_pdf()` + iframe base64.

### `src/dash_ui/pages/elaborar_crt.py`

- Upload acepta `.pdf,.xlsx,.xls`
- Estados FALTA_FACTURA/FALTA_GUIA muestran borrador PDF inmediatamente
- Estado **AMBIGUO**: panel con sugerencias, botones "Confirmar" y "Descartar"
- Si `is_fallback=True`: badge naranja en preview + modal de advertencia antes de descarga
- Audit log: `log_descarga()` se llama en `descargar_crt` y `confirmar_descarga_fallback`
- `dcc.Store` usa `storage_type="session"` — persiste durante la sesión del browser

### `src/services/excel_pdf_builder.py` (generador secundario)

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

### ✅ Etapa 1 — COMPLETADA (2026-04-13)

- MATCH_THRESHOLD 0.50 → 0.80
- Audit log JSONL (`audit_log.py`) con diff legal
- Estado AMBIGUO + Capa 3 sin auto-match
- UI AMBIGUO: panel sugerencias, confirmar/descartar
- `generate_crt_pdf()` retorna tupla `(bytes, is_fallback)`
- Modal advertencia + marca de agua para fallback PDF
- Overlay+merge como camino primario (sin LibreOffice)
- `recalcular_fletes()` en callback confirmar_sugerencia

### P1 — Validación real con documentos (antes de producción)

1. **Probar overlay con PDFs reales de cada pesquera**
   - Verificar coordenadas de `_build_overlay()` contra documentos reales
   - Si hay desajustes: ajustar coordenadas en `pdf_service.py`
   - Comando diagnóstico: `python3 -c "from src.services.pdf_service import _generate_via_overlay, _build_overlay; open('/tmp/test.pdf','wb').write(_generate_via_overlay({'f_remitente':'TEST',...}))"`

2. **Probar extractores con PDFs reales de cada pesquera**
   - Guías Blumar (CANTIDAD|DETALLE), Cermaq, Australis
   - Facturas Excel de Blumar y Cermaq
   - Comando: `python3 -c "from modulos.extractor_guias import extraer_datos_guia; import pprint; pprint.pprint(extraer_datos_guia('ruta/archivo.pdf'))"`

### P2 — Etapa 2: Infraestructura producción

3. **HTTPS + Nginx + dominio** — requisito legal antes de manejar datos de clientes
4. **Autenticación** — Flask-Login o Dash-Auth; aislamiento por tenant (clave para SaaS)
5. **Persistencia PostgreSQL** — reemplazar `dcc.Store(session)` con DB; stubs en `db_service.py`
6. **Fleet DB** — tabla de patentes (307 tractores + 347 semis de Resolución 3811/2019); semáforo de vencimiento

### P3 — Etapa 3: SaaS

7. **RPA portal MIC** — Playwright para autocompletar formulario MIC con datos del CRT
8. **Tests de regresión** — pytest con fixtures de PDFs reales por pesquera
9. **Política de retención de logs** — cron para purgar `logs/` > 90 días

---

## Infraestructura / Despliegue

### Estrategia

- **Código fuente**: GitHub (repositorio privado) — fuente de verdad, nunca en el servidor
- **Servidor de producción**: AWS Lightsail (~$7 USD/mes) — donde corre la app Dash
- **Base de datos** (Fase 3): AWS RDS PostgreSQL — se agrega cuando se implemente `db_service.py`

### Flujo de deploy

```
Mac  →  git push  →  GitHub
                        ↓
              git pull en Lightsail/EC2
                        ↓
              systemctl restart sistema-crt
```

### Configuración del servidor (Ubuntu 22.04)

```bash
# Dependencias del sistema (libreoffice es opcional — el overlay+merge no lo requiere)
sudo apt update && sudo apt install -y python3-pip python3-venv git

# Clonar y preparar
git clone https://github.com/<usuario>/sistema-crt.git
cd sistema-crt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Servicio systemd (para que arranque automáticamente)
# /etc/systemd/system/sistema-crt.service
# → ExecStart: /home/ubuntu/sistema-crt/venv/bin/python3 app_dash.py
sudo systemctl enable sistema-crt
sudo systemctl start sistema-crt
```

### Puertos a abrir en Security Group / Firewall

| Puerto | Para qué |
|--------|----------|
| 22 | SSH (solo tu IP) |
| 8051 | App Dash |
| 80/443 | Si se agrega Nginx al frente |
