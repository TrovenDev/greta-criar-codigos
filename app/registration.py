"""Modelos de cadastro e exportação configuráveis, salvos na base local."""
import copy
import json
import re
from uuid import uuid4
from criar_codigos import product_parts
from grade_export import GRADE_HEADERS,LEGACY_HEADERS,grade_rows,legacy_rows
from stock_io import header_key
from product_guidance import compatible

DEFAULT_FIELDS=[('faixa_etaria','Faixa etária'),('estilo','Estilo'),('pedra','Pedra'),('genero','Gênero'),('tema','Tema')]
BASE_SOURCES=[('codigo','Código'),('referencia','Referência'),('descricao','Descrição escrita'),
              ('produto','Identificador técnico'),('peso','Peso'),('unidade','Unidade'),
              ('grupo','Categoria / GP'),('foto','Foto'),('pai','Código pai'),('tipo_linha','Tipo de linha')]


class Registration:
    def __init__(self,db):
        self.db=db
        db.execute('CREATE TABLE IF NOT EXISTS registration_config (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        saved=db.execute('SELECT payload FROM registration_config WHERE id=1').fetchone()
        self.config=json.loads(saved[0]) if saved else dict(active='troven',profiles=[dict(id='troven',name='Troven',
            fields=[dict(id=k,label=v,options=[],required=False) for k,v in DEFAULT_FIELDS],description_required=False,layout='standard',layouts=[])])
        self._save()

    def _save(self):
        with self.db:self.db.execute('INSERT INTO registration_config VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(json.dumps(self.config,ensure_ascii=False),))

    def profile(self):
        return next(p for p in self.config['profiles'] if p['id']==self.config['active'])

    def sources(self,profile=None):
        p=profile or self.profile()
        return [dict(id=k,label=v) for k,v in BASE_SOURCES]+[dict(id='attr.'+f['id'],label=f['label']) for f in p['fields']]+[dict(id='erp.'+h,label=h) for h in GRADE_HEADERS]

    def snapshot(self):
        return dict(config=copy.deepcopy(self.config),profile=copy.deepcopy(self.profile()),sources=self.sources())

    def select(self,identifier):
        if not any(p['id']==identifier for p in self.config['profiles']):raise ValueError('Modelo de empresa não encontrado.')
        self.config['active']=identifier;self._save()

    def save_profile(self,payload):
        name=str(payload.get('name','')).strip()
        if not name:raise ValueError('Informe o nome da empresa ou do modelo.')
        identifier=payload.get('id')
        old=next((p for p in self.config['profiles'] if p['id']==identifier),None)
        if identifier and not old:raise ValueError('Modelo não encontrado.')
        fields=[];ids=set();labels=set()
        raw=payload.get('fields',[])
        if len(raw)>50:raise ValueError('Use até 50 atributos por modelo.')
        for f in raw:
            label=str(f.get('label','')).strip();key=f.get('id') or uuid4().hex[:12]
            if not label or not header_key(label):raise ValueError('Preencha o nome de cada atributo.')
            if header_key(label) in {header_key(v) for _,v in BASE_SOURCES}|{'descricao','gp','tipo','tamanhoecor'}:
                raise ValueError('O nome '+label+' já identifica um campo básico. Escolha outro nome para o atributo.')
            if key in ids or header_key(label) in labels:raise ValueError('Os atributos precisam de nomes distintos.')
            if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_]+',key):raise ValueError('Identificador de atributo inválido.')
            ids.add(key);labels.add(header_key(label))
            options=list(dict.fromkeys(str(v).strip() for v in f.get('options',[]) if str(v).strip()))
            fields.append(dict(id=key,label=label,options=options,required=bool(f.get('required'))))
        layouts=copy.deepcopy(old['layouts']) if old else []
        for layout in layouts:
            for col in layout['columns']:
                if col.get('source','').startswith('attr.') and col['source'][5:] not in ids:
                    raise ValueError('Um atributo removido está em uso no formato '+layout['name']+'. Ajuste esse formato primeiro.')
        profile=dict(id=identifier or uuid4().hex[:12],name=name,fields=fields,description_required=bool(payload.get('description_required')),layout=old['layout'] if old else 'complete',layouts=layouts)
        if old:self.config['profiles'][self.config['profiles'].index(old)]=profile
        else:self.config['profiles'].append(profile)
        self.config['active']=profile['id'];self._save()

    def save_layout(self,payload):
        profile=self.profile();columns=[];headers=set();allowed={s['id'] for s in self.sources()}
        if not 1<=len(payload.get('columns',[]))<=200:raise ValueError('Defina de 1 a 200 colunas para exportar.')
        for c in payload['columns']:
            label=str(c.get('header','')).strip();source=c.get('source','')
            if not label or header_key(label) in headers:raise ValueError('Preencha cabeçalhos distintos para todas as colunas.')
            if source!='fixed' and source not in allowed:raise ValueError('Escolha a origem de cada coluna.')
            headers.add(header_key(label));columns.append(dict(header=label,source=source,value=str(c.get('value',''))))
        name=str(payload.get('name','')).strip()
        if not name:raise ValueError('Dê um nome ao formato de exportação.')
        identifier=payload.get('id') or uuid4().hex[:12]
        if identifier in ('standard','complete','legacy'):raise ValueError('Crie uma cópia para personalizar um formato inicial.')
        layout=dict(id=identifier,name=name,parents=bool(payload.get('parents',True)),columns=columns)
        profile['layouts']=[l for l in profile['layouts'] if l['id']!=identifier]+[layout]
        profile['layout']=identifier;self._save()

    def select_layout(self,identifier):
        if identifier not in ('standard','complete','legacy') and not any(l['id']==identifier for l in self.profile()['layouts']):raise ValueError('Formato de exportação não encontrado.')
        self.profile()['layout']=identifier;self._save()

    def import_fields(self):
        return {'cad.descricao':'Descrição escrita',**{'cad.'+f['id']:f['label'] for f in self.profile()['fields']}}

    def values(self,item):
        return item.get('cadastros',{}).get(self.profile()['id'],{})

    def details(self,item):
        values=self.values(item)
        return dict(descricao=values.get('descricao',''),atributos=dict(values.get('atributos',{})))

    def validate_values(self,values):
        allowed={f['id']:f for f in self.profile()['fields']}
        for key,value in values.get('atributos',{}).items():
            if key not in allowed:continue  # Conserva valores de atributos retirados do modelo.
            options=allowed[key]['options']
            if value and options and value not in options:raise ValueError('Escolha uma opção válida para '+allowed[key]['label']+'.')

    def missing(self,details):
        p=self.profile();missing=[]
        if p['description_required'] and not details.get('descricao','').strip():missing.append('Descrição')
        for f in p['fields']:
            value=details.get('atributos',{}).get(f['id'],'')
            if f['required'] and not value:missing.append(f['label'])
            elif value and f['options'] and value not in f['options']:missing.append(f['label']+' (opção inválida)')
            if header_key(f['label'])=='pedra' and not compatible(details.get('referencia',''),details.get('grupo',''),dict(tipo=value)):
                missing.append('Categoria compatível com moissanite')
        return missing

    def export(self,records):
        for r in records:
            missing=self.missing(r)
            if missing:raise ValueError(r['referencia']+': confira '+', '.join(missing)+'.')
        # Todos os formatos passam pelas mesmas validações de pais, códigos e unidades.
        descriptions={}
        for r in records:
            parts=product_parts(r['produto'])
            if parts:descriptions.setdefault(parts[0]+parts[2],set()).add(r.get('descricao',''))
        for r in records:
            parts=product_parts(r['produto'])
            if parts:
                values=descriptions[parts[0]+parts[2]]
                r['descricao_pai']=next(iter(values)) if len(values)==1 else ''
        grade=grade_rows(records)
        profile=self.profile();identifier=profile['layout']
        if identifier=='standard':return list(GRADE_HEADERS),grade,'Grade Lançar'
        if identifier=='legacy':return list(LEGACY_HEADERS),legacy_rows(records,grade[:len(records)]),'Grade Lançar antiga'
        if identifier=='complete':
            columns=[dict(header=label,source=source) for source,label in BASE_SOURCES]+[dict(header=f['label'],source='attr.'+f['id']) for f in profile['fields']]
            layout=dict(name='Cadastro completo',parents=True,columns=columns)
        else:layout=next(l for l in profile['layouts'] if l['id']==identifier)
        children=[];by_parent={}
        for r,g in zip(records,grade):
            parent=g[17];by_parent.setdefault(parent,[]).append(r)
            children.append(dict(r,pai=parent,tipo_linha='Variação',**{'erp.'+h:v for h,v in zip(GRADE_HEADERS,g)}))
        parents=[]
        for g in grade[len(records):]:
            members=by_parent[g[2]]
            def common(getter):
                values={getter(r) for r in members}
                return next(iter(values)) if len(values)==1 else ''
            values=dict(codigo=g[2],referencia=g[4],descricao=common(lambda r:r.get('descricao','')),produto=f'{g[0]}-{g[1]}',peso=0,unidade=g[9],grupo=members[0]['grupo'],foto=g[15] or '',pai='',tipo_linha='Pai',atributos={f['id']:common(lambda r:r.get('atributos',{}).get(f['id'],'')) for f in profile['fields']})
            values.update({'erp.'+h:v for h,v in zip(GRADE_HEADERS,g)});parents.append(values)
        def cell(row,column):
            source=column['source']
            if source=='fixed':return column.get('value','')
            if source.startswith('attr.'):return row.get('atributos',{}).get(source[5:],'')
            return row.get(source,'')
        rows=[[cell(r,c) for c in layout['columns']] for r in children+(parents if layout['parents'] else [])]
        return [c['header'] for c in layout['columns']],rows,layout['name']
