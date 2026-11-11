"""Optional research extension isolation and error contract."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from astro_engine import calculate
from astro_engine.hora_finance import TECHNIQUE_ID


class RaoApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request=json.loads((Path(__file__).resolve().parents[1]/'example.synthetic.json').read_text(encoding='utf8'))
        cls.request['allowed_vargas']=['D1','D2_kashinatha']
        cls.baseline=calculate(cls.request)
        request=deepcopy(cls.request)
        request['techniques']=[TECHNIQUE_ID]
        cls.before=deepcopy(request)
        cls.research=calculate(request)
        cls.after=request

    def test_legacy_output_unchanged_when_extension_selected(self):
        result=deepcopy(self.research)
        self.assertIn('techniques',result)
        del result['techniques']
        self.assertEqual(result,self.baseline)
        self.assertEqual(self.after,self.before)

    def test_natal_scope_and_explicit_interval_qualification(self):
        packet=self.research['techniques'][TECHNIQUE_ID]
        self.assertFalse(packet['ready_for_interpretation'])
        self.assertEqual(packet['scope'],'natal_finance')
        self.assertFalse(packet['rules_profile']['annual_compression'])
        self.assertEqual(packet['charts'],self.baseline['natal']['charts'])
        self.assertEqual(packet['window']['start_utc'],self.baseline['annual']['start_utc'])
        self.assertIn('special_lagnas',packet)
        self.assertIn('pachakadi_venus_variant',[x['id'] for x in packet['source_issues']])
        self.assertIn('pachakadi',packet)
        self.assertFalse(packet['qualification']['interval_stability_verified'])
        self.assertNotIn('shadbala_components',packet)

    def test_invalid_requests_rejected_before_calculating(self):
        for value in (None,'rao_hora_finance_2003_v1',['unknown'],[TECHNIQUE_ID,TECHNIQUE_ID]):
            request=deepcopy(self.request); request['techniques']=value
            with self.subTest(value=value),self.assertRaises(ValueError): calculate(request)
        request=deepcopy(self.request); request['techniques']=[TECHNIQUE_ID]
        del request['target_year']
        with self.assertRaises(ValueError): calculate(request)
        request=deepcopy(self.request); request['techniques']=[TECHNIQUE_ID]
        request['allowed_vargas']=['D1']
        with self.assertRaises(ValueError): calculate(request)


if __name__=='__main__': unittest.main()
