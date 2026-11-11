"""Offline reference tables and boundary checks for the two added vargas."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine.core import ChartData
from astro_engine.facts import ZODIAC_SIGNS


class AdditionalVargaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These functions need longitudes and signs, not another ephemeris run.
        cls.chart = ChartData.__new__(ChartData)
        cls.chart.ZODIAC_SIGNS = ZODIAC_SIGNS

    D8_ROWS = (
        ('Baran', 'Byk', 'Bliźnięta', 'Rak', 'Lew', 'Panna', 'Waga', 'Skorpion'),
        ('Strzelec', 'Koziorożec', 'Wodnik', 'Ryby', 'Baran', 'Byk', 'Bliźnięta', 'Rak'),
        ('Lew', 'Panna', 'Waga', 'Skorpion', 'Strzelec', 'Koziorożec', 'Wodnik', 'Ryby'),
    )
    IYER_ROW = ('Baran', 'Ryby', 'Wodnik', 'Koziorożec', 'Strzelec', 'Skorpion',
                'Waga', 'Panna', 'Lew', 'Rak', 'Bliźnięta')

    def test_d8_all_parts_in_every_sign(self):
        for sign in range(12):
            for part, expected in enumerate(self.D8_ROWS[sign % 3]):
                with self.subTest(sign=sign, part=part):
                    degree = 30 * sign + (part + .5) * 3.75
                    actual = self.chart.calculate_ashtamsa_position(degree, sign, 6)
                    self.assertEqual(actual['zodiac_sign'], expected)
                    self.assertEqual(actual['house'], (ZODIAC_SIGNS.index(expected) - 6) % 12 + 1)

    def test_iyer_all_parts_independent_of_d1_sign_and_no_taurus(self):
        for sign in range(12):
            for part, expected in enumerate(self.IYER_ROW):
                with self.subTest(sign=sign, part=part):
                    degree = 30 * sign + 30 * (part + .5) / 11
                    actual = self.chart.calculate_ekadasamsa_iyer_position(degree, sign, 8)
                    self.assertEqual(actual['zodiac_sign'], expected)
                    self.assertNotEqual(actual['zodiac_sign'], 'Byk')
                    self.assertEqual(actual['house'], (ZODIAC_SIGNS.index(expected) - 8) % 12 + 1)

    def test_documented_examples_distinguish_iyer_from_other_d11(self):
        d8 = self.chart.calculate_ashtamsa_position
        d11 = self.chart.calculate_ekadasamsa_iyer_position
        self.assertEqual(d8(70, 2, 0)['zodiac_sign'], 'Waga')  # 10° Gemini
        self.assertEqual(d8(229, 7, 0)['zodiac_sign'], 'Byk')  # 19° Scorpio
        self.assertEqual(d11(71, 2, 0)['zodiac_sign'], 'Strzelec')  # 11° Gemini, not Gemini
        self.assertEqual(d11(229, 7, 0)['zodiac_sign'], 'Waga')  # 19° Scorpio, not Pisces

    def test_every_boundary_belongs_to_next_part_without_epsilon(self):
        for count, function in ((8, self.chart.calculate_ashtamsa_position),
                                (11, self.chart.calculate_ekadasamsa_iyer_position)):
            for sign in range(12):
                row = self.D8_ROWS[sign % 3] if count == 8 else self.IYER_ROW
                for part in range(1, count):
                    boundary = sign * 30 + 30 * part / count
                    for degree, expected in ((math.nextafter(boundary, -math.inf), row[part - 1]),
                                             (boundary, row[part]),
                                             (math.nextafter(boundary, math.inf), row[part])):
                        with self.subTest(count=count, sign=sign, boundary=boundary, degree=degree):
                            self.assertEqual(function(degree, sign, 0)['zodiac_sign'], expected)

    def test_sign_and_zodiac_boundaries(self):
        for count, function in ((8, self.chart.calculate_ashtamsa_position),
                                (11, self.chart.calculate_ekadasamsa_iyer_position)):
            for sign in range(12):
                row = self.D8_ROWS[sign % 3] if count == 8 else self.IYER_ROW
                self.assertEqual(function(sign * 30, sign, 0)['zodiac_sign'], row[0])
                self.assertEqual(function(math.nextafter((sign + 1) * 30, -math.inf), sign, 0)
                                 ['zodiac_sign'], row[-1])
            self.assertEqual(function(360, 12, 0)['zodiac_sign'], 'Baran')

    def test_exact_source_nodes_and_alternate_variant_are_preserved(self):
        for count, function, expected, alternate in (
            (8, self.chart.calculate_ashtamsa_position, 'Lew', 'Panna'),
            (11, self.chart.calculate_ekadasamsa_iyer_position, 'Baran', 'Ryby'),
        ):
            boundary = 60 + 30 / count
            raw = {'AS': {'position_degrees_exact': 71.0, 'position_degrees': 71.0}}
            for code, offset in (('RA', 0), ('KE', 180)):
                degree = boundary + offset - .00001
                raw[code] = {'position_degrees_exact': degree, 'position_degrees': round(degree, 2),
                             'position_degrees_mean_node': boundary + offset + .00001}
            before = deepcopy(raw)
            result = self.chart._build_divisional_chart(function, raw)
            self.assertEqual(raw, before)
            self.assertEqual(result['AS']['house'], 1)
            for code in ('RA', 'KE'):
                self.assertEqual(result[code]['zodiac_sign'], expected)
                self.assertTrue(result[code]['node_ambiguous'])
                self.assertEqual(result[code]['node_alt_sign'], alternate)
                self.assertNotEqual(result[code]['house'], result[code]['node_alt_house'])
            # Both mappings legitimately put opposite D1 nodes in the same varga sign.
            self.assertEqual(result['RA'], result['KE'])

    def test_builds_from_supplied_tp_data_without_changing_natal_data(self):
        chart = deepcopy(self.chart)
        chart.detailed_chart_data = {'AS': {'position_degrees_exact': 71},
                                     'SU': {'position_degrees_exact': 229}}
        natal = deepcopy(chart.detailed_chart_data)
        tp = {'AS': {'position_degrees_exact': 1}, 'SU': {'position_degrees_exact': 71}}
        for function in (chart.calculate_ashtamsa_position, chart.calculate_ekadasamsa_iyer_position):
            self.assertNotEqual(chart._build_divisional_chart(function),
                                chart._build_divisional_chart(function, tp))
        self.assertEqual(chart.detailed_chart_data, natal)


if __name__ == '__main__':
    unittest.main()
