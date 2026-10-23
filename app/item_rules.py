"""Regras de peso e unidade do cadastro."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def weight(value):
    if value is None or str(value).strip() == '':
        return None
    text = str(value).strip().replace(' ', '')
    if ',' in text:
        if '.' in text or text.count(',') > 1:
            raise ValueError('Use apenas uma vírgula ou um ponto decimal, sem separador de milhares.')
        text = text.replace(',', '.')
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise ValueError('Informe um peso numérico em gramas. Ex.: 2,35.') from None
    if not number.is_finite() or number <= 0 or number > Decimal('1000000000'):
        raise ValueError('O peso deve ser maior que zero e menor ou igual a 1.000.000.000 g.')
    return float(number)


def piece_unit(ref, group='', kind=''):
    def norm(v):
        return ''.join(c for c in unicodedata.normalize('NFKD', str(v)).upper() if not unicodedata.combining(c))
    kind, group, ref = norm(kind), norm(group), norm(ref)
    if 'BRINCO' in kind or 'BRINCO' in group:
        return 'PR'
    if any(k in kind for k in ('ANEL', 'GARGANTILHA', 'COLAR', 'PULSEIRA', 'PINGENTE', 'PIERCING', 'CORRENTE', 'TORNOZELEIRA')):
        return 'PC'
    return 'PR' if re.match(r'^BR(?=\d|[-_])', ref.strip()) else 'PC'
