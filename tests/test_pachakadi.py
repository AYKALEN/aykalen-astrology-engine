"""Published table rows and Hora examples; no financial-history fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from astro_engine.pachakadi import pachakadi_relations, VARIANT


def example():
    return json.loads((Path(__file__).parent/'fixtures/rao_hora_2003.json').read_text(encoding='utf8'))['dalmia']['d2_signs']


class PachakadiTests(unittest.TestCase):
    def test_source_tables_55_56_all_rows(self):
        # Hand-transcribed as printed, Rath v3/2004 pp.191-192.
        rows={
            'SU': [('SA',6),('MA',7),('JU',9),('VE',11)],
            'MO': [('VE',7),('MA',9),('SA',11),('SU',3)],
            'MA': [('SU',2),('MO',6),('SA',11),('ME',12)],
            'ME': [('MO',2),('JU',4),('VE',5),('MA',3)],
            'JU': [('SA',6),('MA',5),('MO',7),('SU',12)],
            'VE': [('MO',2),('ME',6),('SA',12),('SU',4)],
            'SA': [('VE',3),('MO',11),('JU',6),('MA',7)]}
        result=pachakadi_relations(example(),variant=VARIANT)
        for subject, expected in rows.items():
            actual=result['subjects'][subject]['roles']
            for role, (natural,house) in zip(('pachaka','bodhaka','karaka','vedhaka'),expected):
                self.assertEqual((actual[role]['natural_planet'],actual[role]['positional']['house_from_subject']),(natural,house))

    def test_rao_hora_published_obstructions_and_karaka_sthana(self):
        result=pachakadi_relations(example(),variant=VARIANT)['subjects']
        self.assertEqual(result['SA']['roles']['vedhaka']['natural_planet'],'MA')
        self.assertEqual(result['ME']['roles']['vedhaka']['natural_planet'],'MA')
        self.assertEqual(result['JU']['roles']['karaka']['positional']['sign'],1) # Taurus
        self.assertIn('MA',result['JU']['roles']['karaka']['positional']['planets'])

    def test_natural_and_positional_are_independent_and_directed(self):
        chart=example(); chart.update(VE=0, ME=5, RA=5, KE=5)
        before=deepcopy(chart)
        result=pachakadi_relations(chart,variant=VARIANT)['subjects']
        row=result['VE']['roles']['bodhaka']
        self.assertTrue(row['natural_also_positional'])
        self.assertEqual(set(row['positional']['planets']),{'ME','RA','KE','SA'})
        self.assertNotEqual(result['ME']['roles']['bodhaka']['natural_planet'],'VE')
        self.assertNotIn('RA',result)
        self.assertEqual(chart,before)
        chart['ME']=4
        row=pachakadi_relations(chart,variant=VARIANT)['subjects']['VE']['roles']['bodhaka']
        self.assertEqual(row['natural_planet'],'ME')
        self.assertFalse(row['natural_also_positional'])

    def test_house_count_wrap_and_empty_positions(self):
        chart={p:11 for p in example()}
        result=pachakadi_relations(chart,variant=VARIANT)['subjects']
        for row in result.values():
            for role in row['roles'].values():
                self.assertEqual(role['positional']['planets'],[])
        self.assertEqual(result['ME']['roles']['pachaka']['positional']['sign'],0)

    def test_table_57_is_distinct_from_vedhaka_and_moon_has_no_natural_enemy(self):
        rows=pachakadi_relations(example(),variant=VARIANT)['subjects']
        self.assertIsNone(rows['MO']['inimical_table_57']['natural_planet'])
        self.assertEqual(rows['MO']['inimical_table_57']['positional']['house_from_subject'],12)
        self.assertEqual(rows['MO']['roles']['vedhaka']['natural_planet'],'SU')
        self.assertEqual(rows['JU']['inimical_table_57']['role'],'pachaka')
        self.assertEqual(rows['SA']['inimical_table_57']['role'],'karaka')

    def test_explicit_variant_and_invalid_chart(self):
        with self.assertRaises(TypeError): pachakadi_relations(example())
        with self.assertRaises(ValueError): pachakadi_relations(example(),variant='automatic')
        for code,value in [('SU',12),('AS',True)]:
            chart=example();chart[code]=value
            with self.assertRaises(ValueError): pachakadi_relations(chart,variant=VARIANT)


if __name__=='__main__':unittest.main()
