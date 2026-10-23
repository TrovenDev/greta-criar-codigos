"""Fluxo estoque -> referências -> código, referência e peso."""
import csv
import json
import re
import sys
from pathlib import Path
from item_rules import weight, piece_unit

from criar_codigos import Catalog, normal, family, product_parts
from stock_io import stock_sheets, read_stock, export_xlsx
import troven_brand as brand
from group_picker import GroupPicker
from grade_export import grade_rows, GRADE_HEADERS
from category_rules import RuleStore, stock_patterns
from product_guidance import compatible, moissanite, situation, visible, FILTERS

class Workflow(Catalog):
    def __init__(self, records, database):
        super().__init__(records, database)
        self.db.execute('CREATE TABLE IF NOT EXISTS weights (referencia TEXT, grupo TEXT, peso REAL, PRIMARY KEY(referencia,grupo))')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(weights)')}
        if 'venda_por' not in columns:
            self.db.execute("ALTER TABLE weights ADD COLUMN venda_por TEXT DEFAULT 'Peso'")
        if 'context' not in columns:
            self.db.execute("ALTER TABLE weights ADD COLUMN context TEXT DEFAULT ''")
        self.db.execute('CREATE TABLE IF NOT EXISTS workflow_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
        self.db.commit()
        self.rules = RuleStore(self.db)
        self._learned_cache = None

    def last_number(self, stock_only=False):
        rows = self.records if stock_only else self.all_records()
        return max((p[1] for r in rows if (p := product_parts(r['produto']))), default=0)

    def set_weight(self, row, value):
        number = weight(value)
        mode = 'Unidade' if number is None else 'Peso'
        number = 1 if number is None else number
        with self.db:
            self.db.execute('INSERT INTO weights(referencia,grupo,peso,venda_por,context) VALUES(?,?,?,?,?) ON CONFLICT(referencia,grupo) DO UPDATE SET peso=excluded.peso,venda_por=excluded.venda_por,context=excluded.context', (normal(row['referencia']), row['grupo'], number, mode, row.get('_context', '')))
        row['peso'] = number
        row['venda_por'] = mode
        row['unidade'] = 'G' if mode == 'Peso' else piece_unit(row['referencia'], row['grupo'], row.get('tipo', ''))

    def saved_weight(self, ref, group):
        result = self.db.execute('SELECT peso FROM weights WHERE referencia=? AND grupo=?', (normal(ref), group)).fetchone()
        return result[0] if result else None

    def infer_suffix(self, ref, group, source_rows=None):
        parts = normal(ref).split()
        if len(parts) == 3 and parts[-1].isdigit():
            return parts[-1] + ' ' + parts[1]
        if len(parts) == 2:
            relatives = [r for r in (source_rows if source_rows is not None else self.all_records()) if r['grupo'] == group and family(r['referencia']) == family(ref)]
            sizes = set()
            for r in relatives:
                p = product_parts(r['produto'])
                if p and len(p[3].split()) == 2:
                    sizes.add(p[3].split()[0])
            if len(sizes) == 1:
                return next(iter(sizes)) + ' ' + parts[1]
            length = re.search(r'(?:^|[-_])(\d+(?:\.\d+)?)CM(?:[-_]|$)', parts[0])
            if length:
                return length[1] + ' ' + parts[1]
        return ''

    def detect_group(self, ref, lookup=None):
        if lookup is None:
            records = self.all_records()
            exact = [r for r in records if normal(r['referencia']) == normal(ref)]
            relatives = [r for r in records if family(r['referencia']) == family(ref)]
        else:
            exact = lookup[0].get(normal(ref), [])
            relatives = lookup[1].get(family(ref), [])
        def groups(rows):
            return sorted({r['grupo'] for r in rows if r['grupo']})
        if exact:
            found = groups(exact)
            return (found[0] if len(found) == 1 else '', found, 'Referência no estoque')
        parts = normal(ref).split()
        color = parts[1] if len(parts) in (2, 3) else ''
        same_color = [r for r in relatives if len(normal(r['referencia']).split()) in (2, 3) and normal(r['referencia']).split()[1] == color] if color else []
        if same_color:
            found = groups(same_color)
            return (found[0] if len(found) == 1 else '', found, 'Modelo e cor no estoque')
        found = groups(relatives)
        return (found[0] if len(found) == 1 else '', found, 'Modelo no estoque' if relatives else 'Modelo novo')

    def prepare(self, text, group='', suffix='', assignments=None, sizes=None, items=None):
        if not self.records:
            raise ValueError('Selecione o Excel de estoque na etapa 1 antes de gerar os códigos.')
        allowed_groups = {r['grupo'] for r in self.records}
        # Primeira passagem valida todos os pesos antes de alterar o lote.
        inputs = []
        assignments, sizes = assignments or {}, sizes or {}
        items = items or {}
        records = self.all_records()
        exact_index, model_index = {}, {}
        for record in records:
            exact_index.setdefault(normal(record['referencia']), []).append(record)
            model_index.setdefault(family(record['referencia']), []).append(record)
        key = (id(self.records), len(self.records))
        if self._learned_cache is None or self._learned_cache[0] != key:
            self._learned_cache = (key, stock_patterns(self.records))
        learned = self._learned_cache[1]
        saved_rules = self.rules.all()
        for line in text.splitlines():
            if not line.strip():
                continue
            fields = [f.strip() for f in line.split('\t')]
            if len(fields) > 4 or not fields[0]:
                raise ValueError('Cole até quatro colunas: referência, tamanho e cor, peso (g), grupo (GP).')
            ref = normal(fields[0])
            meta = items.get(ref, {})
            lookup = (exact_index, model_index)
            if moissanite(ref, meta):
                lookup = ({ref: [r for r in exact_index.get(ref, []) if compatible(ref, r['grupo'], meta)]},
                          {family(ref): [r for r in model_index.get(family(ref), []) if compatible(ref, r['grupo'], meta)]})
            detected, candidates, origin = self.detect_group(ref, lookup)
            chosen = assignments.get(ref, '') or (fields[3] if len(fields) > 3 and fields[3] else '') or group
            if not chosen and not detected:
                inferred, pattern_groups, pattern_origin = self.rules.resolve(ref, items.get(ref, {}).get('grupo', ''), learned, saved_rules)
                if pattern_origin:
                    detected, candidates, origin = inferred, pattern_groups, pattern_origin
            line_group = chosen or detected
            if chosen:
                origin = 'Categoria informada'
            # Aceita tanto o GP completo quanto o prefixo de um GP existente.
            if line_group and line_group not in allowed_groups:
                matches = [g for g in allowed_groups if g.split('-')[0] == line_group]
                if len(matches) != 1:
                    raise ValueError(f'Grupo não encontrado no estoque: {line_group}.')
                line_group = matches[0]
            if line_group and not compatible(ref, line_group, meta):
                line_group = ''
                origin = 'Material incompatível: moissanite exige um grupo de moissanite.'
            if moissanite(ref, meta):
                candidates = [g for g in candidates if compatible(ref, g, meta)]
            explicit = sizes.get(ref, '') or (fields[1] if len(fields) > 1 else '')
            tail = explicit or self.infer_suffix(ref, line_group, model_index.get(family(ref), [])) or suffix
            value = weight(fields[2]) if len(fields) > 2 else None
            inputs.append((ref, line_group, tail, value, candidates, origin))
        if not inputs:
            raise ValueError('Cole pelo menos uma referência na etapa 2.')
        # Um catálogo de trabalho reserva a sequência dentro deste lote, inclusive entre GPs.
        scratch = Catalog(records.copy(), ':memory:')
        result, seen = [], set()
        try:
            for ref, gp, tail, value, candidates, origin in inputs:
                key = (ref, gp)
                if gp:
                    r = scratch.analyze(ref + ('\t' + tail if tail else ''), gp)[0]
                else:
                    detail = 'Escolha entre as categorias do estoque: ' + '; '.join(candidates) if candidates else 'Modelo novo: selecione as linhas e informe a categoria.'
                    if origin.startswith(('Conflito', 'Material incompatível')):
                        detail = origin
                    elif moissanite(ref, items.get(ref, {})):
                        detail = 'Moissanite: selecione um grupo de moissanite. Grupos de outros materiais foram desconsiderados.'
                    r = dict(referencia=ref, grupo='', codigo='', produto='', status='Escolha a categoria', detalhe=detail)
                r['categorias_possiveis'] = candidates
                r['origem_categoria'] = origin
                r['tamanho_cor'] = tail
                # O primeiro item cria o modelo; os seguintes são variações, todos a cadastrar.
                prior_model = any(s['grupo'] == gp and family(s['referencia']) == family(ref) for s in scratch.records)
                r['tipo_cadastro'] = 'Nova variação' if prior_model else 'Novo modelo'
                if key in seen:
                    r.update(status='Repetido no lote', codigo='', produto='', detalhe='Mantenha uma ocorrência por referência e grupo.')
                elif r['status'] == 'Pronto para reservar':
                    scratch.records.append({k: r[k] for k in ('codigo', 'produto', 'referencia', 'grupo')})
                if r['status'] == 'Já cadastrado':
                    # Diferencia estoque efetivo de uma reserva local anterior.
                    if not any(normal(s['codigo']) == normal(r['codigo']) for s in self.records):
                        r['status'] = 'Reservado'
                meta = items.get(ref, {})
                saved = self.db.execute('SELECT peso,venda_por,context FROM weights WHERE referencia=? AND grupo=?', (ref, r['grupo'])).fetchone()
                r['_context'] = meta.get('context', '')
                r['tipo'] = meta.get('tipo', '') or meta.get('grupo', '')
                r['categoria_origem'] = meta.get('grupo', '')
                if saved and (saved[2] or '') == r['_context']:
                    r['peso'], r['venda_por'] = saved[0], saved[1] or 'Peso'
                else:
                    r['peso'] = value if value is not None else 1
                    r['venda_por'] = 'Peso' if value is not None else 'Unidade'
                r['unidade'] = 'G' if r['venda_por'] == 'Peso' else piece_unit(ref, r['grupo'], r['tipo'])
                r['exportar'] = r['status'] in ('Pronto para reservar', 'Reservado')
                result.append(r)
                seen.add(key)
            return result
        finally:
            scratch.db.close()

    def save_session(self, rows, source='', sheet='', text='', group='', suffix='', assignments=None, sizes=None, items=None, new_source=''):
        payload = json.dumps(dict(rows=rows, source=source, sheet=sheet, text=text, group=group, suffix=suffix, assignments=assignments or {}, sizes=sizes or {}, items=items or {}, new_source=new_source), ensure_ascii=False)
        with self.db:
            self.db.execute('INSERT INTO workflow_state(id,payload) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (payload,))

    def session(self):
        row = self.db.execute('SELECT payload FROM workflow_state WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}

    def export_rows(self, rows):
        selected = [r for r in rows if r.get('exportar')]
        if not selected:
            raise ValueError('Não há linhas marcadas para exportar.')
        result, codes = [], set()
        for r in selected:
            if not compatible(r['referencia'], r['grupo'], dict(grupo=r.get('categoria_origem', ''), tipo=r.get('tipo', ''))):
                raise ValueError(f"{r['referencia']}: moissanite exige um grupo de moissanite. Reanalise o lote.")
            if r['status'] not in ('Reservado', 'Já cadastrado', 'Pronto para reservar'):
                raise ValueError(f"Resolva a pendência da referência {r['referencia']} antes de exportar.")
            number = weight(r.get('peso'))
            if number is None:
                raise ValueError(f"Preencha o peso de {r['referencia']} antes de exportar.")
            if r['codigo'] in codes:
                raise ValueError(f"Código repetido no cadastro: {r['codigo']}.")
            codes.add(r['codigo'])
            mode = r.get('venda_por', 'Peso')
            unit = 'G' if mode == 'Peso' else piece_unit(r['referencia'], r['grupo'], r.get('tipo', ''))
            result.append(dict(codigo=r['codigo'], referencia=r['referencia'], peso=number if mode == 'Peso' else 1, unidade=unit, produto=r['produto'], grupo=r['grupo']))
        return result


