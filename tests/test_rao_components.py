"""Independent examples and edge cases; no client history, network or API calls."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone
import swisseph as swe

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine.arudha import arudha_sign, bhava_arudhas
from astro_engine.core import ChartData
from astro_engine.facts import ZODIAC_SIGNS
from astro_engine.narayana import progression, period_structure, subperiod_order, third_topics, dated_periods
from astro_engine.rasi_rules import (UnresolvedRule, advancement, rasi_aspects,
    stronger_lord, stronger_sign, years_for_lord)
from astro_engine.solar_calendar import SolarArcCalendar
from astro_engine.special_lagnas import hora_ghati_lagnas
from astro_engine.hora_finance import _jd, _sidereal_sun
from astro_engine.solar_calendar import jd_to_utc

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/rao_hora_2003.json').read_text(encoding='utf8'))


def reference(name):
    row = FIXTURES[name]
    return dict(row['d2_signs']), {p: d + m/60 for p, (s,d,m) in row['d1_sign_degree_minute'].items()}


class RasiRulesTests(unittest.TestCase):
    def test_rasi_aspects_symmetry_exclusion_and_dual(self):
        self.assertEqual(rasi_aspects(0), (4, 7, 10))
        self.assertEqual(rasi_aspects(1), (3, 6, 9))
        self.assertEqual(rasi_aspects(2), (5, 8, 11))
        for sign in range(12):
            self.assertEqual(len(rasi_aspects(sign)), 3)
            for other in rasi_aspects(sign):
                self.assertIn(sign, rasi_aspects(other))
        for bad in (True, -1, 12, 1.5):
            with self.assertRaises(ValueError): rasi_aspects(bad)

    def test_arudha_published_examples_and_exceptions(self):
        # Rao section 9.2, Example 29: Vi->Pi, Li->Pi, Cp->Ar, Ge->Pi.
        for origin, lord, expected in [(5,11,2), (6,11,4), (9,0,0), (2,11,5), (0,0,9), (4,11,6)]:
            self.assertEqual(arudha_sign(origin, lord), expected)
        for origin in range(12):
            for lord in range(12):
                self.assertNotIn((arudha_sign(origin, lord) - origin) % 12, (0,6))

    def test_both_published_horas_and_arudhas(self):
        helper = ChartData.__new__(ChartData)
        helper.ZODIAC_SIGNS = ZODIAC_SIGNS
        for name in ('dalmia', 'ntr'):
            row = FIXTURES[name]
            chart, degrees = reference(name)
            for code, (sign, degree, minute) in row['d1_sign_degree_minute'].items():
                actual = helper.calculate_hora_kashinatha_position(sign*30+degree+minute/60, sign, chart['AS'])
                self.assertEqual(ZODIAC_SIGNS.index(actual['zodiac_sign']), chart[code])
            before = deepcopy(chart)
            arudhas = bhava_arudhas(chart, degrees=degrees)
            self.assertEqual(arudhas['AL'], row['AL'])
            self.assertEqual(arudhas['UL'], row['UL'])
            self.assertEqual(chart, before)

    def test_co_lord_own_sign_and_role_count(self):
        chart, deg = reference('dalmia')
        chart['SA'], chart['RA'] = 10, 0
        self.assertEqual(stronger_lord(10, chart, purpose='duration')['winner'], 'RA')
        # Section 15.5.1 example: Mercury counts both as planet and dispositor.
        chart.update(SA=2, ME=2, RA=0, MA=4, JU=1, MO=8, VE=9, SU=11, KE=0)
        result = stronger_lord(10, chart, purpose='arudha', degrees=deg)
        self.assertEqual(result['winner'], 'SA')
        self.assertEqual(result['rule'], 'jupiter_mercury_dispositor_support')
        self.assertEqual(result['comparisons'][-1]['SA'], 2)
        self.assertEqual(result['comparisons'][-1]['RA'], 1)

    def test_node_advancement_and_unresolved_tie(self):
        self.assertAlmostEqual(advancement('KE', {'KE': 5+54/60}), 24.1)
        with self.assertRaises(UnresolvedRule): advancement('MA', None)
        with self.assertRaises(ValueError): advancement('MA', {'MA': math.nan})

    def test_stronger_sign_published_occupancy(self):
        chart, degrees = reference('dalmia')
        result = stronger_sign(8,2,chart,degrees=degrees)
        self.assertEqual(result['winner'], 8)
        self.assertEqual(result['rule'], 'occupants')


class NarayanaTests(unittest.TestCase):
    def test_all_published_progression_rows(self):
        # Rao table 40: normal progressions in zodiac seed order.
        expected = (
            (0,1,2,3,4,5,6,7,8,9,10,11), (1,8,3,10,5,0,7,2,9,4,11,6),
            (2,10,6,5,1,9,8,4,0,11,7,3), (3,2,1,0,11,10,9,8,7,6,5,4),
            (4,9,2,7,0,5,10,3,8,1,6,11), (5,9,1,2,6,10,11,3,7,8,0,4),
            (6,7,8,9,10,11,0,1,2,3,4,5), (7,2,9,4,11,6,1,8,3,10,5,0),
            (8,4,0,11,7,3,2,10,6,5,1,9), (9,8,7,6,5,4,3,2,1,0,11,10),
            (10,3,8,1,6,11,4,9,2,7,0,5), (11,3,7,8,0,4,5,9,1,2,6,10))
        for seed in range(12):
            chart = {'SA': (seed+1)%12, 'KE': (seed+2)%12}
            self.assertEqual(progression(seed,chart)['signs'], list(expected[seed]))
            chart['SA'] = seed
            self.assertEqual(progression(seed,chart)['signs'], [(seed+i)%12 for i in range(12)])
            chart['SA'],chart['KE'] = (seed+1)%12,seed
            self.assertEqual(progression(seed,chart)['signs'], [(2*seed-i)%12 for i in expected[seed]])
            chart['SA'] = seed
            with self.assertRaises(UnresolvedRule): progression(seed,chart)

    def test_dalmia_full_reference_table_and_second_cycle(self):
        chart,degrees = reference('dalmia')
        result = period_structure(chart, reference_sign=chart['ME'], degrees=degrees)
        self.assertEqual([p['sign'] for p in result['periods'][:12]], FIXTURES['dalmia']['md_signs'])
        actual = [p['years'] for p in result['periods'][:12]]
        self.assertEqual(actual, FIXTURES['dalmia']['md_years'])
        for a,b in zip(result['periods'][:12], result['periods'][12:]):
            self.assertEqual(a['years']+b['years'],12)
        self.assertEqual(result['periods'][-1]['end_year'],144)

    def test_ntr_published_periods_use_article_mars_seed_and_saturn_exception(self):
        chart,degrees=reference('ntr')
        result=period_structure(chart,reference_sign=chart['MA'],degrees=degrees)
        self.assertEqual(result['progression']['exception'],'saturn')
        for source in FIXTURES['ntr']['narrative_periods']:
            row=next(p for p in result['periods'][:12] if p['sign']==source['sign'])
            self.assertEqual(1923+row['start_year'],source['start_year'])
            self.assertEqual(1923+row['end_year'],source['end_year'])

    def test_published_dalmia_solar_boundaries(self):
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        chart, degrees = reference('dalmia')
        structure = period_structure(chart, reference_sign=chart['ME'], degrees=degrees)
        expected = FIXTURES['dalmia']['md_local_boundaries']
        calendar = SolarArcCalendar(_jd(expected[0]), _sidereal_sun)
        offsets = [0] + [p['end_year'] for p in structure['periods'][:12]]
        for years, source in zip(offsets, expected):
            actual = datetime.fromisoformat(jd_to_utc(calendar.at_years(years)))
            error = abs((actual - datetime.fromisoformat(source).astimezone(timezone.utc)).total_seconds())
            # Old publication/program settings are not fully specified: agreement
            # within 30 s is a reference comparison, not sub-second validation.
            self.assertLess(error, 30, (years, source, error))

    def test_solar_calendar_rejects_invalid_longitudes_and_offsets(self):
        for invalid in (math.nan, math.inf):
            with self.assertRaises(ValueError): SolarArcCalendar(2451545, lambda _: invalid)
        calendar = SolarArcCalendar(2451545, lambda jd: ((jd-2451545)*360/365.25636)%360)
        for invalid in (True, -1, 145, math.nan):
            with self.assertRaises(ValueError): calendar.at_years(invalid)

    def test_zero_period_is_preserved_in_structure(self):
        chart,_=reference('dalmia'); chart['JU']=9
        self.assertEqual(years_for_lord(8,'JU',chart),0)
        chart['JU']=8
        self.assertEqual(years_for_lord(8,'JU',chart),12)

    def test_own_exalted_mercury_is_twelve_not_thirteen_years(self):
        # Explicit exception 3(b), Rath 2004, printed p.40.
        chart, degrees = reference('dalmia')
        chart['ME'] = 5
        self.assertEqual(years_for_lord(5, 'ME', chart), 12)
        result = period_structure(chart, reference_sign=5, degrees=degrees)
        periods = [p for p in result['periods'] if p['sign'] == 5]
        self.assertEqual([p['years'] for p in periods], [12, 0])

    def test_subperiods_equal_solar_arcs_and_window_coverage(self):
        chart,deg=reference('dalmia')
        structure=period_structure(chart,reference_sign=8,degrees=deg)
        # Deliberately nonuniform, monotonic apparent Sun simulation.
        def longitude(jd):
            t=(jd-2451545)/365.25636
            return (100+360*t+1.5*math.sin(2*math.pi*t))%360
        calendar=SolarArcCalendar(2451545,longitude)
        start,end=calendar.at_years(30),calendar.at_years(31)
        result=dated_periods(structure,chart,calendar,window=(start,end),degrees=deg)
        leaves=[p for m in result['periods'] for a in m['antardasas'] for p in a['pratyantardasas']]
        self.assertEqual(leaves[0]['window_start_utc'],result['window_start_utc'])
        self.assertEqual(leaves[-1]['window_end_utc'],result['window_end_utc'])
        for a,b in zip(leaves,leaves[1:]):
            self.assertEqual(a['window_end_utc'],b['window_start_utc'])
        self.assertNotAlmostEqual(calendar.at_years(.25)-calendar.at_years(0),
                                  calendar.at_years(.5)-calendar.at_years(.25),places=3)
        for years in (.25, .5, 11, 35.37, 120):
            residual=(longitude(calendar.at_years(years))-100-360*years+180)%360-180
            self.assertAlmostEqual(residual,0,places=6)

    def test_thirds_and_requested_reference_are_explicit(self):
        self.assertEqual(third_topics(11),('occupants_and_aspectors','house','lord'))
        self.assertEqual(third_topics(0),('occupants_and_aspectors','lord','house'))
        self.assertEqual(third_topics(4),('house','lord','occupants_and_aspectors'))
        chart,deg=reference('dalmia')
        a=period_structure(chart,reference_sign=8,degrees=deg)
        b=period_structure(chart,reference_sign=chart['AS'],degrees=deg)
        self.assertNotEqual(a['seed_sign'],b['seed_sign'])


class SpecialLagnaTests(unittest.TestCase):
    def test_textbook_examples_8_and_9(self):
        # Sunrise 06:37, birth 19:23, Sun at Capricorn 24deg47.
        result=hora_ghati_lagnas(moment_jd=100+766/1440,sunrise_jd=100,
            next_sunrise_jd=101,sun_longitude_at_sunrise=294+47/60)
        self.assertAlmostEqual(result['HL'],317+47/60)
        # The book prints Virgo 21deg17, but its formula/input give 22deg17.
        self.assertAlmostEqual(result['GL'],172+17/60)

    def test_before_sunrise_requires_previous_sunrise(self):
        with self.assertRaises(ValueError):
            hora_ghati_lagnas(moment_jd=100.9,sunrise_jd=101,next_sunrise_jd=102,sun_longitude_at_sunrise=0)
        result=hora_ghati_lagnas(moment_jd=100.9,sunrise_jd=100,next_sunrise_jd=101,sun_longitude_at_sunrise=0)
        self.assertAlmostEqual(result['elapsed_minutes'],1296)


if __name__ == '__main__': unittest.main()
