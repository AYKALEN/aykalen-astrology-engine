"""Equal sunrise-day horas: reference example, uniform lengths and boundaries."""
import copy
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import swisseph as swe

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine.core import ChartData, HORA_METHOD


class PlanetaryHourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prototype = ChartData(
            full_name="synthetic", date="2000-06-15", real_time="12:00:00",
            latitude=10.0, longitude=20.0, timezone="UTC",
        )

    def chart(self, day=11, hour=21 + 40 / 60, day_length=1.0):
        chart = copy.deepcopy(self.prototype)
        chart.sunrise_mode = "center"
        chart.tp_datetime_local = datetime(2024, 9, day, tzinfo=timezone.utc)
        chart.tp_jd_ut = swe.julday(2024, 9, day, hour)
        chart.tp_sr_prev_ut = swe.julday(2024, 9, day, 6)
        chart.tp_ss_ut = swe.julday(2024, 9, day, 19)
        chart.tp_sr_next_ut = chart.tp_sr_prev_ut + day_length
        return chart

    def test_published_wednesday_example(self):
        # P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach,
        # section 1.3.11: Wednesday 6:10am sunrise, 9:40pm -> 16th hora, Moon.
        chart = self.chart()
        chart.tp_sr_prev_ut = swe.julday(2024, 9, 11, 6 + 10 / 60)
        chart.tp_sr_next_ut = chart.tp_sr_prev_ut + 1
        hora = chart.get_hora_lord_for_tp()
        self.assertEqual((hora["index"], hora["lord_code"]), (16, "MO"))
        self.assertEqual(hora["vaara_lord_code"], "ME")
        self.assertEqual(hora["method"], HORA_METHOD)

    def test_saturday_seventeenth_hora_is_mars(self):
        chart = self.chart(day=14, hour=22.5)
        hora = chart.get_hora_lord_for_tp()
        self.assertEqual((hora["index"], hora["lord_code"]), (17, "MA"))
        self.assertEqual(hora["vaara_lord_code"], "SA")

    def test_uniform_intervals_follow_next_sunrise_not_sunset_or_fixed_minutes(self):
        chart = self.chart(day_length=1 + 24 / 1440)
        schedule = chart.get_hora_schedule_for_tp()
        self.assertEqual(len(schedule), 24)
        self.assertEqual([row[1] for row in schedule], list(range(1, 25)))
        self.assertEqual({row[0] for row in schedule}, {"sunrise_day"})
        for row in schedule:
            self.assertAlmostEqual((row[4] - row[3]) * 86400, 61 * 60, delta=0.0001)
        for left, right in zip(schedule, schedule[1:]):
            self.assertEqual(left[4], right[3])
        self.assertEqual(schedule[0][3], chart.tp_sr_prev_ut)
        self.assertEqual(schedule[-1][4], chart.tp_sr_next_ut)
        chart.tp_ss_ut += 2 / 24
        self.assertEqual(chart.get_hora_schedule_for_tp(), schedule)

    def test_all_boundaries_belong_to_the_new_hora(self):
        chart = self.chart(day_length=1.001)
        schedule = chart.get_hora_schedule_for_tp()
        for index, row in enumerate(schedule):
            with self.subTest(hora=index + 1):
                chart.tp_jd_ut = row[3]
                hora = chart.get_hora_lord_for_tp()
                self.assertEqual(hora["index"], index + 1)
                self.assertEqual(hora["lord_code"], row[2])
                if index:
                    chart.tp_jd_ut = math.nextafter(row[3], -math.inf)
                    self.assertEqual(chart.get_hora_lord_for_tp()["index"], index)

    def test_next_sunrise_starts_the_next_vaara_and_first_hora(self):
        chart = self.chart(day=14)
        chart.tp_jd_ut = chart.tp_sr_next_ut
        next_window = (chart.tp_sr_next_ut, chart.tp_ss_ut + 1, chart.tp_sr_next_ut + 1)
        with patch.object(chart, "_sr_ss_by_se", return_value=next_window) as sunrise:
            hora = chart.get_hora_lord_for_tp()
            self.assertEqual((hora["index"], hora["lord_code"], hora["vaara_lord_code"]), (1, "SU", "SU"))
            self.assertEqual(hora["start_ut"], chart.tp_jd_ut)
            sunrise.assert_called_with(chart.tp_jd_ut, mode="center")

    def test_explicit_sunrise_mode_does_not_reuse_other_modes_cache(self):
        chart = self.chart(day=14, hour=6.25)
        # An alternative sunrise is after TP, so its sunrise day is still Friday.
        alternative = (chart.tp_sr_prev_ut - 1 + 0.5 / 24, chart.tp_ss_ut - 1,
                       chart.tp_sr_prev_ut + 0.5 / 24)
        cache_before = (chart.tp_sr_prev_ut, chart.tp_ss_ut, chart.tp_sr_next_ut)
        with patch.object(chart, "_sr_ss_by_se", return_value=alternative) as sunrise:
            hora = chart.get_hora_lord_for_tp("standard")
            self.assertEqual((hora["index"], hora["lord_code"], hora["vaara_lord_code"]), (24, "MO", "VE"))
            self.assertEqual(hora["sunrise_mode"], "standard")
            sunrise.assert_called_with(chart.tp_jd_ut, mode="standard")
        self.assertEqual((chart.tp_sr_prev_ut, chart.tp_ss_ut, chart.tp_sr_next_ut), cache_before)
        self.assertEqual(chart.get_hora_lord_for_tp()["lord_code"], "SA")

    def test_real_sunrise_rollover_when_sunrise_is_getting_later(self):
        for mode in ("center", "standard"):
            chart = self.chart(day=14)
            chart.latitude, chart.longitude = 53.33972222, 15.0375
            chart.sunrise_mode = mode
            start, sunset, end = chart._sr_ss_by_se(chart.tp_jd_ut, mode=mode)
            self.assertGreater(end - start, 1)
            for delta_seconds, expected in ((-60, (24, "MA", "SA")),
                                            (-1, (24, "MA", "SA")),
                                            (0, (1, "SU", "SU")),
                                            (1, (1, "SU", "SU"))):
                for cached in (False, True):
                    with self.subTest(mode=mode, delta=delta_seconds, cached=cached):
                        sample = copy.deepcopy(chart)
                        sample.tp_jd_ut = end + delta_seconds / 86400
                        for key in ("tp_sr_prev_ut", "tp_ss_ut", "tp_sr_next_ut"):
                            delattr(sample, key)
                        if cached:
                            sample.tp_sr_prev_ut, sample.tp_ss_ut, sample.tp_sr_next_ut = start, sunset, end
                        hora = sample.get_hora_lord_for_tp()
                        self.assertEqual((hora["index"], hora["lord_code"], hora["vaara_lord_code"]), expected)
                        self.assertLessEqual(hora["start_ut"], sample.tp_jd_ut)
                        self.assertLess(sample.tp_jd_ut, hora["end_ut"])

    def test_missing_tp_and_invalid_mode_are_explicit_errors(self):
        chart = copy.deepcopy(self.prototype)
        for method in (chart.get_hora_lord_for_tp, chart.get_hora_schedule_for_tp, chart.get_vaara_lord_for_tp):
            with self.assertRaises(RuntimeError):
                method()
        with self.assertRaises(ValueError):
            self.chart().get_hora_lord_for_tp("unknown")


if __name__ == "__main__":
    unittest.main()
