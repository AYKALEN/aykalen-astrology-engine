"""Kāśinātha Hora: published examples, all 24 halves and export boundaries.

Reference: P.V.R. Narasimha Rao, Personal Finances from Hora Chart, pp. 1–3,
https://www.vedicastrologer.org/articles/hora.pdf. No network or personal data.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine import calculate
from astro_engine.core import ChartData
from astro_engine.facts import ZODIAC_SIGNS


class KashinathaTests(unittest.TestCase):
    # Reference results for the first and second halves, in D1 zodiac order.
    ROWS = (
        ('Skorpion', 'Baran'), ('Byk', 'Waga'), ('Panna', 'Bliźnięta'),
        ('Rak', 'Lew'), ('Lew', 'Rak'), ('Bliźnięta', 'Panna'),
        ('Waga', 'Byk'), ('Baran', 'Skorpion'), ('Ryby', 'Strzelec'),
        ('Koziorożec', 'Wodnik'), ('Wodnik', 'Koziorożec'), ('Strzelec', 'Ryby'),
    )

    def setUp(self):
        self.chart = ChartData.__new__(ChartData)
        self.chart.ZODIAC_SIGNS = ZODIAC_SIGNS
        self.position = self.chart.calculate_hora_kashinatha_position

    def test_all_24_halves_and_all_ascendants(self):
        for sign, row in enumerate(self.ROWS):
            for half, expected in enumerate(row):
                for ascendant in range(12):
                    with self.subTest(sign=sign, half=half, ascendant=ascendant):
                        actual = self.position(sign * 30 + half * 15 + 7.5, sign, ascendant)
                        self.assertEqual(actual['zodiac_sign'], expected)
                        self.assertEqual(actual['house'],
                                         (ZODIAC_SIGNS.index(expected) - ascendant) % 12 + 1)

    def test_boundaries_and_adjacent_floats_without_rounding(self):
        for sign, row in enumerate(self.ROWS):
            boundary = sign * 30 + 15
            for degree, expected in (
                (sign * 30, row[0]),
                (math.nextafter(boundary, -math.inf), row[0]),
                (boundary, row[1]),
                (math.nextafter(boundary, math.inf), row[1]),
                (math.nextafter((sign + 1) * 30, -math.inf), row[1]),
            ):
                with self.subTest(sign=sign, degree=degree):
                    self.assertEqual(self.position(degree, sign, 0)['zodiac_sign'], expected)
        self.assertEqual(self.position(360, 12, 0)['zodiac_sign'], 'Skorpion')

    def test_published_examples_and_luminary_pair(self):
        # Rao: Jupiter at Taurus 25°16' -> Libra; Mars at Sagittarius 18°53' -> Sagittarius.
        self.assertEqual(self.position(30 + 25 + 16/60, 1, 0)['zodiac_sign'], 'Waga')
        self.assertEqual(self.position(240 + 18 + 53/60, 8, 0)['zodiac_sign'], 'Strzelec')
        self.assertEqual(self.position(95, 3, 0)['zodiac_sign'], 'Rak')
        self.assertEqual(self.position(110, 3, 0)['zodiac_sign'], 'Lew')
        self.assertEqual(self.position(125, 4, 0)['zodiac_sign'], 'Lew')
        self.assertEqual(self.position(140, 4, 0)['zodiac_sign'], 'Rak')

    def test_exact_nodes_and_alternate_nodes_do_not_mutate_input(self):
        raw = {'AS': {'position_degrees_exact': 61.0}}
        for code, offset in (('RA', 0), ('KE', 180)):
            raw[code] = {'position_degrees_exact': 75 + offset - .00001,
                         'position_degrees': 75 + offset,
                         'position_degrees_mean_node': 75 + offset + .00001}
        before = deepcopy(raw)
        result = self.chart._build_divisional_chart(self.position, raw)
        self.assertEqual(result['AS'], {'zodiac_sign': 'Panna', 'house': 1})
        for code, expected, alternate in (('RA', 'Panna', 'Bliźnięta'),
                                           ('KE', 'Ryby', 'Strzelec')):
            self.assertEqual(result[code]['zodiac_sign'], expected)
            self.assertEqual(result[code]['node_alt_sign'], alternate)
            self.assertTrue(result[code]['node_ambiguous'])
            self.assertNotEqual(result[code]['house'], result[code]['node_alt_house'])
        self.assertEqual(raw, before)

    def test_supplied_tp_data_is_independent_of_natal_state_and_other_horas(self):
        self.chart.detailed_chart_data = {'AS': {'position_degrees_exact': 35},
                                          'SU': {'position_degrees_exact': 148}}
        before = deepcopy(self.chart.detailed_chart_data)
        natal = self.chart.calculate_hora_kashinatha_chart()
        tp = {'AS': {'position_degrees_exact': 61}, 'SU': {'position_degrees_exact': 148}}
        annual = self.chart._build_divisional_chart(self.position, tp)
        self.assertEqual(natal['AS']['zodiac_sign'], 'Byk')
        self.assertEqual(annual['AS']['zodiac_sign'], 'Panna')
        self.assertEqual(annual['SU']['house'], 11)
        self.assertEqual(self.chart.detailed_chart_data, before)
        self.assertEqual(self.chart.calculate_hora_chart()['AS']['zodiac_sign'], 'Rak')
        self.assertEqual(self.chart.calculate_hora_parivritti_chart()['AS']['zodiac_sign'], 'Bliźnięta')

    def test_public_api_exports_named_variant_without_changing_existing_outputs(self):
        request = json.loads((Path(__file__).resolve().parents[1] / 'example.synthetic.json')
                             .read_text(encoding='utf8'))
        request['allowed_vargas'] = ['D1', 'D2_parashara', 'D2_parivritti', 'D2_kashinatha']
        result = calculate(request)
        self.assertIn('Kashinatha Hora', result['calculation_profile']['varga_methods']['D2_kashinatha'])
        for section in ('natal', 'annual'):
            chart = result[section]['charts']['D2_kashinatha']
            self.assertEqual(set(chart['positions']), {'AS','SU','MO','ME','VE','MA','JU','SA','RA','KE'})
            self.assertEqual(len(chart['house_lords']), 12)
            self.assertEqual(len(chart['aspects']), 7)
            for body in chart['positions'].values():
                self.assertIn('dispositor', body)
                self.assertIn('rules_houses', body)
                self.assertNotIn('position_within_sign_degrees', body)
        relation = result['annual']['lagna_distances']['charts']['D2_kashinatha']
        self.assertEqual(relation['inclusive_sign_count'],
                         (ZODIAC_SIGNS.index(relation['to']) - ZODIAC_SIGNS.index(relation['from'])) % 12 + 1)
        request['allowed_vargas'].remove('D2_kashinatha')
        legacy = calculate(request)
        del result['calculation_profile']['varga_methods']
        result['scope']['exported_vargas'].remove('D2_kashinatha')
        for section in ('natal', 'annual'):
            del result[section]['charts']['D2_kashinatha']
        del result['annual']['lagna_distances']['charts']['D2_kashinatha']
        self.assertEqual(result, legacy)
