import json
import tempfile
import unittest
from pathlib import Path
from criar_codigos import Catalog, HOME, read_xlsx


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HOME)
        self.rows = [
            dict(codigo='17052314W', produto='17-0523 14 W', referencia='AR39052-F83 W 14', grupo='17-ANEL'),
            dict(codigo='17052316W', produto='17-0523 16 W', referencia='AR39052-F83 W 16', grupo='17-ANEL'),
        ]
        self.c = Catalog(self.rows, Path(self.tmp.name) / 'r.db')

    def tearDown(self):
        self.c.db.close()
        self.tmp.cleanup()

    def test_existing_and_whitespace(self):
        r = self.c.analyze(' ar39052-f83   w 14 ')[0]
        self.assertEqual(r['codigo'], '17052314W')
        self.assertEqual(r['status'], 'Já cadastrado')

    def test_new_variation(self):
        r = self.c.analyze('AR39052-F83 W 18\t18 W', '17-ANEL')[0]
        self.assertEqual(r['codigo'], '17052318W')

    def test_new_family_and_batch_variations(self):
        rows = self.c.analyze('NEW W 14\t14 W\nNEW W 16\t16 W\nOTHER W\tJ W', '17-ANEL')
        self.assertEqual([r['codigo'] for r in rows], ['17052414W', '17052416W', '170525JW'])

    def test_collision_and_repeated_line(self):
        rows = self.c.analyze('AR39052-F83 X\t14 W\nAR39052-F83 X\t14 W', '17-ANEL')
        self.assertEqual([r['status'] for r in rows], ['Código em uso', 'Repetido no lote'])

    def test_ambiguous_reference(self):
        self.c.records.append(dict(self.rows[0], codigo='OTHER'))
        self.assertEqual(self.c.analyze('AR39052-F83 W 14')[0]['status'], 'Referência ambígua')

    def test_ambiguous_family(self):
        self.c.records.append(dict(self.rows[0], produto='17-0524 20 W', referencia='AR39052-F83 W 20', codigo='17052420W'))
        self.assertEqual(self.c.analyze('AR39052-F83 W 22', '17-ANEL', '22 W')[0]['status'], 'Família ambígua')

    def test_required_inputs_and_number(self):
        self.assertEqual(self.c.analyze('NEW')[0]['status'], 'Escolha o grupo')
        self.assertEqual(self.c.analyze('NEW', '17-ANEL')[0]['status'], 'Informe tamanho e cor')
        with self.assertRaises(ValueError):
            self.c.analyze('NEW', '17-ANEL', 'J W', '523')

    def test_persistent_reservation_and_stale_proposal(self):
        rows = self.c.analyze('NEW W', '17-ANEL', 'J W')
        self.assertEqual(self.c.reserve(rows), 1)
        with self.assertRaises(ValueError):
            self.c.reserve(rows)
        self.assertEqual(self.c.analyze('NEW W', '17-ANEL')[0]['status'], 'Já cadastrado')
        self.assertEqual(self.c.analyze('OTHER W', '17-ANEL', 'J W')[0]['codigo'], '170525JW')
        other = Catalog(self.rows, Path(self.tmp.name) / 'r.db')
        self.assertEqual(len(other.all_records()), 3)
        other.db.close()

    def test_reservation_is_atomic(self):
        rows = self.c.analyze('NEW W\tJ W\nOTHER W\tJ W', '17-ANEL')
        rows[1]['codigo'] = self.rows[0]['codigo']
        with self.assertRaises(ValueError):
            self.c.reserve(rows)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0], 0)

    def test_global_sequence_across_groups(self):
        self.c.records.append(dict(codigo='AU260999JW', produto='AU26-0999 J W', referencia='OTHER-GROUP W', grupo='AU26-BRINCO'))
        row = self.c.analyze('NEW W', '17-ANEL', 'J W')[0]
        self.assertEqual(row['codigo'], '171000JW')
        self.c.reserve([row])
        row2 = self.c.analyze('NEXT W', 'AU26-BRINCO', 'J W')[0]
        self.assertEqual(row2['codigo'], 'AU261001JW')

    def test_stale_number_across_groups(self):
        first = self.c.analyze('NEW W', '17-ANEL', 'J W')
        second = self.c.analyze('OTHER W', '26-BRINCO', 'J W')
        self.c.reserve(first)
        with self.assertRaises(ValueError):
            self.c.reserve(second)

    def test_invalid_paste(self):
        row = self.c.analyze('REF\t18\tW', '17-ANEL')[0]
        self.assertEqual(row['status'], 'Formato inválido')

    def test_real_base_import(self):
        source = HOME.parents[2] / 'Criar Códigos.xlsx'
        if not source.exists():
            self.skipTest('Estoque real não faz parte do repositório.')
        imported = read_xlsx(source)
        seed = json.loads((HOME / 'base.json').read_text(encoding='utf-8'))
        self.assertEqual(imported, seed)
        self.assertEqual(len(imported), 4941)


if __name__ == '__main__':
    unittest.main()
