"""Synthetic, offline regression vectors for extracted calculation helpers."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astro_engine import facts, shadbala, timing, vimsopaka


def body(sign, house, longitude=0.0, **extra):
    return {"zodiac_sign": sign, "house": house,
            "position_degrees": round(longitude, 2),
            "position_degrees_exact": longitude, **extra}


class FactsTests(unittest.TestCase):
    def test_house_lords_and_rules(self):
        chart = {"AS": body("Baran", 1), "MA": body("Rak", 4, 92)}
        rows = facts.house_lords_rows(chart)
        self.assertEqual(len(rows), 12)
        self.assertEqual((rows[0]["lord"], rows[0]["lord_house"]), ("MA", 4))
        self.assertEqual(facts.rules_houses("MA", chart), [1, 8])
        self.assertEqual(facts.rules_houses("RA", chart), [])

    def test_chart_projection_keeps_exact_and_node_alternate(self):
        source = {"RA": body("Baran", 1, 29.99999, node_ambiguous=True,
                              node_alt_sign="Byk", node_alt_house=2)}
        projected = facts.chart_dict_from_detailed(source)["RA"]
        self.assertEqual(projected["position_degrees_exact"], 29.99999)
        self.assertEqual(projected["node_alt_sign"], "Byk")
        self.assertEqual(projected["node_alt_house"], 2)

    def test_dignities_are_sign_only_unless_degrees_supplied(self):
        self.assertEqual(facts.sign_dignity("SU", "Lew"), "własny znak")
        self.assertEqual(facts.sign_dignity("SU", "Lew", 19.999),
                         "mūlatrikoṇa + własny znak")
        self.assertEqual(facts.sign_dignity("SU", "Lew", 20), "własny znak")
        self.assertEqual(facts.sign_dignity("SU", "Waga"), "upadek")
        self.assertEqual(facts.sign_dignity("MA", "Rak"), "upadek")

    def test_aspects_whole_sign_no_node_aspect(self):
        chart = {"MA": body("Baran", 1), "JU": body("Lew", 5),
                 "RA": body("Rak", 4), "MO": body("Waga", 7)}
        rows = facts.aspects_for_chart(chart)
        mars = next(row for row in rows if row["planet"] == "MA")
        self.assertEqual([r["house"] for r in mars["targets"]], [4, 7, 8])
        self.assertIn("RA", mars["targets"][0]["occupants"])
        self.assertNotIn("RA", [row["planet"] for row in rows])

    def test_conjunctions_use_exact_positions_and_same_sign(self):
        chart = {"MA": body("Baran", 1, 29.999),
                 "JU": body("Byk", 2, 30.001),
                 "VE": body("Baran", 1, 28.9991)}
        rows = facts.conjunctions_d1(chart)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["orb"], 0.9999)
        self.assertAlmostEqual(facts.angular_sep(359, 1), 2)

    def test_legacy_combustion_boundary_remains_profiled(self):
        chart = {"SU": body("Baran", 1), "ME": body("Baran", 1, 14.00001)}
        self.assertFalse(facts.combustion_rows(chart)[0]["combust"])
        chart["ME"]["position_degrees_exact"] = 14.0
        self.assertTrue(facts.combustion_rows(chart)[0]["combust"])
        self.assertIn("LEGACY", facts.OPTIONAL_LEGACY_PROFILES["combustion"])

    def test_legacy_yuddha_does_not_cross_sign_boundary(self):
        chart = {"MA": body("Baran", 1, 29.9), "VE": body("Byk", 2, 30.1)}
        self.assertEqual(facts.graha_yuddha_rows(chart), [])
        chart["VE"] = body("Baran", 1, 29.8)
        self.assertEqual(facts.graha_yuddha_rows(chart)[0]["winner"], "VE")

    def test_nica_bhanga_is_optional_pattern_helper(self):
        chart = {"AS": body("Baran", 1), "SU": body("Waga", 7, 190),
                 "VE": body("Lew", 5, 130)}
        hits = facts.detect_nica_bhanga_for_planet("SU", chart)
        self.assertIn("parivartana_nica", [h["typ"] for h in hits])
        self.assertEqual(facts.detect_nica_bhanga_for_planet("VE", chart), [])


class TimingTests(unittest.TestCase):
    @staticmethod
    def chart():
        return SimpleNamespace(utc_date="2000-01-01", calc_time="12:00:00",
                               detailed_chart_data={"MO": body("Baran", 1, 0.0)})

    def test_nine_md_cycle_and_exact_utc_endpoint_continuity(self):
        periods = timing.unfiltered_vimshottari(self.chart(), include_timestamps=True)
        self.assertEqual(len(periods), 9)
        self.assertEqual(periods[0]["mahadasha_lord"], "KE")
        self.assertEqual(periods[0]["start_utc"], "2000-01-01T12:00:00+00:00")
        for parent in periods:
            ads = parent["antardashas"]
            self.assertEqual(ads[0]["start_utc"], parent["start_utc"])
            self.assertEqual(ads[-1]["end_utc"], parent["end_utc"])
            for ad in ads:
                pds = ad["pratyantardashas"]
                self.assertEqual(pds[0]["start_utc"], ad["start_utc"])
                self.assertEqual(pds[-1]["end_utc"], ad["end_utc"])
                for left, right in zip(pds, pds[1:]):
                    self.assertEqual(left["end_utc"], right["start_utc"])
            for left, right in zip(ads, ads[1:]):
                self.assertEqual(left["end_utc"], right["start_utc"])
        for left, right in zip(periods, periods[1:]):
            self.assertEqual(left["end_utc"], right["start_utc"])

    def test_first_balance_convention_is_preserved_and_explicit(self):
        chart = self.chart()
        chart.detailed_chart_data["MO"]["position_degrees_exact"] = (13 + 1 / 3) / 2
        first = timing.unfiltered_vimshottari(chart, include_timestamps=True)[0]
        start = datetime.fromisoformat(first["start_utc"])
        end = datetime.fromisoformat(first["end_utc"])
        self.assertAlmostEqual((end-start).total_seconds()/86400, 3.5*365.25)
        ad = first["antardashas"][0]
        ad_days = (datetime.fromisoformat(ad["end_utc"])-start).total_seconds()/86400
        self.assertAlmostEqual(ad_days, 3.5*365.25*7/120)
        self.assertEqual(timing.VIMSHOTTARI_PROFILE["first_md_subdivision"],
                         "remaining_balance_proportional_from_birth")

    def test_date_only_compatibility_does_not_emit_timestamps(self):
        first = timing.unfiltered_vimshottari(self.chart())[0]
        self.assertNotIn("start_utc", first)
        self.assertEqual(first["start"], "01-01-2000")


class BalaTests(unittest.TestCase):
    def test_partial_shadbala_has_no_full_total(self):
        longitudes = {p: index * 35.0 for index, p in enumerate(shadbala.CLASSICAL_PLANETS)}
        result = shadbala.component_snapshot(longitudes, 0.0)
        self.assertEqual(result["full_shadbala_status"], "INCOMPLETE")
        self.assertFalse(result["full_shadbala_publishable"])
        self.assertEqual(result["missing_runtime_components"], ["sthana", "kala", "cheshta"])
        self.assertEqual(result["naisargika"]["SU"]["value"], 60)
        self.assertIsNone(result["drik"]["SU"]["value"])

    def test_shadbala_aggregation_gates_missing_and_complete_inputs(self):
        incomplete = shadbala.aggregate_shadbala("SU", {"dig": 60})
        self.assertEqual(incomplete["status"], "INCOMPLETE")
        self.assertIsNone(incomplete["value"])
        complete = shadbala.aggregate_shadbala("SU", {key: 60 for key in shadbala.REQUIRED_COMPONENTS})
        self.assertEqual(complete["status"], "GATED")
        self.assertIsNone(complete["value"])

    def test_vimsopaka_weights_and_missing_data_remain_visible(self):
        for name, weights in vimsopaka.WEIGHTS.items():
            self.assertEqual(sum(weight for _, weight in weights),
                             21 if name == "dashavarga" else 20)
        score = vimsopaka.score_planet_system("SU", {"D1": {"SU": body("Lew", 1, 130)}}, "shadvarga")
        self.assertIsNone(score["score"])
        self.assertEqual(score["diagnostic_partial_sum"], 6.0)
        self.assertEqual(score["status"], "INCOMPLETE")
        self.assertFalse(score["complete"])
        self.assertIn("D2", score["missing_vargas"])
        self.assertIsNone(vimsopaka.dignity_factor("RA", "Baran"))

    def test_vimsopaka_invalid_legacy_weight_profile_cannot_emit_score(self):
        pack = {varga: {"SU": body("Lew", 1, 130)}
                for varga, _ in vimsopaka.WEIGHTS["dashavarga"]}
        score = vimsopaka.score_planet_system("SU", pack, "dashavarga")
        self.assertEqual(score["weight_sum"], 21.0)
        self.assertEqual(score["status"], "UNRESOLVED")
        self.assertEqual(score["reason"], "invalid_weight_sum")
        self.assertIsNone(score["score"])
        self.assertTrue(score["complete"])

    def test_vimsopaka_complete_supported_weight_profile(self):
        pack = {varga: {"SU": body("Lew", 1, 130)}
                for varga, _ in vimsopaka.WEIGHTS["shadvarga"]}
        score = vimsopaka.score_planet_system("SU", pack, "shadvarga")
        self.assertEqual(score["score"], 20)
        self.assertEqual(score["status"], "CALCULATED_SIMPLIFIED")


if __name__ == "__main__":
    unittest.main()
