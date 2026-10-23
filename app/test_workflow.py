import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook, load_workbook
from workflow import Workflow, weight
from stock_io import export_xlsx, stock_sheets, read_stock


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.tmp.name)
        self.rows = [
            dict(codigo='17052314W', produto='17-0523 14 W', referencia='AR39052-F83 W 14', grupo='17-ANEL', peso=2.35),
            dict(codigo='AU261149JW', produto='AU26-1149 J W', referencia='BR-OLD W', grupo='AU26-BRINCO', peso=3.15),
        ]
        self.c = Workflow(self.rows, self.path / 'db.sqlite3')

    def tearDown(self):
        self.c.db.close()
        self.tmp.cleanup()

    def test_no_stock_prevents_generation(self):
        self.c.records = []
        with self.assertRaisesRegex(ValueError, 'estoque'):
            self.c.prepare('NEW W', '17-ANEL', 'J W')

    def test_global_number_and_weights(self):
        rows = self.c.prepare('NEW W 14\t\t2,35\nNEW W 16\t\t3.2\nOTHER W\tJ W\t4\tAU26', '17-ANEL')
        self.assertEqual([r['codigo'] for r in rows], ['17115014W', '17115016W', 'AU261151JW'])
        self.assertEqual([r['peso'] for r in rows], [2.35, 3.2, 4.0])
        self.c.reserve(rows)
        self.assertEqual(self.c.last_number(), 1151)
        self.assertEqual(self.c.last_number(True), 1149)

    def test_mixed_batch_detects_categories_for_each_model(self):
        rows = self.c.prepare('AR39052-F83 CZ04 14\nBR-OLD CZ04')
        self.assertEqual([r['grupo'] for r in rows], ['17-ANEL', 'AU26-BRINCO'])
        self.assertEqual([r['codigo'] for r in rows], ['17052314CZ04', 'AU261149JCZ04'])

    def test_new_model_requires_category_even_when_prefix_exists(self):
        row = self.c.prepare('AR-NEW W 14')[0]
        self.assertEqual(row['status'], 'Escolha a categoria')
        self.assertEqual(row['codigo'], '')
        self.assertFalse(row['exportar'])

    def test_same_reference_in_two_categories_is_not_guessed(self):
        self.c.records.append(dict(self.rows[0], codigo='47052314W', produto='47-0523 14 W', grupo='47-ANEL'))
        row = self.c.prepare('AR39052-F83 W 14')[0]
        self.assertEqual(row['status'], 'Escolha a categoria')
        self.assertEqual(row['categorias_possiveis'], ['17-ANEL', '47-ANEL'])
        chosen = self.c.prepare('AR39052-F83 W 14', assignments={'AR39052-F83 W 14': '47-ANEL'})[0]
        self.assertEqual(chosen['codigo'], '47052314W')

    def test_family_color_can_disambiguate_a_missing_size(self):
        self.c.records.append(dict(self.rows[0], codigo='47052314MO5', produto='47-0523 14 MO5', referencia='AR39052-F83 MO5 14', grupo='47-ANEL'))
        rows = self.c.prepare('AR39052-F83 MO5 16\nAR39052-F83 MCB 18')
        self.assertEqual(rows[0]['grupo'], '47-ANEL')
        self.assertEqual(rows[0]['codigo'], '47052316MO5')
        self.assertEqual(rows[1]['status'], 'Escolha a categoria')

    def test_individual_categories_share_one_global_sequence(self):
        rows = self.c.prepare('AR-NEW W 12\nAR-NEW W 14\nBR-NEW W', assignments={'AR-NEW W 12': '17-ANEL', 'AR-NEW W 14': '17-ANEL', 'BR-NEW W': 'AU26-BRINCO'}, sizes={'BR-NEW W': 'J W'})
        self.assertEqual([r['codigo'] for r in rows], ['17115012W', '17115014W', 'AU261151JW'])

    def test_category_and_size_choices_are_saved(self):
        assignments = {'AR-NEW W 12': '17-ANEL'}
        sizes = {'AR-NEW W 12': '14 W'}
        rows = self.c.prepare('AR-NEW W 12', assignments=assignments, sizes=sizes)
        self.c.save_session(rows, text='AR-NEW W 12', assignments=assignments, sizes=sizes)
        self.assertEqual(self.c.session()['assignments'], assignments)
        self.assertEqual(self.c.session()['sizes'], sizes)

    def test_existing_keeps_stock_weight_but_not_selected(self):
        r = self.c.prepare('AR39052-F83 W 14', '17-ANEL')[0]
        self.assertEqual(r['status'], 'Já cadastrado')
        self.assertEqual(r['peso'], 1)
        self.assertEqual(r['unidade'], 'PC')
        self.assertFalse(r['exportar'])

    def test_new_variation_has_no_invented_weight(self):
        r = self.c.prepare('AR39052-F83 CZ04 14', '17-ANEL')[0]
        self.assertEqual(r['codigo'], '17052314CZ04')
        self.assertEqual(r['peso'], 1)
        self.assertEqual(r['unidade'], 'PC')

    def test_default_size_color_only_fills_missing_information(self):
        rows = self.c.prepare('NEW W 14\nNEW CZ04 16\nOTHER W', '17-ANEL', 'J W')
        self.assertEqual([r['produto'] for r in rows], ['17-1150 14 W', '17-1150 16 CZ04', '17-1151 J W'])

    def test_explicit_line_size_color_can_override_inferred(self):
        row = self.c.prepare('NEW W 14\t18 CZ04', '17-ANEL', 'J W')[0]
        self.assertEqual(row['produto'], '17-1150 18 CZ04')

    def test_unambiguous_family_suffix(self):
        r = self.c.prepare('BR-OLD CZ04', 'AU26-BRINCO')[0]
        self.assertEqual(r['codigo'], 'AU261149JCZ04')

    def test_missing_or_invalid_weight_blocks_export(self):
        rows = self.c.prepare('NEW W', '17-ANEL', 'J W')
        self.assertEqual(self.c.export_rows(rows)[0]['unidade'], 'PC')
        self.assertEqual(self.c.export_rows(rows)[0]['peso'], 1)
        for v in ('0', '-1', 'NaN', 'Infinity', 'um', '1.234,56', '1,2,3'):
            with self.subTest(v=v), self.assertRaises(ValueError):
                weight(v)
        self.c.set_weight(rows[0], '1,25')
        self.assertEqual(self.c.export_rows(rows)[0]['peso'], 1.25)

    def test_weight_is_saved_and_reservation_can_be_reexported(self):
        rows = self.c.prepare('NEW W', '17-ANEL', 'J W')
        self.c.set_weight(rows[0], '2,5')
        self.c.reserve(rows)
        again = self.c.prepare('NEW W', '17-ANEL')
        self.assertEqual(again[0]['status'], 'Reservado')
        self.assertEqual(again[0]['peso'], 2.5)
        self.assertTrue(again[0]['exportar'])
        self.assertEqual(len(self.c.export_rows(again)), 1)
        self.c.reserve(again)
        self.assertEqual(self.c.last_number(), 1150)

    def test_ambiguous_and_duplicates_not_selected(self):
        rows = self.c.prepare('NEW W\nNEW W', '17-ANEL', 'J W')
        self.assertEqual(rows[1]['status'], 'Repetido no lote')
        self.assertFalse(rows[1]['exportar'])

    def test_unknown_group_and_invalid_paste(self):
        with self.assertRaisesRegex(ValueError, 'Grupo'):
            self.c.prepare('NEW W', '999')
        with self.assertRaises(ValueError):
            self.c.prepare('NEW W\tJ W\t2\t17\textra', '17-ANEL')

    def test_session_persists(self):
        rows = self.c.prepare('NEW W\tJ W\t3,14', '17-ANEL')
        self.c.save_session(rows, 'stock.xlsx', 'Produtos', 'NEW W\tJ W\t3,14', '17-ANEL')
        again = Workflow(self.rows, self.path / 'db.sqlite3')
        self.assertEqual(again.session()['rows'][0]['peso'], 3.14)
        self.assertEqual(again.session()['source'], 'stock.xlsx')
        again.db.close()

    def make_stock(self):
        book = Workbook()
        s = book.active
        s.title = 'Estoque atualizado'
        s.append(['Relatório do estoque'])
        s.append(['GP', 'Referência', 'Peso', 'Produto', 'Cód. Sistema'])
        s.append(['17-ANEL', 'AR39052-F83 W 14', 2.35, '17-0523 14 W', '17052314W'])
        target = self.path / 'stock.xlsx'
        book.save(target)
        book.close()
        return target

    def test_stock_any_sheet_and_reordered_columns(self):
        source = self.make_stock()
        self.assertEqual(stock_sheets(source), ['Estoque atualizado'])
        data = read_stock(source)
        self.assertEqual(data, self.rows[:1])

    def test_wrong_stock_is_rejected(self):
        b = Workbook()
        p = self.path / 'wrong.xlsx'
        b.save(p)
        b.close()
        self.assertEqual(stock_sheets(p), [])
        with self.assertRaises(ValueError):
            read_stock(p)

    def test_stock_unrecognized_sequence_is_rejected(self):
        source = self.make_stock()
        b = load_workbook(source)
        b.active['D3'] = 'PRODUTO SEM SEQUÊNCIA'
        b.save(source)
        b.close()
        with self.assertRaisesRegex(ValueError, 'sequência'):
            read_stock(source)

    def test_export_exact_three_columns_and_numeric_weight(self):
        rows = self.c.prepare('NEW W\tJ W\t2,35', '17-ANEL')
        p = self.path / 'cadastro.xlsx'
        export_xlsx(p, self.c.export_rows(rows))
        b = load_workbook(p, data_only=False)
        s = b.active
        self.assertEqual(s.max_column, 19)
        self.assertEqual(s.max_row, 3)
        self.assertEqual(s['C2'].value, '171150JW')
        self.assertEqual(s['E2'].value, 'NEW W')
        self.assertEqual(s['C2'].data_type, 's')
        self.assertEqual(s['H2'].data_type, 'n')
        self.assertEqual(s.freeze_panes, 'A2')
        b.close()

    def test_literal_formula_text_stays_text(self):
        p = self.path / 'literal.xlsx'
        export_xlsx(p, [dict(codigo='170123JW', produto='17-0123 J W', grupo='17-ANEL', referencia='=1+1', peso=1.0,unidade='G')])
        b = load_workbook(p)
        self.assertEqual(b.active['B2'].value, '0123')
        self.assertEqual(b.active['E2'].data_type, 's')
        b.close()


if __name__ == '__main__':
    unittest.main()
