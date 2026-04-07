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

# Run tests
pytest
pytest tests/test_pdf_service.py -v
pytest --cov=src tests/
```

---

## Estado actual del proyecto (2026-04-06)

### Entry point activo

`app_dash.py` — Dash app, puerto 8051. `app.py` (Streamlit) conservado solo como referencia.

### Flujo principal

```
Usuario sube PDF/Excel
  → clasificar_documento()          # por extensión (.xlsx → factura) o contenido (PDF)
  → extraer_documento()             # llama extractor guía o factura
  → buscar_match_guia/factura()     # 4 capas de matching
  → construir_form_data()           # siempre, incluso para borradores
  → generate_crt_pdf()              # genera PDF (borrador o completo)
  → kanban + vista previa           # visible inmediatamente
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
| `src/services/orchestrator.py` | ✅ activo | Coordinador central: clasifica → extrae → matchea → genera form_data |
| `src/services/pdf_service.py` | ✅ activo | Generador PDF con ReportLab (`generate_crt_pdf`) |
| `modulos/config_cliente.py` | ✅ activo | Configs de 6 pesqueras + detección automática |
| `modulos/extractor_guias.py` | ✅ activo | Extrae datos de guías de despacho PDF |
| `modulos/extractor_facturas.py` | ✅ activo | Extrae datos de facturas PDF y Excel (.xlsx) |
| `modulos/motor_calculos.py` | ✅ activo | Prorrateo de fletes |
| `modulos/generador_glosas.py` | ✅ activo | Genera textos casillas 8 y 18 del CRT |

### Legacy / referencia

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `app.py` | 🗄 legacy | Streamlit — no usar, conservar |
| `src/ui/` | 🗄 legacy | Frontend Streamlit completo |
| `modulos/creador_crt.py` | 🗄 referencia | Generador PDF legacy — fuente de coordenadas |
| `src/services/pdf_builder.py` | 🗄 experimental | Variante de generador PDF |
| `src/services/excel_pdf_builder.py` | 🗄 experimental | Variante Excel→PDF |

### Stubs Fase 2/3 (no implementados)

`src/services/db_service.py`, `src/services/customs_service.py`, `src/api/routes.py`,
`src/models/crt.py`, `src/dash_ui/pages/buscar.py`, `src/dash_ui/pages/historial.py`

---

## Módulos detallados

### `modulos/config_cliente.py`

6 pesqueras: `aquachile`, `blumar_magallanes`, `blumar`, `multix`, `australis`, `cermaq`.

Cada config tiene: `remitente`, `dir_remitente`, `transportista`, `dir_transportista`,
`lugar_emision`, `tarifa_flete`, `firma_remitente`, `paso_frontera`, `aeropuerto`.

```python
from modulos.config_cliente import detectar_pesquera, get_config, get_config_desde_texto
clave, config = get_config_desde_texto(texto_pdf)
```

### `modulos/extractor_guias.py`

Extrae de guías PDF: `numero_guia`, `orden_venta`, `peso_bruto`, `peso_neto`, `bultos`,
`patente_tracto`, `patente_semi`, `conductor`, `cert_sanitario`, `destinatario`, `pesquera`.

`orden_venta` usa patrón específico por pesquera (`PATRONES_ORDEN_VENTA_PESQUERA`):
- Multi X: `N° Pedido:`
- AquaChile: `PEDIDO EXPORTACION`
- Blumar: `PO:`
- Cermaq: `CO - CLIENTE:` (solo captura los dígitos)
- Australis: fallback genérico

### `modulos/extractor_facturas.py`

Soporta **PDF y Excel (.xlsx)**. Detecta por extensión automáticamente.

Extrae: `numero_factura`, `ref_pedido`, `incoterm`, `moneda`, `total`, `destinatario`,
`direccion`, `pais_destino`, `cert_sanitario`, `pesquera`.

`ref_pedido` usa patrón específico por pesquera (`PATRONES_REF_PEDIDO_PESQUERA`):
- Multi X: `PV:`
- AquaChile: `N° PEDIDO / ORDER`
- Blumar: `SELLER'S REFERENCE No.`
- Cermaq: `Order Ref`

El extractor Excel (openpyxl) busca etiquetas por celda y toma el valor adyacente.

