import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from workflow import Workflow
from new_items import inspect_sheet, read_items


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.folder = Path(self.tmp.name)
        self.c = Workflow([
            dict(codigo='17114814W', produto='17-1148 14 W', referencia='AR-OLD W 14', grupo='17-ANEL'),
            dict(codigo='261149JW', produto='26-1149 J W', referencia='BR-OLD W', grupo='26-BRINCO'),
        ], self.folder / 'r.db')

    def tearDown(self):
        self.c.db.close()
        self.tmp.cleanup()

    def source(self, bad=False):
        b = Workbook()
        s = b.active
        s.title = 'Pedido'
        s.append(['Informações do fornecedor'])
        s.append(['Campo inútil', 'Referência', 'Preço', 'Peso', 'Tipo'])
        s.append(['ignorar', 'AR-OLD CZ04 14', 999, '2,35', 'Anel'])
        s.append(['ignorar', 'BR-OLD CZ04', 888, None, 'Brinco'])
        s.append(['ignorar', 'AR-OLD W 16', 777, 'zero' if bad else None, 'Anel'])
        s.append(['ignorar', 'TOTAL', 123, 100, None])
        path = self.folder / 'novos.xlsx'
        b.save(path)
        b.close()
        return path

    def test_mapping_ignores_unneeded_columns_and_totals(self):
        path = self.source()
        header, cols, mapping, preview = inspect_sheet(path, 'Pedido')
        self.assertEqual(header, 2)
        self.assertEqual(mapping['referencia'], 1)
        self.assertEqual(mapping['peso'], 3)
        items, skipped = read_items(path, 'Pedido', header, mapping)
        self.assertEqual(len(items), 3)
        self.assertEqual(skipped, 1)
        self.assertEqual(items[0]['peso'], 2.35)
        self.assertIsNone(items[1]['peso'])
        self.assertNotIn('Preço', items[0])

    def test_invalid_weight_is_not_treated_as_unit(self):
        path = self.source(bad=True)
        header, _, mapping, _ = inspect_sheet(path, 'Pedido')
        with self.assertRaisesRegex(ValueError, 'Linha 5'):
            read_items(path, 'Pedido', header, mapping)

    def test_no_weight_column_means_unit(self):
        path = self.source()
        header, _, mapping, _ = inspect_sheet(path, 'Pedido')
        mapping['peso'] = None
        items, _ = read_items(path, 'Pedido', header, mapping)
        self.assertTrue(all(r['peso'] is None for r in items))

    def test_weight_and_unit_rules_for_mixed_batch(self):
        rows = self.c.prepare('AR-OLD CZ04 14\t\t2,35\nBR-OLD CZ04\nAR-OLD W 16')
        self.assertEqual([r['unidade'] for r in rows], ['G', 'PR', 'PC'])
        self.assertEqual([r['peso'] for r in rows], [2.35, 1, 1])

    def test_explicit_one_gram_remains_grams(self):
        row = self.c.prepare('BR-OLD CZ04\t\t1')[0]
        self.assertEqual(row['peso'], 1)
        self.assertEqual(row['unidade'], 'G')

    def test_new_file_blank_weight_does_not_reuse_previous_batch_weight(self):
        ref = 'BR-OLD CZ04'
        first = self.c.prepare(ref, items={ref: {'context': 'primeiro'}})[0]
        self.c.set_weight(first, '3,25')
        self.assertEqual(self.c.prepare(ref, items={ref: {'context': 'primeiro'}})[0]['unidade'], 'G')
        other = self.c.prepare(ref, items={ref: {'context': 'segundo'}})[0]
        self.assertEqual(other['unidade'], 'PR')
        self.assertEqual(other['peso'], 1)

    def test_edit_back_to_unit_and_export(self):
        row = self.c.prepare('BR-OLD CZ04\t\t3.5')[0]
        self.c.set_weight(row, None)
        exported = self.c.export_rows([row])[0]
        self.assertEqual({k:exported[k] for k in ('codigo','referencia','peso','unidade')}, dict(codigo='261149JCZ04', referencia='BR-OLD CZ04', peso=1, unidade='PR'))


if __name__ == '__main__':
    unittest.main()
