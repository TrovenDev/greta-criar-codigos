import unittest
from workflow import Workflow


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.c = Workflow([
            dict(codigo='27000114W',produto='27-0001 14 W',referencia='AR100-RS01-F83 W 14',grupo='27-ANEL PRATA'),
            dict(codigo='47000114W',produto='47-0001 14 W',referencia='AR100-RS01-F83 W 14',grupo='47-ANEL MOISSANITE'),
        ], ':memory:')

    def tearDown(self):
        self.c.db.close()

    def test_rule_applies_to_all_1000_items_and_one_sequence(self):
        self.c.rules.save('AR*', '*PRATA*', '27-ANEL PRATA')
        refs = [f'AR{i+200}-RS01-F83 W 14' for i in range(1000)]
        rows = self.c.prepare('\n'.join(refs), items={r:{'grupo':'PRATA BRANCA'} for r in refs})
        self.assertEqual(len(rows),1000)
        self.assertTrue(all(r['grupo']=='27-ANEL PRATA' for r in rows))
        self.assertTrue(all(r['status']=='Pronto para reservar' for r in rows))
        self.assertEqual(len({r['codigo'] for r in rows}),1000)
        self.assertEqual(rows[0]['produto'],'27-0002 14 W')
        self.assertEqual(rows[-1]['produto'],'27-1001 14 W')

    def test_conflicting_rules_require_review(self):
        self.c.rules.save('AR*','','27-ANEL PRATA')
        self.c.rules.save('AR*','','47-ANEL MOISSANITE')
        r = self.c.prepare('AR200-RS01-F83 W 14')[0]
        self.assertEqual(r['status'],'Escolha a categoria')
        self.assertIn('Conflito',r['detalhe'])
        self.assertFalse(r['exportar'])

    def test_stock_pattern_must_have_unique_category_and_multiple_models(self):
        self.c.records = [dict(codigo=f'67R000{i}45W',produto=f'67R-000{i} 45 W',referencia=f'GR{i}-FC01-F83 W',grupo='67R-FLOWER') for i in (1,2)]
        r = self.c.prepare('GR999-FC02-F83 W\t45 W')[0]
        self.assertEqual(r['grupo'],'67R-FLOWER')
        self.assertIn('Padrão único',r['origem_categoria'])

    def test_manual_choice_overrides_rule_and_known_stock_is_preserved(self):
        self.c.rules.save('AR*','','47-ANEL MOISSANITE')
        r = self.c.prepare('AR200-RS01-F83 W 14', assignments={'AR200-RS01-F83 W 14':'27-ANEL PRATA'})[0]
        self.assertEqual(r['grupo'],'27-ANEL PRATA')
        self.c.records = self.c.records[:1]
        known = self.c.prepare('AR100-RS01-F83 W 14')[0]
        self.assertEqual(known['grupo'],'27-ANEL PRATA')
