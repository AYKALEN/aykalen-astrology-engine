"""Synthetic regression checks for the extracted computation-only core."""

import copy
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest

import pytz
import swisseph as swe

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine.core import (
    ChartData, _find_ingress_egress, _signed_angle_diff_deg,
    _sun_sidereal_long_deg, _tithi_angle_deg,
)


def synthetic_chart(**overrides):
    data = dict(full_name="synthetic", date="2000-06-15", real_time="12:00:00",
                latitude=10.0, longitude=20.0, timezone="UTC")
    data.update(overrides)
    return ChartData(**data)


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chart = synthetic_chart()

    def test_silent_core_and_explicit_coordinates(self):
        output = io.StringIO()
        with redirect_stdout(output):
            chart = synthetic_chart(silent_mode=False)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(chart.jd_ut, swe.julday(2000, 6, 15, 12.0))
        with self.assertRaises(ValueError):
            synthetic_chart(latitude=None, longitude=None, city="not-looked-up")

    def test_invalid_coordinates_and_timezone_rejected(self):
        for overrides in ({"latitude": float("nan")}, {"longitude": float("inf")},
                          {"latitude": 91}, {"longitude": 181}, {"timezone": ""},
                          {"timezone": "Not/A_Zone"}):
            with self.subTest(overrides=overrides), self.assertRaises((ValueError, pytz.UnknownTimeZoneError)):
                synthetic_chart(**overrides)

    def test_dst_gap_and_ambiguity_are_not_silently_resolved(self):
        with self.assertRaises(pytz.NonExistentTimeError):
            synthetic_chart(date="2026-03-29", real_time="02:30:00", timezone="Europe/Warsaw")
        with self.assertRaises(pytz.AmbiguousTimeError):
            synthetic_chart(date="2026-10-25", real_time="02:30:00", timezone="Europe/Warsaw")

    def test_standard_vargas_have_all_bodies_and_valid_houses(self):
        charts = self.chart.calculate_all_divisionals_from_detailed(self.chart.detailed_chart_data)
        self.assertEqual(set(charts), {"D2_parashara", "D2_parivritti", "D2_kashinatha", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11_iyer",
                                      "D12", "D16", "D20", "D24", "D27", "D30", "D40", "D45", "D60"})
        bodies = {"AS", "SU", "MO", "MA", "ME", "JU", "VE", "SA", "RA", "KE"}
        for name, chart in charts.items():
            with self.subTest(varga=name):
                self.assertEqual(set(chart), bodies)
                self.assertEqual(chart["AS"]["house"], 1)
                self.assertTrue(all(1 <= data["house"] <= 12 for data in chart.values()))

    def test_true_and_mean_nodes_are_separate_and_opposite(self):
        chart = self.chart.detailed_chart_data
        for field in ("position_degrees_exact", "position_degrees_mean_node"):
            self.assertAlmostEqual((chart["KE"][field] - chart["RA"][field]) % 360, 180)

    def test_temporal_chart_restores_all_natal_attributes(self):
        chart = copy.deepcopy(self.chart)
        before = copy.deepcopy(chart.__dict__)
        tp = chart._compute_detailed_chart_at_jd(chart.jd_ut + 200.12345)
        self.assertEqual(chart.__dict__, before)
        self.assertNotEqual(tp["AS"]["position_degrees_exact"], chart.ascendant_adjusted_position)

    def test_ingress_egress_crosses_january_without_crashing(self):
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        ingress, egress = _find_ingress_egress(2026, 8)
        self.assertEqual(swe.revjul(ingress)[:2], (2026, 12))
        self.assertEqual(swe.revjul(egress)[:2], (2027, 1))
        self.assertGreater(egress - ingress, 25)
        self.assertLess(egress - ingress, 40)
        self.assertAlmostEqual(_sun_sidereal_long_deg(ingress), 240, places=4)
        self.assertAlmostEqual(_sun_sidereal_long_deg(egress), 270, places=4)

    def test_tp_hora_default_and_natal_preservation(self):
        chart = copy.deepcopy(self.chart)
        natal = copy.deepcopy(chart.detailed_chart_data)
        ascendant = chart.ascendant_adjusted_position
        chart.generate_tithi_pravesha_chart(2026)
        self.assertEqual(chart.detailed_chart_data, natal)
        self.assertEqual(chart.ascendant_adjusted_position, ascendant)
        self.assertEqual(chart.tp_datetime_local.utcoffset().total_seconds(), 0)
        schedule = chart.get_hora_schedule_for_tp()
        self.assertEqual(len(schedule), 24)
        self.assertTrue(all(a[4] == b[3] for a, b in zip(schedule, schedule[1:]) if a[0] == b[0]))
        hora = chart.get_hora_lord_for_tp()
        matching = [row for row in schedule if row[3] <= chart.tp_jd_ut < row[4]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(hora["lord_code"], matching[0][2])

    def test_january_birth_tp_uses_documented_ingress_year(self):
        chart = synthetic_chart(date="2000-01-08")
        chart.generate_tithi_pravesha_chart(2026)
        # Target 2026 denotes the ingress year, not necessarily the return year.
        self.assertEqual(chart.tp_year, 2026)
        self.assertEqual((chart.tp_datetime_utc.year, chart.tp_datetime_utc.month), (2027, 1))
        residual = abs(_signed_angle_diff_deg(_tithi_angle_deg(chart.tp_jd_ut),
                                              _tithi_angle_deg(chart.jd_ut)))
        self.assertLess(residual, 1e-4)

    def test_no_legacy_registry_reporting_or_now_filtered_dasha_api(self):
        for removed in ("get_coordinates_from_csv", "get_doc_links", "generate_planet_description",
                        "generate_chart_descriptions", "get_tp_lagna_interpretation",
                        "print_summary", "vimshottari_dasha"):
            self.assertFalse(hasattr(self.chart, removed), removed)


if __name__ == "__main__":
    unittest.main()
