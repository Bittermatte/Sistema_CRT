"""Tests para pdf_service — Fase 1."""

import base64
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest


def test_load_pdf_returns_base64_string():
    """El loader debe retornar una cadena base64 válida cuando el archivo existe."""
    fake_pdf_bytes = b"%PDF-1.4 fake content"
    expected_b64 = base64.b64encode(fake_pdf_bytes).decode("utf-8")

    with patch("builtins.open", mock_open(read_data=fake_pdf_bytes)):
        with patch("pathlib.Path.exists", return_value=True):
            # Importar dentro del test para evitar cache entre tests
            from src.services import pdf_service
            # Limpiar cache de Streamlit si existe
            if hasattr(pdf_service.load_pdf_as_base64, "clear"):
                pdf_service.load_pdf_as_base64.clear()

            result = pdf_service.load_pdf_as_base64()

    assert result == expected_b64


def test_load_pdf_returns_empty_string_when_file_missing():
    """Si el PDF no existe, debe retornar cadena vacía sin lanzar excepción."""
    with patch("pathlib.Path.exists", return_value=False):
        from src.services import pdf_service
        if hasattr(pdf_service.load_pdf_as_base64, "clear"):
            pdf_service.load_pdf_as_base64.clear()

        result = pdf_service.load_pdf_as_base64()

    assert result == ""
