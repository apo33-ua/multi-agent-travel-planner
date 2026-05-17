"""Tests unitarios de _to_float: conversión de cadenas monetarias heterogéneas."""
import pytest

from supervisor_viajes import _to_float


class TestToFloat:
    # --- tipos nativos ---
    def test_int(self):
        assert _to_float(500) == 500.0

    def test_float(self):
        assert _to_float(123.45) == 123.45

    def test_none(self):
        assert _to_float(None) is None

    def test_list_returns_none(self):
        assert _to_float([100]) is None

    # --- cadenas simples ---
    def test_plain_integer_string(self):
        assert _to_float("500") == 500.0

    def test_plain_decimal_string(self):
        assert _to_float("123.45") == 123.45

    def test_empty_string(self):
        assert _to_float("") is None

    def test_non_numeric_string(self):
        assert _to_float("N/D") is None

    # --- formato anglosajón (miles con coma, decimal con punto) ---
    def test_us_thousands_and_decimal(self):
        assert _to_float("1,250.75") == 1250.75

    def test_us_thousands_no_decimal(self):
        # "1,250" → miles, sin parte decimal → 1250
        assert _to_float("1,250") == 1250.0

    def test_us_large(self):
        assert _to_float("12,345.00") == 12345.0

    # --- formato europeo (miles con punto, decimal con coma) ---
    def test_eu_thousands_and_decimal(self):
        assert _to_float("1.250,75") == 1250.75

    def test_eu_thousands_no_decimal(self):
        # "1.250" → miles, sin parte decimal → 1250
        assert _to_float("1.250") == 1250.0

    def test_eu_large(self):
        assert _to_float("12.345,00") == 12345.0

    # --- símbolos de moneda y espacios ---
    def test_with_euro_symbol(self):
        assert _to_float("500 €") == 500.0

    def test_with_dollar_symbol(self):
        assert _to_float("$1,234.56") == 1234.56

    def test_with_nbsp(self):
        # Non-breaking space como separador de miles (formato francés/ruso)
        assert _to_float("1 250") == 1250.0

    # --- casos límite del TFG (precios reales de mock) ---
    def test_typical_flight_price(self):
        assert _to_float("180") == 180.0

    def test_typical_hotel_total(self):
        assert _to_float("270") == 270.0
