"""Tests de _select_forecast_for_date: selección robusta del bloque de forecast."""
from datetime import date

import pytest

from agente_clima import _select_forecast_for_date


def _make_item(dt_txt: str) -> dict:
    return {
        "dt_txt": dt_txt,
        "main": {"temp": 20.0, "feels_like": 18.0, "humidity": 60},
        "weather": [{"description": "cielos despejados"}],
        "wind": {"speed": 3.0},
    }


class TestSelectForecastForDate:
    def test_exact_date_prefers_noon(self):
        items = [
            _make_item("2026-06-15 06:00:00"),
            _make_item("2026-06-15 12:00:00"),
            _make_item("2026-06-15 18:00:00"),
        ]
        result = _select_forecast_for_date(items, date(2026, 6, 15))
        assert result["dt_txt"] == "2026-06-15 12:00:00"

    def test_exact_date_single_block(self):
        items = [_make_item("2026-06-15 09:00:00")]
        result = _select_forecast_for_date(items, date(2026, 6, 15))
        assert result["dt_txt"] == "2026-06-15 09:00:00"

    def test_no_exact_date_falls_back_to_closest(self):
        # Ningún bloque coincide con la fecha objetivo → cae al más cercano
        items = [
            _make_item("2026-06-13 12:00:00"),
            _make_item("2026-06-14 12:00:00"),
            _make_item("2026-06-16 12:00:00"),
        ]
        result = _select_forecast_for_date(items, date(2026, 6, 15))
        # 14 está a 24h, 16 está a 24h → empate → cualquiera de los dos es válido
        assert result["dt_txt"] in ("2026-06-14 12:00:00", "2026-06-16 12:00:00")

    def test_past_mock_dates_dont_crash(self):
        # Reproduce el bug original: mock con fechas pasadas + fecha objetivo futura
        items = [
            _make_item("2026-03-24 12:00:00"),
            _make_item("2026-03-25 12:00:00"),
            _make_item("2026-03-26 12:00:00"),
        ]
        # Debe devolver algo (el bloque más cercano), no lanzar RuntimeError
        result = _select_forecast_for_date(items, date(2026, 6, 15))
        assert "dt_txt" in result

    def test_empty_items_raises(self):
        with pytest.raises(RuntimeError, match="Sin bloques"):
            _select_forecast_for_date([], date(2026, 6, 15))

    def test_items_with_missing_dt_txt_skipped(self):
        items = [
            {"main": {}, "weather": [{}], "wind": {}},  # sin dt_txt
            _make_item("2026-06-15 12:00:00"),
        ]
        result = _select_forecast_for_date(items, date(2026, 6, 15))
        assert result["dt_txt"] == "2026-06-15 12:00:00"

    def test_all_items_missing_dt_txt_raises(self):
        items = [{"main": {}, "weather": [{}], "wind": {}}]
        with pytest.raises(RuntimeError):
            _select_forecast_for_date(items, date(2026, 6, 15))
