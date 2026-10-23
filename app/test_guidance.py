import unittest
from pathlib import Path
from workflow import Workflow
from stock_io import read_stock
from product_guidance import situation, visible


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.c = Workflow([
            dict(codigo='27023014MO5', produto='27-0230 14 MO5', referencia='AR38138-MRS03-F83 MO5 14', grupo='27-ANEL PRATA'),
            dict(codigo='47023014W', produto='47-0230 14 W', referencia='AR38138-MRS03-F83 W 14', grupo='47-ANEL MOISSANITE'),
            dict(codigo='47115014W', produto='47-1150 14 W', referencia='OLD W 14', grupo='47-ANEL MOISSANITE'),
        ], ':memory:')

    def tearDown(self):
        self.c.db.close()

    def test_wrong_stock_group_does_not_mean_already_registered(self):
        r = self.c.prepare('AR38138-MRS03-F83 MO5 14')[0]
        self.assertEqual(r['grupo'], '47-ANEL MOISSANITE')
        self.assertEqual(r['status'], 'Pronto para reservar')
        self.assertEqual(r['codigo'], '47023014MO5')
        self.assertTrue(r['exportar'])

    def test_existing_moissanite_is_reused(self):
        r = self.c.prepare('AR38138-MRS03-F83 W 14')[0]
        self.assertEqual(r['status'], 'Já cadastrado')
        self.assertEqual(r['codigo'], '47023014W')
        self.assertFalse(r['exportar'])

    def test_incompatible_manual_group_and_rule_block(self):
        ref = 'AR999-MRS04-F83 W 14'
        self.c.rules.save('AR*', '', '27-ANEL PRATA')
        for assignments in ({}, {ref: '27-ANEL PRATA'}):
            r = self.c.prepare(ref, assignments=assignments)[0]
            self.assertEqual(r['status'], 'Escolha a categoria')
            self.assertEqual(r['codigo'], '')
            self.assertIn('moissanite', r['detalhe'])
            self.assertFalse(r['exportar'])

    def test_origin_material_also_restricts_non_mrs_reference(self):
        ref = 'OTHER W 14'
        r = self.c.prepare(ref, assignments={ref:'27-ANEL PRATA'}, items={ref:dict(tipo='ANEL MOISSANITE')})[0]
        self.assertFalse(r['exportar'])
        self.assertEqual(r['grupo'], '')

    def test_export_cannot_bypass_material_validation(self):
        r = self.c.prepare('AR38138-MRS03-F83 W 14')[0]
        r.update(grupo='27-ANEL PRATA', exportar=True)
        with self.assertRaisesRegex(ValueError, 'moissanite'):
            self.c.export_rows([r])

    def test_new_filter_includes_first_item_and_new_variations(self):
        rows = self.c.prepare('AR-NEW W 12\nAR-NEW W 14\nOLD W 14\nPENDING W 12',
                              assignments={'AR-NEW W 12':'47-ANEL MOISSANITE', 'AR-NEW W 14':'47-ANEL MOISSANITE'})
        self.assertEqual([r['produto'] for r in rows[:2]], ['47-1151 12 W', '47-1151 14 W'])
        self.assertEqual([situation(r)[0] for r in rows[:2]], ['Novo modelo', 'Nova variação'])
        self.assertEqual([i for i,r in enumerate(rows) if visible(r, 'A cadastrar (novos e variações)')], [0,1])
        self.assertTrue(visible(rows[1], 'Novas variações', '47-1151 14'))
        self.assertTrue(visible(rows[3], 'Precisam de atenção'))
        self.c.reserve(rows[:2])
        again = self.c.prepare('AR-NEW W 12\nAR-NEW W 14')
        self.assertTrue(all(visible(r, 'A cadastrar (novos e variações)') for r in again))
        self.assertTrue(all('não confirma' in situation(r)[1] for r in again))

    def test_real_ar38138_stock_never_uses_prata(self):
        stock = Path(__file__).resolve().parents[3] / 'Criar Códigos.xlsx'
        if not stock.exists():
            self.skipTest('Estoque de referência não disponível')
        self.c.records = read_stock(stock, '1 - Estoque')
        rows = self.c.prepare('AR38138-MRS03-F83 MO5 14\nAR38138-MRS03-F83 W 14\nAR38138-MRS02-F83 W 12')
        self.assertTrue(all(r['grupo']=='47-ANEL MOISSANITERODIO' for r in rows))
        self.assertEqual([r['status'] for r in rows], ['Pronto para reservar','Já cadastrado','Já cadastrado'])
