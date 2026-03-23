# Sistema CRT — Arquitectura y Hoja de Ruta

## Fases de Desarrollo

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Plataforma web: formulario CRT 24 campos + Live Preview PDF + generación PDF final | En desarrollo |
| 2 | Conexión automatizada con Aduana (RPA/API): MIC automático + historial en BD | Pendiente |
| 3 | App móvil: visualización, revisión y aprobación de CRTs/MICs en terreno | Pendiente |

## Stack Tecnológico

- **Frontend Web**: Streamlit (Python)
- **Validación de datos**: Pydantic v2
- **PDF**: pypdf (leer/rellenar), pdfplumber (extraer texto)
- **Base de datos** (Fase 2): PostgreSQL + SQLAlchemy 2.0
- **API móvil** (Fase 3): FastAPI + uvicorn

## Mapa de Casillas CRT → Campos del Modelo

| Casilla | Nombre en modelo | Notas |
|---------|-----------------|-------|
| 1 | `numero_crt` | Identificador único |
| 2 | `lugar_emision` | |
| 3 | `fecha_emision` | |
| 4 | `remitente` | |
| 5 | `fecha_documento` | Toma fecha de la Factura |
| 6 | `dir_remitente` | |
| 7 | `fecha_entrega` | Toma fecha de la Factura |
| 8 | `destinatario` | Overrides: MARDI SA, AGRO COMERCIAL |
| 9 | `dir_destinatario` | |
| 10 | `transportista` | |
| 11 | `pais_origen` | |
| 12 | `pais_destino` | |
| 13 | `lugar_recepcion` | Puerto Natales / Punta Arenas |
| 14 | `incoterm` | Extraído de la Factura |
| 15 | `flete_usd` | Prorrateo: (KgBrutos_CRT × Tarifa) / KgBrutos_Camión |
| 16 | `lugar_entrega` | |
| 17 | `num_bultos` | |
| 18 | `instrucciones_aduana` | Glosas / Codaut |
| 19 | `tipo_embalaje` | |
| 20 | `descripcion` | |
| 21 | `peso_neto_kg` | |
| 22 | `peso_bruto_kg` | Usado en prorrateo de flete |
| 23 | `marcas_numeros` | |
| 24 | `num_factura` | |

## Reglas de Negocio Fase 1

### Prorrateo de Flete (Casilla 15)
- Agrupa CRTs por Patente de Camión/Rampla
- Tarifa Puerto Natales: 4.400 USD | Punta Arenas: 4.250 USD
- Fórmula: `(KgBrutos_CRT × Tarifa) / KgBrutos_Camión`
- Resultado en columna "Monto remitente"

### Overrides Estrictos (Destinatarios especiales)
- `MARDI S.A.` → Tarifa fija 4.250 USD en "Valor destinatario"
  - Desglose: Origen/Frontera 340 USD + Frontera/Destino 3.910 USD
- `AGRO COMERCIAL DEL CARMEN S.A.` → misma regla