### `src/services/orchestrator.py`

Funciones clave:
- `procesar_documentos(store_actual, archivos)` — punto de entrada único
- `clasificar_documento(file_bytes, nombre)` — soporta PDF y Excel
- `detectar_discrepancias(guia_datos, factura_datos)` — compara bultos, peso bruto, peso neto
- `construir_form_data(crt)` — genera dict `f_*` para el PDF; se llama siempre, incluso para borradores
- `recalcular_fletes(crts)` — agrupa por patente, proratea por peso; usa `crt["config"]["tarifa_flete"]`

Discrepancias se prefijan con `"DISCREPANCIA:"` para que el callback las coloree en naranja.

### `src/dash_ui/pages/elaborar_crt.py`

- Upload acepta `.pdf,.xlsx,.xls`
- CRTs incompletos (FALTA_FACTURA / FALTA_GUIA) muestran borrador PDF inmediatamente
- Botón descarga: "Descargar borrador" (naranja) para incompletos, "Descargar CRT" (azul) para completos
- Alertas: naranja = discrepancia logística, rojo = error de procesamiento

---

## Reglas de negocio

- **Prorrateo flete (Casilla 15)**: `flete_usd = (peso_bruto_CRT / peso_bruto_camión) × tarifa`
  - Tarifa por defecto: 4,400 USD por camión (configurable por pesquera en `config_cliente.py`)
- **Destinatarios especiales** (`motor_calculos.py`): `MARDI S.A.` y `AGRO COMERCIAL DEL CARMEN S.A.`
  usan tarifa fija 4,250 USD (split: 340 USD origen/frontera + 3,910 USD frontera/destino)
- **Correlativo CRT**: generado por `generador_glosas.py` a partir de `next_numero` del store
- **Valor mercadería**: solo se usa el de la factura — nunca el de la guía

---

## Pendientes en orden de prioridad

### P1 — Crítico (bloquea operación)

1. **Validar patrones con documentos reales de cada pesquera**
   - Probar `orden_venta` y `ref_pedido` con guías y facturas reales de Multi X, Cermaq, Blumar
   - Los patrones fueron definidos a partir de descripción verbal — pueden necesitar ajuste
   - Herramienta de diagnóstico: `python3 -c "from modulos.extractor_guias import extraer_datos_guia; import pprint; pprint.pprint(extraer_datos_guia('ruta/guia.pdf'))"`

2. **Probar Excel de Blumar y Cermaq**
   - El extractor Excel usa búsqueda por etiqueta de celda — la estructura real puede diferir
   - Si falla, ajustar `extraer_datos_factura_excel()` en `modulos/extractor_facturas.py`

3. **`openpyxl` en requirements.txt**
   - Verificar que está declarado: `grep openpyxl requirements.txt`
   - Si no está, agregarlo

### P2 — Importante (mejora la experiencia)

4. **Parser de tabla de productos en guías**
   - `extractor_guias.py` retorna `"productos": []` — campo reservado pero vacío
   - Los `f_descripcion_1`, `f_kilos_netos_1` en el PDF quedan en blanco
   - Cada pesquera tiene formato de tabla diferente (ver `modulos/creador_crt.py` legacy para referencia)

5. **Fecha del documento en el CRT**
   - `f_fecha_emision` y `f_fecha_documento` siempre vacíos
   - Agregar extracción de fecha en guías (`FECHA:`, `FECHA EMISION:`)

6. **Manejo de múltiples guías por factura** (o viceversa)
   - Actualmente Capa 0 retorna el primero que matchea — si hay 2 guías con el mismo `orden_venta`, solo se empareja la primera

### P3 — Deseado (robustez)

7. **Tests unitarios para extractores**
   - No existe ningún test para `extractor_guias`, `extractor_facturas`, ni `orchestrator`
   - Mínimo: test con el archivo `modulos/pdfs_prueba/guia_agrosuper.pdf`

8. **Persistencia del store entre recargas**
   - `dcc.Store` usa `storage_type="memory"` — se pierde al recargar la página
   - Cambiar a `"session"` o `"local"` para persistir durante la sesión del browser

9. **Fase 2: base de datos**
   - Stubs listos en `src/services/db_service.py` y `src/models/crt.py`
   - Requiere PostgreSQL + SQLAlchemy
