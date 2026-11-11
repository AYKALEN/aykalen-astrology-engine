"""Independent reference tables (Rao 6.2.5–6.2.6), no API/network calls."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine.core import ChartData
from astro_engine.facts import ZODIAC_SIGNS


class D5D6Tests(unittest.TestCase):
    ROWS = {
        5: (("Baran", "Wodnik", "Strzelec", "Bliźnięta", "Waga"),
            ("Byk", "Panna", "Ryby", "Koziorożec", "Skorpion")),
        6: (("Baran", "Byk", "Bliźnięta", "Rak", "Lew", "Panna"),
            ("Waga", "Skorpion", "Strzelec", "Koziorożec", "Wodnik", "Ryby")),
    }

    def setUp(self):
        self.chart = ChartData.__new__(ChartData)
        self.chart.ZODIAC_SIGNS = ZODIAC_SIGNS
        self.functions = {5: self.chart.calculate_panchamsa_position,
                          6: self.chart.calculate_shashtamsa_position}

    def test_all_parts_all_signs_and_houses(self):
        for count, function in self.functions.items():
            for sign in range(12):
                for part, expected in enumerate(self.ROWS[count][sign % 2]):
                    actual = function(sign * 30 + (part + .5) * 30 / count, sign, 4)
                    self.assertEqual(actual['zodiac_sign'], expected)
                    self.assertEqual(actual['house'], (ZODIAC_SIGNS.index(expected) - 4) % 12 + 1)

    def test_every_boundary_and_adjacent_float(self):
        for count, function in self.functions.items():
            for sign in range(12):
                row = self.ROWS[count][sign % 2]
                for part in range(1, count):
                    boundary = sign * 30 + part * 30 / count
                    for degree, expected in ((math.nextafter(boundary, -math.inf), row[part - 1]),
                                             (boundary, row[part]),
                                             (math.nextafter(boundary, math.inf), row[part])):
                        self.assertEqual(function(degree, sign, 0)['zodiac_sign'], expected)
                self.assertEqual(function(sign * 30, sign, 0)['zodiac_sign'], row[0])
                self.assertEqual(function(math.nextafter((sign + 1) * 30, -math.inf), sign, 0)['zodiac_sign'], row[-1])
            self.assertEqual(function(360, 12, 0)['zodiac_sign'], 'Baran')

    def test_published_d6_example_13(self):
        self.assertEqual(self.functions[6](71, 2, 0)['zodiac_sign'], 'Bliźnięta')
        self.assertEqual(self.functions[6](229, 7, 0)['zodiac_sign'], 'Koziorożec')

    def test_precise_longitudes_and_alternate_nodes(self):
        for count, function in self.functions.items():
            boundary = 30 / count
            raw = {'AS': {'position_degrees_exact': 14., 'position_degrees': 14.}}
            for code, offset in (('RA', 0), ('KE', 180)):
                raw[code] = {'position_degrees_exact': boundary + offset - .00001,
                             'position_degrees': boundary + offset,
                             'position_degrees_mean_node': boundary + offset + .00001}
            before = deepcopy(raw)
            result = self.chart._build_divisional_chart(function, raw)
            self.assertEqual(result['AS']['house'], 1)
            for code in ('RA', 'KE'):
                self.assertEqual(result[code]['zodiac_sign'], 'Baran')
                self.assertEqual(result[code]['node_alt_sign'], self.ROWS[count][0][1])
                self.assertTrue(result[code]['node_ambiguous'])
            self.assertEqual(raw, before)
