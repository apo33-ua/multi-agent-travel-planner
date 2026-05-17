"""Tests de _build_budget_combinations y _budget_node (RF-10/11/12)."""
import pytest

from supervisor_viajes import _build_budget_combinations, _budget_node


VUELOS = [
    {"airline": "Iberia", "price": "250", "duration": 145, "stops": []},
    {"airline": "Ryanair", "price": "180", "duration": 140, "stops": []},
    {"airline": "Vueling", "price": "320", "duration": 150, "stops": []},
]

HOTELES = [
    {"name": "Hotel Centro", "rating": 4.2, "price_per_night": "90", "total_rate": "270", "type": "Hotel"},
    {"name": "Hostal Barato", "rating": 3.8, "price_per_night": "55", "total_rate": "165", "type": "Hostel"},
    {"name": "Gran Hotel", "rating": 4.9, "price_per_night": "400", "total_rate": "1200", "type": "Hotel"},
]


class TestBuildBudgetCombinations:
    def test_decision_ok_when_combos_fit(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=800.0)
        assert result["auditoria"]["decision"] == "ok"
        assert result["auditoria"]["n_validas"] > 0

    def test_decision_solo_sugerencias_when_nothing_fits(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=50.0)
        assert result["auditoria"]["decision"] == "solo-sugerencias-fuera-presupuesto"
        assert result["auditoria"]["n_validas"] == 0
        assert result["auditoria"]["n_excluidas"] > 0

    def test_validas_sorted_by_total_ascending(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=2000.0)
        totales = [c["total_estimated"] for c in result["validas"]]
        assert totales == sorted(totales)

    def test_all_valid_combos_have_fits_budget_true(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=800.0)
        for combo in result["validas"]:
            assert combo["fits_budget"] is True
            assert combo["excluded_by_budget"] is False

    def test_all_excluded_combos_have_fits_budget_false(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=50.0)
        for combo in result["excluidas"]:
            assert combo["fits_budget"] is False
            assert combo["excluded_by_budget"] is True

    def test_budget_gap_positive_when_fits(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=800.0)
        for combo in result["validas"]:
            assert combo["budget_gap"] >= 0

    def test_budget_gap_negative_when_excluded(self):
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=50.0)
        for combo in result["excluidas"]:
            assert combo["budget_gap"] < 0

    def test_auditoria_total_evaluadas(self):
        # total_evaluadas cuenta todos los cruces brutos; n_validas y n_excluidas
        # están acotados a 5 cada uno, así que total >= n_validas + n_excluidas
        result = _build_budget_combinations(VUELOS, HOTELES, presupuesto=800.0)
        auditoria = result["auditoria"]
        assert auditoria["total_evaluadas"] >= auditoria["n_validas"] + auditoria["n_excluidas"]
        assert auditoria["total_evaluadas"] == len(VUELOS) * len(HOTELES)

    def test_empty_vuelos_returns_sin_datos(self):
        result = _build_budget_combinations([], HOTELES, presupuesto=800.0)
        assert result["auditoria"]["decision"] == "sin-datos"

    def test_empty_hoteles_returns_sin_datos(self):
        result = _build_budget_combinations(VUELOS, [], presupuesto=800.0)
        assert result["auditoria"]["decision"] == "sin-datos"

    def test_price_unparseable_skipped(self):
        vuelos_malos = [{"airline": "X", "price": "N/D", "duration": 100, "stops": []}]
        result = _build_budget_combinations(vuelos_malos, HOTELES, presupuesto=1000.0)
        assert result["auditoria"]["total_evaluadas"] == 0


class TestBudgetNode:
    def test_no_presupuesto_returns_sin_datos(self):
        state = {
            "presupuesto_total_eur": 0,
            "opciones_vuelos": VUELOS,
            "opciones_hoteles": HOTELES,
        }
        result = _budget_node(state)
        assert result["auditoria_presupuesto"]["decision"] == "sin-datos"
        assert result["combinaciones_presupuesto"] == []
        assert result["acciones_sugeridas"] == []

    def test_no_vuelos_returns_sin_datos_with_acciones(self):
        state = {
            "presupuesto_total_eur": 800.0,
            "opciones_vuelos": [],
            "opciones_hoteles": HOTELES,
        }
        result = _budget_node(state)
        assert result["auditoria_presupuesto"]["decision"] == "sin-datos"
        assert len(result["acciones_sugeridas"]) > 0

    def test_budget_ok_sets_combinaciones(self):
        state = {
            "presupuesto_total_eur": 800.0,
            "opciones_vuelos": VUELOS,
            "opciones_hoteles": HOTELES,
        }
        result = _budget_node(state)
        assert result["auditoria_presupuesto"]["decision"] == "ok"
        assert len(result["combinaciones_presupuesto"]) > 0

    def test_budget_too_low_sets_acciones(self):
        state = {
            "presupuesto_total_eur": 10.0,
            "opciones_vuelos": VUELOS,
            "opciones_hoteles": HOTELES,
        }
        result = _budget_node(state)
        assert result["auditoria_presupuesto"]["decision"] == "solo-sugerencias-fuera-presupuesto"
        assert len(result["acciones_sugeridas"]) >= 3
