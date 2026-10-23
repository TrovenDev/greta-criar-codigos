"""Ponte da interface web com o fluxo validado de cadastro."""
import csv
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from workflow_core import Workflow
from criar_codigos import normal, family
from stock_io import stock_sheets, read_stock, export_xlsx
from new_items import list_sheets, inspect_sheet, read_items
from product_guidance import situation, compatible, VALID
from grade_export import grade_rows, GRADE_HEADERS
from category_rules import stock_patterns
from updates import UpdateManager
from release_notes import changelog,mark_seen
from photo_links import PhotoLinks
from registration import Registration


class DesktopAPI:
    def __init__(self, data_dir=None):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='troven')
        self._window = None
        self._home = Path(data_dir or os.environ.get('TROVEN_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Troven' / 'Cadastro')
        self._home.mkdir(parents=True, exist_ok=True)
        self._updates = UpdateManager(self._home)
        self._photos = PhotoLinks(self._home)
        self._restart_requested=False
        self._exit_callback=None
        self._pool.submit(self._init).result()

    def _init(self):
        self._catalog = Workflow([], self._home / 'reservas.sqlite3')
        self._registration=Registration(self._catalog.db)
        self._rows, self._assignments, self._sizes, self._items = [], {}, {}, {}
        self._text = self._source = self._sheet = self._new_source = ''
        self._stamp = None
        self._pending_stock = self._pending_new = ''

    def call(self, action, payload=None):
        try:
            return self._pool.submit(self._dispatch, action, payload or {}).result()
        except Exception as exc:
            return dict(ok=False, error=str(exc))

    def _dispatch(self, action, p):
        actions = {'state':self._state, 'choose_stock':self._choose_stock, 'load_stock':self._load_stock,
                   'choose_new':self._choose_new, 'inspect_new':self._inspect_new, 'import_new':self._import_new,
                   'manual':self._manual, 'category':self._category, 'edit_item':self._edit_item,
                   'weight':self._weight, 'paste_weights':self._paste_weights, 'toggle':self._toggle,
                   'include_existing':self._include_existing, 'save':self._save_action, 'restore':self._restore,
                   'rule_save':self._rule_save, 'rule_remove':self._rule_remove, 'learning':self._learning,
                   'preview_grade':self._preview_grade, 'export':self._export, 'import_database':self._import_database,
                   'check_updates':lambda p:self._updates.start(), 'update_state':lambda p:self._updates.snapshot(),
                   'changelog':lambda p:changelog(self._home), 'changelog_seen':lambda p:mark_seen(self._home),
                   'choose_photo_folder':self._choose_photo_folder,'photo_settings':self._photo_settings,
                   'restart_update':self._restart_update,
                   'profile_select':self._profile_select,'profile_save':self._profile_save,
                   'layout_save':self._layout_save,'layout_select':self._layout_select,
                   'product_details':self._product_details}
        if action not in actions:
            raise ValueError('Ação não reconhecida.')
        result = actions[action](p)
        return dict(ok=True, data=result)

    def _state(self, p=None):
        rows = [dict(r, id=i, situacao=situation(r)[0], proximo_passo=situation(r)[1]) for i,r in enumerate(self._rows)]
        for r in rows:
            r.update(self._registration.details(self._items.get(r['referencia'],{})))
            r['cadastro_pendente']=self._registration.missing(r)
        counts = dict(total=len(rows), novos=sum(r['status'] in ('Pronto para reservar','Reservado') for r in rows),
                      existentes=sum(r['status']=='Já cadastrado' for r in rows),
                      pendencias=sum(r['status'] not in VALID for r in rows),
                      exportar=sum(bool(r.get('exportar')) for r in rows),cadastro_pendente=sum(bool(r['cadastro_pendente']) for r in rows))
        return dict(rows=rows, counts=counts, stock=dict(path=self._source, sheet=self._sheet, count=len(self._catalog.records),
                    last=self._catalog.last_number(True), next=self._catalog.last_number()+1),
                    groups=sorted({r['grupo'] for r in self._catalog.records}), rules=self._catalog.rules.all(),
                    learning=self._catalog.rules.learning(), new_source=self._new_source,
                    has_saved=bool(self._catalog.session().get('rows')), data_dir=str(self._home),update=self._updates.snapshot(),changelog=changelog(self._home),photos=self._photos.summary(self._rows),registration=self._registration.snapshot())

    def _dialog(self, save=False, name='', database=False):
        import webview
        kinds = ('Base de reservas (*.sqlite3)',) if database else ('Excel (*.xlsx;*.xlsm)',)
        chosen = self._window.create_file_dialog(webview.FileDialog.SAVE if save else webview.FileDialog.OPEN,
                    save_filename=name, file_types=kinds)
        return str(chosen[0] if isinstance(chosen, (tuple,list)) else chosen) if chosen else ''

    def _choose_stock(self, p):
        path = self._dialog()
        if not path:
            return None
        sheets = stock_sheets(path)
        if not sheets:
            raise ValueError('Não encontrei uma aba com Código do sistema, Produto, Referência e GP.')
        self._pending_stock = path
        return dict(name=Path(path).name, sheets=sheets)

    def _load_stock(self, p):
        path = self._pending_stock
        records = read_stock(path, p['sheet'],known_records=self._catalog.all_records())
        self._catalog.records = records
        self._source, self._sheet = path, p['sheet']
        stat = Path(path).stat()
        self._stamp = (stat.st_mtime_ns, stat.st_size)
        self._rows, self._assignments, self._sizes, self._items = [], {}, {}, {}
        self._text = self._new_source = ''
        return self._state()

    def _require_stock(self):
        if not self._catalog.records:
            raise ValueError('Comece selecionando o Excel de estoque na primeira etapa.')

    def _choose_new(self, p):
        self._require_stock()
        path = self._dialog()
        if not path:
            return None
        self._pending_new = path
        sheets = list_sheets(path)
        return dict(name=Path(path).name, sheets=sheets, inspection=self._inspect_new(dict(sheet=sheets[0])))

    def _inspect_new(self, p):
        extra=self._registration.import_fields()
        row, columns, mapping, preview = inspect_sheet(self._pending_new, p['sheet'], p.get('header'),extra)
        return dict(header=row, columns=columns, mapping=mapping,
                    fields=extra,
                    preview=[[str(v) if v is not None else '' for v in line] for line in preview])

    def _import_new(self, p):
        records, skipped = read_items(self._pending_new, p['sheet'], int(p['header']), p['mapping'],self._registration.import_fields())
        items, lines = {}, []
        context = uuid4().hex
        options = {r['grupo'] for r in self._catalog.records}
        for item in records:
            ref = normal(item['referencia'])
            if ref in items:
                raise ValueError(f'A referência {ref} aparece mais de uma vez. Remova a duplicação na planilha antes de importar.')
            items[ref] = dict(item, context=context)
            values=dict(descricao=item.get('cad.descricao',''),atributos={f['id']:item.get('cad.'+f['id'],'') for f in self._registration.profile()['fields']})
            self._registration.validate_values(values)
            items[ref]['cadastros']={self._registration.profile()['id']:values}
            raw = normal(item.get('grupo',''))
            found = [g for g in options if normal(g)==raw or normal(g.split('-')[0])==raw]
            gp = found[0] if len(found)==1 else ''
            lines.append('\t'.join((ref,normal(item.get('tamanho_cor','')),str(item['peso']) if item['peso'] is not None else '',gp)))
        text = '\n'.join(lines)
        rows = self._catalog.prepare(text, items=items)
        self._text, self._items, self._rows = text, items, rows
        self._assignments, self._sizes = {}, {}
        self._new_source = self._pending_new
        self._save()
        return dict(state=self._state(), imported=len(rows), skipped=skipped)

    def _manual(self, p):
        self._require_stock()
        text = p['text']
        rows = self._catalog.prepare(text)
        self._text, self._rows = text, rows
        self._assignments, self._sizes, self._items = {}, {}, {}
        self._new_source = 'Referências coladas manualmente'
        self._save()
        return self._state()

    def _reanalyze(self):
        previous = {(r['referencia'],r['grupo']):r for r in self._rows}
        rows = self._catalog.prepare(self._text, assignments=self._assignments, sizes=self._sizes, items=self._items)
        for row in rows:
            old = previous.get((row['referencia'],row['grupo']))
            if old and old['status'] in VALID and row['status'] in VALID:
                row['exportar'] = bool(old.get('exportar'))
        self._rows = rows
        self._save()
        return self._state()

    def _selected(self, p):
        ids = {int(i) for i in p.get('ids',[])}
        rows = [r for i,r in enumerate(self._rows) if i in ids]
        if not rows:
            raise ValueError('Selecione pelo menos um produto na tabela.')
        return rows

    def _category(self, p):
        targets = self._selected(p)
        if p.get('model',True):
            models = {family(r['referencia']) for r in targets}
            targets = [r for r in self._rows if r in targets or not r['grupo'] and family(r['referencia']) in models]
        gp = p['group']
        if gp not in {r['grupo'] for r in self._catalog.records}:
            raise ValueError('Escolha um grupo da lista do estoque.')
        for r in targets:
            if not compatible(r['referencia'],gp,self._items.get(r['referencia'],{})):
                raise ValueError(f"{r['referencia']}: moissanite exige um grupo de moissanite.")
        for r in targets:
            self._assignments[r['referencia']] = gp
        return self._reanalyze()

    def _edit_item(self, p):
        row = self._selected(p)[0]
        gp = p['group']
        if gp not in {r['grupo'] for r in self._catalog.records} or not compatible(row['referencia'],gp,self._items.get(row['referencia'],{})):
            raise ValueError('Escolha uma categoria compatível. Moissanite exige grupo de moissanite.')
        self._assignments[row['referencia']] = gp
        self._sizes[row['referencia']] = normal(p.get('size',''))
        return self._reanalyze()

    def _weight(self, p):
        from item_rules import weight
        value = p.get('value','') if p.get('mode')=='Peso' else ''
        if p.get('mode')=='Peso' and weight(value) is None:
            raise ValueError('Informe um peso maior que zero para venda em gramas.')
        for r in self._selected(p):
            self._catalog.set_weight(r,value)
        self._save()
        return self._state()

    def _paste_weights(self, p):
        from item_rules import weight
        changes = []
        for line in p['text'].splitlines():
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts)!=2:
                raise ValueError('Cole duas colunas: código ou referência, e peso.')
            matches = [r for r in self._rows if normal(parts[0]) in (normal(r['referencia']),normal(r['codigo']))]
            if len(matches)!=1:
                raise ValueError(f'Identificação ausente ou ambígua: {parts[0]}. Use o código.')
            weight(parts[1])
            changes.append((matches[0],parts[1]))
        for r,v in changes:
            self._catalog.set_weight(r,v)
        self._save()
        return self._state()

    def _toggle(self, p):
        for r in self._selected(p):
            if r['status'] in VALID:
                r['exportar'] = bool(p['value']) if 'value' in p else not r.get('exportar')
        self._save()
        return self._state()

    def _include_existing(self, p):
        for r in self._rows:
            if r['status']=='Já cadastrado':
                r['exportar'] = bool(p['value'])
        self._save()
        return self._state()

    def _save(self):
        self._photos.apply(self._rows)
        self._catalog.save_session(self._rows,self._source,self._sheet,self._text,assignments=self._assignments,
                                  sizes=self._sizes,items=self._items,new_source=self._new_source)

    def _save_action(self, p):
        self._save()
        return self._state()

    def _restore(self, p):
        saved = self._catalog.session()
        if not saved.get('rows'):
            raise ValueError('Ainda não há um lote salvo nesta base.')
        records = read_stock(saved['source'],saved['sheet'],known_records=self._catalog.all_records())
        self._catalog.records = records
        self._source,self._sheet,self._text = saved['source'],saved['sheet'],saved['text']
        stat = Path(self._source).stat()
        self._stamp = (stat.st_mtime_ns,stat.st_size)
        self._assignments,self._sizes,self._items = saved.get('assignments',{}),saved.get('sizes',{}),saved.get('items',{})
        self._new_source = saved.get('new_source','')
        self._rows = self._catalog.prepare(self._text,assignments=self._assignments,sizes=self._sizes,items=self._items)
        old = {(r['referencia'],r['grupo']):r for r in saved['rows']}
        for r in self._rows:
            previous = old.get((r['referencia'],r['grupo']))
            if previous:
                for k in ('peso','venda_por','unidade'):
                    if k in previous:
                        r[k] = previous[k]
                r['exportar'] = bool(previous.get('exportar')) and r['status'] in VALID
        self._photos.apply(self._rows,force=True)
        return self._state()

    def _rule_save(self, p):
        if p['group'] not in {r['grupo'] for r in self._catalog.records}:
            raise ValueError('Escolha uma categoria da lista.')
        self._catalog.rules.save(p['pattern'],p.get('source',''),p['group'])
        return self._reanalyze() if self._rows else self._state()

    def _rule_remove(self, p):
        self._catalog.rules.remove(p['ids'])
        return self._reanalyze() if self._rows else self._state()

    def _learning(self, p):
        self._catalog.rules.learning(p['value'])
        return self._reanalyze() if self._rows else self._state()

    def _preview_grade(self, p):
        records = self._export_records()
        headers,grade,name=self._registration.export(records)
        return dict(headers=headers,rows=grade[:100],total=len(grade),children=len(records),parents=len(grade)-len(records),name=name)

    def _export(self, p):
        stat = Path(self._source).stat()
        if self._stamp!=(stat.st_mtime_ns,stat.st_size):
            raise ValueError('O estoque foi alterado. Carregue novamente o estoque antes de exportar.')
        records = self._export_records()
        headers,grade,name=self._registration.export(records)
        ext = 'csv' if p.get('csv') else 'xlsx'
        import webview
        path = self._window.create_file_dialog(webview.FileDialog.SAVE,save_filename='Grade Lançar.'+ext,
                     file_types=('CSV (*.csv)',) if ext=='csv' else ('Excel (*.xlsx)',))
        if not path:
            return None
        path = str(path[0] if isinstance(path,(tuple,list)) else path)
        if not Path(path).suffix:
            path += '.'+ext
        protected = [self._source,self._new_source,str(self._home/'reservas.sqlite3')]
        if Path(path).resolve() in [Path(f).resolve() for f in protected if f]:
            raise ValueError('Escolha outro nome. Os arquivos de origem e a base local não podem ser sobrescritos.')
        selected = [r for r in self._rows if r.get('exportar')]
        self._catalog.reserve(selected)
        for r in selected:
            if r['status']=='Pronto para reservar':
                r['status']='Reservado'
        self._save()
        if ext=='xlsx':
            export_xlsx(path,records,prepared=grade,headers=headers)
        else:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f,delimiter=';')
                writer.writerow(headers)
                for row in grade:
                    writer.writerow([str(v).replace('.',',') if isinstance(v,float) else "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in row])
        return dict(state=self._state(),path=path,children=len(records),parents=len(grade)-len(records))

    def _import_database(self, p):
        if self._rows:
            raise ValueError('Salve e conclua o lote atual antes de trocar a base de reservas. Reabra o aplicativo para importar a base anterior.')
        path = self._dialog(database=True)
        if not path:
            return None
        target = self._home/'reservas.sqlite3'
        if Path(path).resolve()==target.resolve():
            raise ValueError('Esta já é a base em uso.')
        with sqlite3.connect(f'{Path(path).as_uri()}?mode=ro',uri=True) as source:
            if not source.execute("SELECT 1 FROM sqlite_master WHERE name='reservations'").fetchone():
                raise ValueError('Este arquivo não contém uma base de reservas válida.')
            with sqlite3.connect(self._home/('backup-'+uuid4().hex[:8]+'.sqlite3')) as backup:
                self._catalog.db.backup(backup)
            source.backup(self._catalog.db)
        self._catalog.db.close()
        self._catalog = Workflow([],target)
        self._registration=Registration(self._catalog.db)
        return self._state()

    def _close(self):
        self._pool.submit(self._catalog.db.close).result()
        self._pool.shutdown(wait=True)

    def _export_records(self):
        self._photos.apply(self._rows,strict=True,force=True)
        records=self._catalog.export_rows(self._rows)
        source={r['codigo']:r for r in self._rows if r.get('exportar')}
        for record in records:
            row=source[record['codigo']]
            record.update(foto=row.get('foto',''),foto_pai=row.get('foto_pai',''))
            record.update(self._registration.details(self._items.get(row['referencia'],{})))
        return records

    def _profile_select(self,p):
        self._registration.select(p['id'])
        return self._state()

    def _profile_save(self,p):
        self._registration.save_profile(p)
        return self._state()

    def _layout_save(self,p):
        self._registration.save_layout(p)
        return self._state()

    def _layout_select(self,p):
        self._registration.select_layout(p['id'])
        return self._state()

    def _product_details(self,p):
        import copy
        targets=self._selected(p)
        if p.get('model'):
            models={(family(r['referencia']),r['grupo']) for r in targets}
            targets=[r for r in self._rows if (family(r['referencia']),r['grupo']) in models]
        fields={f['id'] for f in self._registration.profile()['fields']}
        changes=[]
        for row in targets:
            item=copy.deepcopy(self._items.get(row['referencia'],{}))
            values=copy.deepcopy(self._registration.details(item));replace=bool(p.get('overwrite'))
            if 'descricao' in p and (replace or not values['descricao']):values['descricao']=str(p['descricao']).strip()
            for key,value in p.get('atributos',{}).items():
                if key not in fields:raise ValueError('Atributo não encontrado no modelo ativo.')
                if replace or not values['atributos'].get(key):values['atributos'][key]=str(value).strip()
            self._registration.validate_values(values)
            item.setdefault('cadastros',{})[self._registration.profile()['id']]=values
            changes.append((row['referencia'],item))
        for ref,item in changes:self._items[ref]=item
        self._save()
        return self._state()

    def _choose_photo_folder(self,p):
        import webview
        selected=self._window.create_file_dialog(webview.FileDialog.FOLDER,directory=self._photos.folder)
        return str(selected[0] if isinstance(selected,(tuple,list)) else selected) if selected else None

    def _photo_settings(self,p):
        self._photos.configure(p.get('folder') or self._photos.folder,p.get('enabled',True))
        self._photos.apply(self._rows,strict=True,force=True)
        if self._source or self._rows:self._save()
        return self._state()

    def _restart_update(self,p):
        if not getattr(sys,'frozen',False) or not self._exit_callback:
            raise ValueError('Reiniciar para atualizar está disponível no aplicativo instalado.')
        if not self._updates.pending_installer():
            raise ValueError('Ainda não há uma atualização baixada e verificada. Use Verificar agora e aguarde o download.')
        if self._source or self._rows:
            self._save()
        if self._restart_requested:return dict(restarting=True)
        self._restart_requested=True
        import threading
        threading.Timer(.5,self._exit_callback).start()
        return dict(restarting=True)
