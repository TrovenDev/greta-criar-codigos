"""Contrato de importação fornecido em dmaaa.xlsx."""
import re
from decimal import Decimal
from criar_codigos import normal, family, product_parts

GRADE_HEADERS = (
    'aaa_grupo', 'aaa_refbase', 'aaa_codigo', 'aaa_descricao',
    'aaa_codrefforn', 'aaa_status', 'aaa_fornecedor', 'aaa_pesogramas',
    'aaa_fatconv', 'aaa_um', 'aaa_um2', 'aaa_configurador', 'aaa_posipi',
    'aaa_peso', 'aaa_tipo', 'aaa_foto', 'aaa_obs', 'aaa_produtobase', 'aaa_integracao',
)


def grade_rows(records):
    children, parents = [], {}
    codes = set()
    for r in records:
        parts = product_parts(r.get('produto', ''))
        if not parts:
            raise ValueError(f"Produto sem grupo e sequência: {r['referencia']}.")
        prefix, _, sequence, _ = parts
        base = prefix + sequence
        model = family(r['referencia'])
        suppliers = re.findall(r'-F(\d+)(?=$|[-_\s])', normal(r['referencia']))
        supplier = suppliers[-1] if suppliers else ''
        grams = r['peso']
        kg = float(Decimal(str(grams)) / Decimal(1000))
        child = [prefix, sequence, r['codigo'], r['produto'], r['referencia'], 'A', supplier,
                 grams, grams, r['unidade'], 'UN', None, '71132000', kg, 'PV', '', None, base, '002']
        if r['codigo'] in codes:
            raise ValueError(f"Código repetido na grade: {r['codigo']}.")
        codes.add(r['codigo'])
        children.append(child)
        parent = [prefix, sequence, base, f'{prefix}-{sequence}', model, 'A', supplier,
                  0, 50, r['unidade'], 'UN', '001', '71132000', 0, 'PV', None, None, None, '002']
        if base in parents and parents[base][4] != model:
            raise ValueError(f'O código pai {base} está associado a referências-base diferentes. Revise a numeração antes de exportar.')
        if base in parents and parents[base][9] != r['unidade']:
            raise ValueError(f'O modelo {model} tem variações com unidades diferentes ({parents[base][9]} e {r["unidade"]}). Confira a venda por peso ou por unidade nas variações antes de exportar: o pai precisa seguir uma única unidade.')
        parents.setdefault(base, parent)
    if any(code in codes for code in parents):
        raise ValueError('Um código de variação coincide com um código pai. Revise os códigos.')
    return children + list(parents.values())
