"""
sheets_service.py — Integración Google Sheets para generación de CRT.

Flujo:
  1. Copia la pestaña PLANTILLA con el nombre del CRT
  2. Llena los campos usando named ranges
  3. Exporta la pestaña como PDF
  4. Retorna los bytes del PDF
"""

import time
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDENTIALS_PATH = Path("/sandbox/autocrt/credentials/google_service_account.json")
SPREADSHEET_ID   = "1ZslA9InWxdHJG7hptLkQj5I69H2L4RQE-M9hveyL8Kg"
TEMPLATE_SHEET   = "PLANTILLA"
CA_CERT          = "/etc/openshell-tls/openshell-ca.pem"
PROXY            = "http://10.200.0.1:3128"
BASE_URL         = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_URL        = "https://www.googleapis.com/drive/v3/files"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PESQUERA_COLORS = {
    "aquachile":         {"red": 0.0,  "green": 0.69, "blue": 0.31},
    "blumar":            {"red": 0.11, "green": 0.47, "blue": 0.78},
    "blumar magallanes": {"red": 0.11, "green": 0.47, "blue": 0.78},
    "multi x":           {"red": 0.93, "green": 0.42, "blue": 0.07},
    "australis":         {"red": 0.54, "green": 0.17, "blue": 0.89},
    "cermaq":            {"red": 0.83, "green": 0.07, "blue": 0.07},
}


def _fmt_num(val) -> str:
    """Convierte número a formato español: 41418.46 → 41.418,46"""
    if val is None or str(val).strip() in ("", "None"):
        return ""
    try:
        f = float(str(val).replace(",", "."))
        partes = f"{f:,.2f}".split(".")
        entero = partes[0].replace(",", ".")
        return f"{entero},{partes[1]}"
    except (ValueError, TypeError):
        return str(val).strip()


def _get_session() -> AuthorizedSession:
    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH), scopes=SCOPES
    )
    creds = creds.with_always_use_jwt_access(True)
    session = AuthorizedSession(creds)
    session.verify  = CA_CERT
    session.proxies = {"https": PROXY, "http": PROXY}
    return session


def _get_meta(session: AuthorizedSession) -> dict:
    r = session.get(f"{BASE_URL}/{SPREADSHEET_ID}?fields=namedRanges,sheets.properties")
    r.raise_for_status()
    return r.json()


def _get_sheet_id(meta: dict, name: str) -> Optional[int]:
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == name:
            return s["properties"]["sheetId"]
    return None


def _copy_template(session: AuthorizedSession, new_name: str) -> int:
    meta = _get_meta(session)
    template_id = _get_sheet_id(meta, TEMPLATE_SHEET)
    if template_id is None:
        raise ValueError(f"No se encontró la pestaña '{TEMPLATE_SHEET}'")

    r = session.post(
        f"{BASE_URL}/{SPREADSHEET_ID}/sheets/{template_id}:copyTo",
        json={"destinationSpreadsheetId": SPREADSHEET_ID},
    )
    r.raise_for_status()
    new_sheet_id = r.json()["sheetId"]

    r2 = session.post(
        f"{BASE_URL}/{SPREADSHEET_ID}:batchUpdate",
        json={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": new_sheet_id, "title": new_name},
            "fields": "title",
        }}]},
    )
    r2.raise_for_status()
    return new_sheet_id


def _apply_tab_color(session: AuthorizedSession, sheet_id: int, pesquera: str):
    color = PESQUERA_COLORS.get(pesquera.lower().strip(), {"red": 0.5, "green": 0.5, "blue": 0.5})
    session.post(
        f"{BASE_URL}/{SPREADSHEET_ID}:batchUpdate",
        json={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "tabColor": color},
            "fields": "tabColor",
        }}]},
    )


