import unittest
from openpyxl import Workbook,load_workbook
import test_desktop as fixtures
from desktop_api import DesktopAPI
from stock_io import read_stock


class RegistrationTests(unittest.TestCase):
    setUp=fixtures.DesktopTests.setUp
    tearDown=fixtures.DesktopTests.tearDown
    ok=fixtures.DesktopTests.ok

    def seed(self):
        self.ok('manual',dict(text='NEW W 12\t\t\t47\nNEW W 14\t\t\t47'))

    def test_description_bulk_preserves_filled_values_and_reanalysis(self):
        self.seed()
        self.ok('product_details',dict(ids=[0],descricao='Anel solitário',atributos={'pedra':'Moissanite'},overwrite=True,model=True))
        d=self.ok('product_details',dict(ids=[0,1],descricao='Não substituir',atributos={'estilo':'Clássico'},overwrite=False))
        self.assertEqual([r['descricao'] for r in d['rows']],['Anel solitário']*2)
        self.ok('edit_item',dict(ids=[0],group='47-ANEL MOISSANITE',size='12 W'))
        self.ok('restore')
        grade=self.ok('preview_grade')
        self.assertEqual([r[3] for r in grade['rows']],['Anel solitário']*3)
        self.assertEqual([r[2] for r in grade['rows']],['47115112W','47115114W','471151'])

    def test_custom_export_order_fixed_values_and_parent_consensus(self):
        self.seed()
        self.ok('product_details',dict(ids=[0],descricao='Anel A',atributos={'tema':'Flores'},overwrite=True))
        self.ok('product_details',dict(ids=[1],descricao='Anel B',atributos={'tema':'Corações'},overwrite=True))
        self.ok('layout_save',dict(name='Minha empresa',parents=True,columns=[dict(header='Tema',source='attr.tema'),dict(header='Código',source='codigo'),dict(header='Constante',source='fixed',value='001'),dict(header='Fator',source='erp.aaa_fatconv')]))
        grade=self.ok('preview_grade')
        self.assertEqual(grade['headers'],['Tema','Código','Constante','Fator'])
        self.assertEqual(grade['rows'][-1],['','471151','001',50])
        target=self.folder/'custom.xlsx';self.window.paths.append(target);self.ok('export')
        book=load_workbook(target);sheet=book.active
        self.assertEqual(sheet.max_column,4);self.assertEqual(sheet['C2'].value,'001')
        self.assertEqual(sheet['D4'].value,50);self.assertEqual(sheet.auto_filter.ref,'A1:D4');book.close()

    def test_profile_values_are_isolated_persist_and_required_blocks_reservation(self):
        self.seed();self.ok('product_details',dict(ids=[0],descricao='Troven original',overwrite=True))
        d=self.ok('profile_save',dict(name='Empresa nova',description_required=True,fields=[dict(id='material',label='Material',required=True,options=['Prata','Ouro'])]))
        second=d['registration']['profile']['id']
        self.assertFalse(d['rows'][0]['descricao'])
        error=self.api.call('preview_grade');self.assertFalse(error['ok']);self.assertIn('Descrição',error['error'])
        self.assertFalse(self.api.call('export')['ok'])
        count=self.api._pool.submit(lambda:self.api._catalog.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]).result()
        self.assertEqual(count,0)
        self.assertFalse(self.api.call('product_details',dict(ids=[0],atributos={'material':'Inválido'},overwrite=True))['ok'])
        self.ok('product_details',dict(ids=[0,1],descricao='Produto da empresa',atributos={'material':'Prata'},overwrite=True))
        self.assertEqual(self.ok('preview_grade')['headers'][-1],'Material')
        d=self.ok('profile_select',dict(id='troven'));self.assertEqual(d['rows'][0]['descricao'],'Troven original')
        self.ok('save');self.api._close();self.api=DesktopAPI(self.folder);self.api._window=self.window
        self.ok('restore');d=self.ok('profile_select',dict(id=second))
        self.assertEqual(d['rows'][0]['descricao'],'Produto da empresa')
        self.assertEqual(d['rows'][0]['atributos']['material'],'Prata')

    def test_import_description_and_dynamic_attributes(self):
        incoming=self.folder/'atributos.xlsx';book=Workbook();sheet=book.active;sheet.title='Itens'
        sheet.append(['Referência','GP','Descrição','Faixa etária','Tema','Peso'])
        sheet.append(['NEW W 12','47','Anel escrito','Adulto','Flores',2.35]);book.save(incoming);book.close()
        self.window.paths.append(incoming);info=self.ok('choose_new');inspection=info['inspection']
        self.assertEqual(inspection['mapping']['cad.descricao'],2)
        self.ok('import_new',dict(sheet='Itens',header=1,mapping=inspection['mapping']))
        state=self.ok('state');self.assertEqual(state['rows'][0]['descricao'],'Anel escrito')
        self.assertEqual(state['rows'][0]['atributos']['faixa_etaria'],'Adulto')
        self.ok('layout_select',dict(id='complete'));grade=self.ok('preview_grade')
        self.assertEqual(grade['rows'][0][grade['headers'].index('Tema')],'Flores')
        self.assertEqual(grade['rows'][0][grade['headers'].index('Peso')],2.35)

    def test_custom_export_cannot_bypass_mixed_parent_units(self):
        self.seed();self.ok('layout_save',dict(name='Somente código',parents=False,columns=[dict(header='Código',source='codigo')]))
        self.ok('weight',dict(ids=[0],mode='Peso',value='2,35'))
        result=self.api.call('preview_grade');self.assertFalse(result['ok']);self.assertIn('unidades diferentes',result['error'])

    def test_written_stock_names_use_reserved_codes_or_explicit_sequence(self):
        source=self.folder/'nomes.xlsx';book=Workbook();sheet=book.active;sheet.title='Estoque'
        sheet.append(['Código','Produto','Referência','GP'])
        sheet.append(['47115112W','Anel solitário','NEW W 12','47-ANEL MOISSANITE']);book.save(source);book.close()
        with self.assertRaisesRegex(ValueError,'Identificador técnico'):read_stock(source)
        known=[dict(codigo='47115112W',produto='47-1151 12 W',referencia='NEW W 12',grupo='47-ANEL MOISSANITE')]
        self.assertEqual(read_stock(source,known_records=known)[0]['produto'],'47-1151 12 W')
        book=load_workbook(source);sheet=book.active;sheet.cell(1,5).value='aaa_refbase';sheet.cell(2,5).value='1151';book.save(source);book.close()
        self.assertEqual(read_stock(source)[0]['produto'],'47-1151 12 W')

    def test_complete_export_preserves_technical_identifier_for_next_stock(self):
        self.seed();self.ok('product_details',dict(ids=[0,1],descricao='Anel solitário',overwrite=True))
        self.ok('layout_select',dict(id='complete'));target=self.folder/'Completo.xlsx'
        self.window.paths.append(target);self.ok('export')
        records=read_stock(target)
        self.assertEqual(records[0]['produto'],'47-1151 12 W')
        self.assertEqual(records[-1]['produto'],'47-1151')

    def test_moissanite_stone_attribute_requires_compatible_group(self):
        self.ok('manual',dict(text='AR-DESIGN W 12\t\t\t27'))
        self.ok('product_details',dict(ids=[0],atributos={'pedra':'Moissanite'},overwrite=True))
        result=self.api.call('preview_grade');self.assertFalse(result['ok']);self.assertIn('moissanite',result['error'])
