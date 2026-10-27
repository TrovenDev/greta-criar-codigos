"""Formatos de exportação da Grade Lançar, salvos na base local."""
import copy
import json
from uuid import uuid4
from criar_codigos import product_parts
from grade_export import GRADE_HEADERS, grade_rows
from stock_io import header_key

BASE_SOURCES=[('codigo','Código'),('referencia','Referência'),('produto','Identificador técnico'),
              ('peso','Peso'),('unidade','Unidade'),('grupo','Categoria / GP'),('tamanho','Tamanho'),
              ('cor','Cor'),('obs','Moissanite ou flower'),('foto','Foto'),('pai','Código pai'),('tipo_linha','Tipo de linha')]
LEGACY_COLUMNS=[('aaa_codigo','codigo',''),('aaa_descricao','erp.aaa_descricao',''),('aaa_tipo','erp.aaa_tipo',''),
    ('aaa_almox','fixed','01'),('aaa_um','erp.aaa_um',''),('aaa_grupo','erp.aaa_grupo',''),('aaa_refbase','erp.aaa_refbase',''),
    ('aaa_lingrade','fixed',''),('aaa_colgrade','fixed',''),('aaa_status','erp.aaa_status',''),
    ('aaa_codgrade','erp.aaa_produtobase',''),('aaa_codlingrade','tamanho',''),('aaa_codcolgrade','cor',''),
    ('aaa_posipi','erp.aaa_posipi',''),('aaa_fornecedor','erp.aaa_fornecedor',''),('aaa_codrefforn','erp.aaa_codrefforn',''),
    ('aaa_integracao','fixed','001'),('aaa_foto','erp.aaa_foto',''),('aaa_pesogramas','erp.aaa_pesogramas',''),
    ('aaa_fatconv','erp.aaa_fatconv',''),('aaa_um2','erp.aaa_um2',''),('aaa_peso','erp.aaa_peso',''),('aaa_obs','obs','')]
DEFAULT_LAYOUTS=[
    dict(id='standard',name='Grade TAM e COR',parents=True,columns=[dict(header=h,source='erp.'+h,value='') for h in GRADE_HEADERS]),
    dict(id='legacy',name='Configurador 01',parents=False,columns=[dict(header=h,source=s,value=v) for h,s,v in LEGACY_COLUMNS]),
]


def category_label(group):
    text=' '.join(str(group or '').split()).upper()
    return next((name for name in ('MOISSANITE','FLOWER') if name in text),'')


class Registration:
    def __init__(self,db):
        self.db=db
        db.execute('CREATE TABLE IF NOT EXISTS registration_config (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        saved=db.execute('SELECT payload FROM registration_config WHERE id=1').fetchone()
        self.config=self._load(json.loads(saved[0]) if saved else {})
        self._save()

    def _load(self,saved):
        if 'profiles' in saved:
            # Bases criadas com modelos de empresa: mantém só os formatos personalizados do modelo ativo.
            profile=next((p for p in saved['profiles'] if p['id']==saved.get('active')),saved['profiles'][0])
            layouts=[l for l in profile.get('layouts',[]) if l['id'] not in {d['id'] for d in DEFAULT_LAYOUTS}]
            for layout in layouts:layout['columns']=[c for c in layout['columns'] if not c['source'].startswith('attr.')]
            layouts=DEFAULT_LAYOUTS+layouts
            selected=profile.get('layout','standard')
        else:
            layouts=saved.get('layouts',[])
            known={l['id'] for l in layouts}
            layouts=[copy.deepcopy(d) for d in DEFAULT_LAYOUTS if d['id'] not in known]+layouts
            selected=saved.get('layout','standard')
        if selected not in {l['id'] for l in layouts}:selected='standard'
        return dict(layout=selected,layouts=layouts)

    def _save(self):
        with self.db:self.db.execute('INSERT INTO registration_config VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(json.dumps(self.config,ensure_ascii=False),))

    def sources(self):
        return [dict(id=k,label=v) for k,v in BASE_SOURCES]+[dict(id='erp.'+h,label=h) for h in GRADE_HEADERS]

    def snapshot(self):
        return dict(layout=self.config['layout'],layouts=copy.deepcopy(self.config['layouts']),sources=self.sources())

    def save_layout(self,payload):
        columns=[];headers=set();allowed={s['id'] for s in self.sources()}
        if not 1<=len(payload.get('columns',[]))<=200:raise ValueError('Defina de 1 a 200 colunas para exportar.')
        for c in payload['columns']:
            label=str(c.get('header','')).strip();source=c.get('source','')
            if not label or header_key(label) in headers:raise ValueError('Preencha cabeçalhos distintos para todas as colunas.')
            if source!='fixed' and source not in allowed:raise ValueError('Escolha a origem de cada coluna.')
            headers.add(header_key(label));columns.append(dict(header=label,source=source,value=str(c.get('value',''))))
        name=str(payload.get('name','')).strip()
        if not name:raise ValueError('Dê um nome ao formato de exportação.')
        identifier=payload.get('id') or uuid4().hex[:12]
        layout=dict(id=identifier,name=name,parents=bool(payload.get('parents',True)),columns=columns)
        layouts=self.config['layouts']
        index=next((i for i,l in enumerate(layouts) if l['id']==identifier),None)
        if index is None:layouts.append(layout)
        else:layouts[index]=layout
        self.config['layout']=identifier;self._save()

    def select_layout(self,identifier):
        if not any(l['id']==identifier for l in self.config['layouts']):raise ValueError('Formato de exportação não encontrado.')
        self.config['layout']=identifier;self._save()

    def export(self,records):
        grade=grade_rows(records)
        for r in records:
            size,_,color=product_parts(r['produto'])[3].partition(' ')
            r.update(tamanho=size,cor=color,obs=category_label(r.get('grupo','')))
        layout=next(l for l in self.config['layouts'] if l['id']==self.config['layout'])
        children=[];by_parent={}
        for r,g in zip(records,grade):
            parent=g[17];by_parent.setdefault(parent,[]).append(r)
            children.append(dict(r,pai=parent,tipo_linha='Variação',**{'erp.'+h:v for h,v in zip(GRADE_HEADERS,g)}))
        parents=[]
        for g in grade[len(records):]:
            members=by_parent[g[2]]
            values=dict(codigo=g[2],referencia=g[4],produto=f'{g[0]}-{g[1]}',peso=0,unidade=g[9],grupo=members[0]['grupo'],
                        tamanho='',cor='',obs=category_label(members[0]['grupo']),foto=g[15] or '',pai='',tipo_linha='Pai')
            values.update({'erp.'+h:v for h,v in zip(GRADE_HEADERS,g)});parents.append(values)
        def cell(row,column):
            if column['source']=='fixed':return column.get('value','')
            return row.get(column['source'],'')
        rows=[[cell(r,c) for c in layout['columns']] for r in children+(parents if layout['parents'] else [])]
        return [c['header'] for c in layout['columns']],rows,layout['name']