def _fill_named_ranges(session: AuthorizedSession, sheet_name: str, form_data: dict, meta: dict):
    def v(key):
        val = form_data.get(key)
        if val is None:
            return ""
        if hasattr(val, "strftime"):
            return val.strftime("%d-%m-%Y")
        return str(val).strip()

    instr = v("f_instrucciones_aduana").split("\n") if v("f_instrucciones_aduana") else ["", "", ""]
    while len(instr) < 3:
        instr.append("")

    # --- FIX destino_final: evitar duplicar el prefijo si el extractor ya lo trae ---
    destino_raw = v("f_destino_final")
    if destino_raw.upper().startswith("ARGENTINA"):
        destino_final = destino_raw
    else:
        destino_final = f"ARGENTINA - DESTINO FINAL {destino_raw}".strip()

    # --- FIX cert_sanitario: mostrar prefijo siempre, número solo si existe ---
    cert = v("f_cert_sanitario")
    cert_sanitario = f"CERTIFICADO SANITARIO NRO: {cert}" if cert not in ("", "None") else "CERTIFICADO SANITARIO NRO: "

    campos = {
        "f_remitente":             v("f_remitente"),
        "f_dir_remitente_1":       v("f_dir_remitente").split("\n")[0] if "\n" in v("f_dir_remitente") else v("f_dir_remitente"),
        "f_dir_remitente_2":       v("f_dir_remitente").split("\n")[1] if "\n" in v("f_dir_remitente") else "",
        "f_numero_crt":            v("f_numero_crt"),
        "f_destinatario":          v("f_destinatario"),
        "f_dir_destinatario":      v("f_dir_destinatario"),
        "f_lugar_emision":         v("f_lugar_emision"),
        "f_lugar_recepcion_fecha": f"{v('f_lugar_recepcion')}   {v('f_fecha_documento')}".strip(),
        "f_lugar_entrega":         v("f_lugar_entrega"),
        "f_destino_final":         destino_final,
        "f_peso_bruto":            _fmt_num(form_data.get("f_peso_bruto")),
        "f_descripcion_1":         v("f_descripcion_1"),
        "f_descripcion_2":         v("f_descripcion_2"),
        "f_descripcion_3":         v("f_descripcion_3"),
        "f_descripcion_4":         v("f_descripcion_4"),
        "f_descripcion_5":         v("f_descripcion_5"),
        "f_total_cajas":           f"     TOTAL CAJAS: {v('f_total_cajas')}",
        "f_total_kilos_netos":     f"     TOTAL KILOS NETOS: {_fmt_num(form_data.get('f_peso_neto'))}",
        "f_total_kilos_brutos":    f"     TOTAL KILOS BRUTOS: {_fmt_num(form_data.get('f_peso_bruto'))}",
        "f_valor_incoterm":        f"{_fmt_num(form_data.get('f_valor_mercaderia'))} {v('f_incoterm')}".strip(),
        "f_declaracion_valor":     f"US$ {_fmt_num(form_data.get('f_valor_mercaderia'))}",
        "f_flete_usd":             _fmt_num(form_data.get("f_flete_usd")),
        "f_facturas_1":            f"FACTURAS NROS: {v('f_num_factura')}",
        "f_guias_1":               f"GUIAS DE DESPACHO: {v('f_guias_despacho')}",
        "f_cert_sanitario":        cert_sanitario,
        "f_instrucciones_1":       instr[0].strip(),
        "f_instrucciones_2":       instr[1].strip(),
        "f_instrucciones_3":       instr[2].strip(),
        "f_firma_remitente":       f"p.p. {v('f_remitente')}",
        "f_fecha_emision":         f"Fecha / Data  {v('f_fecha_emision')}",
        "f_conductor":             f"CONDUCTOR: {v('f_conductor')}",
        "f_patentes":              f"PATENTE CAMION: {v('f_patente_camion')} / PATENTE RAMPLA: {v('f_patente_rampla')}",
    }

    named_ranges_map = {}
    for nr in meta.get("namedRanges", []):
        named_ranges_map[nr["name"]] = nr["range"]

    data = []
    for campo, valor in campos.items():
        if campo not in named_ranges_map:
            continue
        rng = named_ranges_map[campo]
        col = chr(ord("A") + rng["startColumnIndex"])
        row = rng["startRowIndex"] + 1
        data.append({
            "range": f"'{sheet_name}'!{col}{row}",
            "values": [[valor]],
        })

    if data:
        r = session.post(
            f"{BASE_URL}/{SPREADSHEET_ID}/values:batchUpdate",
            json={"valueInputOption": "USER_ENTERED", "data": data},
        )
        r.raise_for_status()


def generate_crt_sheets(form_data: dict, pesquera: str) -> tuple[Optional[bytes], bool]:
    try:
        session = _get_session()
        meta = _get_meta(session)

        correlativo = form_data.get("f_numero_crt", "NUEVO")
        sheet_name  = f"{correlativo.replace(chr(47), chr(45))} - {pesquera.upper()[:15]}"

        new_sheet_id = _copy_template(session, sheet_name)
        _apply_tab_color(session, new_sheet_id, pesquera)
        _fill_named_ranges(session, sheet_name, form_data, meta)
        time.sleep(2)
        pdf_bytes = _export_pdf_sheet(new_sheet_id)
        return pdf_bytes, False

    except Exception as e:
        print(f"[sheets_service] Error: {e}")
        return None, True


# --- Export con OAuth del usuario ---
import json as _json

def _get_oauth_session():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession

    OAUTH_PATH = Path("/sandbox/autocrt/credentials/oauth_token.json")
    with open(OAUTH_PATH) as f:
        data = _json.load(f)

    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"]
    )
    session = AuthorizedSession(creds)
    session.verify  = CA_CERT
    session.proxies = {"https": PROXY, "http": PROXY}
    return session


def _export_pdf(session, sheet_id: int) -> bytes:
    oauth = _get_oauth_session()
    SHEET_ID = SPREADSHEET_ID
    r = oauth.get(
        f"https://www.googleapis.com/drive/v3/files/{SHEET_ID}/export?mimeType=application/pdf"
    )
    r.raise_for_status()
    return r.content


def _export_pdf_sheet(sheet_id: int) -> bytes:
    """Exporta solo la pestaña específica como PDF sin grilla."""
    oauth = _get_oauth_session()
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export"
        f"?format=pdf&scale=4"
        f"&gid={sheet_id}"
        f"&size=legal"
        f"&portrait=true"
        f"&fitw=true"
        f"&gridlines=false"
        f"&printtitle=false"
        f"&sheetnames=false"
        f"&fzr=false"
        f"&top_margin=0.25"
        f"&bottom_margin=0.25"
        f"&left_margin=0.25"
        f"&right_margin=0.25"
    )
    r = oauth.get(url)
    r.raise_for_status()
    return r.content
