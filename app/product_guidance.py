"""Validação de material e situações apresentadas ao operador."""
import re
from criar_codigos import normal

VALID = ('Pronto para reservar', 'Reservado', 'Já cadastrado')
FILTERS = ('Todos', 'A cadastrar (novos e variações)', 'Novos modelos', 'Novas variações',
           'Já cadastrados no estoque', 'Precisam de atenção', 'Marcados para exportar')


def moissanite(reference, metadata=None):
    data = metadata or {}
    # MRS é a identificação presente nas referências deste cadastro.
    return bool(re.search(r'-MRS\d', normal(reference)) or 'MOISSAN' in normal(reference)
                or any('MOISSAN' in normal(data.get(k, '')) for k in ('grupo', 'tipo')))


def compatible(reference, group, metadata=None):
    return not moissanite(reference, metadata) or 'MOISSAN' in normal(group)


def situation(row):
    status = row['status']
    if status not in VALID:
        return 'Precisa de atenção', row['detalhe']
    if status == 'Já cadastrado':
        return 'Já cadastrado no estoque', 'Não cadastrar novamente. Fica fora da exportação por padrão.'
    kind = row.get('tipo_cadastro', 'Novo modelo')
    action = 'Cadastrar esta variação. Ela usa o mesmo número do modelo.' if kind == 'Nova variação' else 'Cadastrar este modelo e suas variações.'
    if status == 'Reservado':
        action += ' Código reservado neste computador; isso não confirma cadastro no ERP.'
    return kind, action


def visible(row, selected, search=''):
    label, _ = situation(row)
    match = (selected == 'Todos'
             or selected == 'A cadastrar (novos e variações)' and row['status'] in ('Pronto para reservar', 'Reservado')
             or selected == 'Novos modelos' and label == 'Novo modelo'
             or selected == 'Novas variações' and label == 'Nova variação'
             or selected == 'Já cadastrados no estoque' and row['status'] == 'Já cadastrado'
             or selected == 'Precisam de atenção' and row['status'] not in VALID
             or selected == 'Marcados para exportar' and row.get('exportar'))
    return bool(match and normal(search) in normal(' '.join(str(row.get(k, '')) for k in ('referencia', 'produto', 'codigo', 'grupo'))))
