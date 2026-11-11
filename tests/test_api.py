"""Synthetic data only; tests the public export and portable-folder boundary."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))

from astro_engine import calculate
from astro_engine.api import VARGAS, _validate

EXAMPLE = json.loads((ENGINE / "example.synthetic.json").read_text(encoding="utf-8"))


class InputTests(unittest.TestCase):
    def test_default_scope_is_d1(self):
        request = deepcopy(EXAMPLE)
        request.pop("allowed_vargas")
        self.assertEqual(_validate(request)[2], ["D1"])

    def test_bad_inputs_rejected(self):
        changes = [
            {"allowed_vargas": ["D9"]}, {"allowed_vargas": ["D1", "D1"]},
            {"allowed_vargas": ["D1", "D999"]}, {"allowed_vargas": "D10"},
            {"allowed_vargas": ["D1", "D11"]},  # Variant must be explicit.
            {"target_year": True}, {"target_year": 1800},
            {"sunrise_mode": "guess"}, {"api_key": "not-a-secret-synthetic"},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                _validate({**EXAMPLE, **change})

    def test_nonfinite_coordinates_and_polar_limit(self):
        for value in (float("nan"), float("inf"), True, 67, "50"):
            request = deepcopy(EXAMPLE)
            request["birth"]["latitude"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                _validate(request)

    def test_dst_gaps_folds_and_unknown_zone(self):
        for date, time, zone in (("2020-03-29", "02:30:00", "Europe/Warsaw"),
                                 ("2020-10-25", "02:30:00", "Europe/Warsaw"),
                                 ("2000-06-15", "12:00:00", "Unknown/Zone")):
            request = deepcopy(EXAMPLE)
            request["birth"].update(date=date, time=time, timezone=zone)
            with self.subTest(date=date, zone=zone), self.assertRaises(ValueError):
                _validate(request)


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        request = deepcopy(EXAMPLE)
        request["allowed_vargas"] = list(VARGAS)
        cls.result = calculate(request)

    def test_serializable_all_requested_natal_and_tp_vargas(self):
        json.dumps(self.result, allow_nan=False)
        for chart in (self.result["natal"], self.result["annual"]):
            self.assertEqual(set(chart["charts"]), set(VARGAS))
            for label, data in chart["charts"].items():
                self.assertEqual(len(data["positions"]), 10, label)
                self.assertEqual(len(data["house_lords"]), 12, label)
                self.assertEqual(data["positions"]["AS"]["house"], 1)
            self.assertFalse(chart["shadbala_components"]["full_shadbala_publishable"])
            self.assertIn(chart["ephemeris"]["SU"]["backend"], ("swiss", "moshier", "jpl"))

    def test_tp_phase_and_lagna_geometry(self):
        annual = self.result["annual"]
        self.assertLess(annual["phase_residual_degrees"], 1e-4)
        self.assertEqual(annual["lagna_distances"]["direction"], "natal_to_tp")
        for item in annual["lagna_distances"]["charts"].values():
            self.assertTrue(1 <= item["inclusive_sign_count"] <= 12)
        self.assertEqual(len(annual["hora_schedule"]), 24)

    def test_export_identifies_hora_convention_and_matching_schedule(self):
        from astro_engine.core import HORA_METHOD
        annual = self.result["annual"]
        hora = annual["hora"]
        self.assertEqual(self.result["calculation_profile"]["hora_method"], HORA_METHOD)
        self.assertEqual(hora["method"], HORA_METHOD)
        row = annual["hora_schedule"][hora["index"] - 1]
        self.assertEqual(row, [hora["which"], hora["index"], hora["lord_code"], hora["start_ut"], hora["end_ut"]])
        self.assertEqual(annual["vaara"]["lord_code"], hora["vaara_lord_code"])

    def test_added_vargas_use_each_period_d1_and_have_explicit_methods(self):
        from astro_engine.core import ChartData
        from astro_engine.facts import ZODIAC_SIGNS
        chart = ChartData.__new__(ChartData)
        chart.ZODIAC_SIGNS = ZODIAC_SIGNS
        methods = self.result['calculation_profile']['varga_methods']
        self.assertEqual(set(methods), {'D2_kashinatha', 'D5', 'D6', 'D8', 'D11_iyer'})
        self.assertIn('Iyer', methods['D11_iyer'])
        for label, function in (('D2_kashinatha', chart.calculate_hora_kashinatha_position),
                                ('D5', chart.calculate_panchamsa_position),
                                ('D6', chart.calculate_shashtamsa_position),
                                ('D8', chart.calculate_ashtamsa_position),
                                ('D11_iyer', chart.calculate_ekadasamsa_iyer_position)):
            for period in ('natal', 'annual'):
                charts = self.result[period]['charts']
                expected = chart._build_divisional_chart(function, charts['D1']['positions'])
                for code, position in expected.items():
                    self.assertEqual(charts[label]['positions'][code]['zodiac_sign'], position['zodiac_sign'])
                    self.assertEqual(charts[label]['positions'][code]['house'], position['house'])
            natal = self.result['natal']['charts'][label]['positions']['AS']['zodiac_sign']
            annual = self.result['annual']['charts'][label]['positions']['AS']['zodiac_sign']
            distance = self.result['annual']['lagna_distances']['charts'][label]
            self.assertEqual(distance, {'from': natal, 'to': annual, 'inclusive_sign_count':
                                        (ZODIAC_SIGNS.index(annual) - ZODIAC_SIGNS.index(natal)) % 12 + 1})

    def test_timelines_cover_full_tp_year_without_gaps(self):
        annual = self.result["annual"]
        windows = annual["natal_vimshottari_windows"]
        self.assertEqual(windows[0]["start_utc"], annual["start_utc"])
        self.assertEqual(windows[-1]["end_utc"], annual["end_utc"])
        for a, b in zip(windows, windows[1:]):
            self.assertEqual(a["end_utc"], b["start_utc"])
        schedule = annual["tithi_ashtottari"]
        periods = schedule["periods"]
        self.assertEqual(periods[0]["start_jd"], schedule["tp_start_jd"])
        self.assertEqual(periods[-1]["end_jd"], schedule["tp_end_jd"])
        for a, b in zip(periods, periods[1:]):
            self.assertEqual(a["end_jd"], b["start_jd"])
        for md in periods:
            ads = md["antardashas"]
            self.assertEqual(ads[0]["start_jd"], md["start_jd"])
            self.assertEqual(ads[-1]["end_jd"], md["end_jd"])
            for a, b in zip(ads, ads[1:]):
                self.assertEqual(a["end_jd"], b["start_jd"])

    def test_folder_runs_outside_repository_without_old_modules(self):
        # TemporaryDirectory owns only this newly created synthetic test tree.
        with tempfile.TemporaryDirectory(prefix="astro-engine-isolation-") as tmp:
            copied = Path(tmp) / "Engine"
            shutil.copytree(ENGINE, copied, ignore=shutil.ignore_patterns("__pycache__", ".venv"))
            code = (
                "import json,sys; from pathlib import Path; "
                "sys.path.insert(0, str(Path.cwd()/'Engine')); "
                "from astro_engine import calculate; "
                "r=json.loads(Path('Engine/example.synthetic.json').read_text(encoding='utf-8')); "
                "d=calculate(r); "
                "assert 'database' not in sys.modules; assert 'natal' not in sys.modules; "
                "print(json.dumps({'jd':d['annual']['jd_ut'],'charts':list(d['annual']['charts'])}))"
            )
            run = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", "-c", code],
                                 cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            output = json.loads(run.stdout)
            self.assertEqual(output["charts"], EXAMPLE["allowed_vargas"])
            self.assertAlmostEqual(output["jd"], self.result["annual"]["jd_ut"], places=8)

    def test_cli_never_overwrites_and_invalid_input_has_no_output(self):
        with tempfile.TemporaryDirectory(prefix="astro-engine-cli-") as tmp:
            existing = Path(tmp) / "keep.json"
            existing.write_text("synthetic-original", encoding="utf-8")
            command = [sys.executable, "-B", "-X", "utf8", str(ENGINE / "engine.py"), "--input", "-"]
            run = subprocess.run(command + ["--output", str(existing)], input="{}", capture_output=True,
                                 text=True, encoding="utf-8", timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(existing.read_text(encoding="utf-8"), "synthetic-original")
            new = Path(tmp) / "new.json"
            run = subprocess.run(command + ["--output", str(new)], input="{}", capture_output=True,
                                 text=True, encoding="utf-8", timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(new.exists())


if __name__ == "__main__":
    unittest.main()
