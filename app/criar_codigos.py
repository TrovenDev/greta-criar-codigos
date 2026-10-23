"""Gerador local de códigos. Apenas biblioteca padrão do Python."""
import csv
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HOME = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


def normal(value):
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).upper()


def family(ref):
    return normal(ref).split(' ')[0]


def product_parts(product):
    m = re.fullmatch(r'([A-Z0-9]+)-(\d+)(?:\s+(.*))?', normal(product))
    return (m[1], int(m[2]), m[2], m[3] or '') if m else None


def read_xlsx(path):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns)]
        book = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next((s for s in book.findall('m:sheets/m:sheet', ns) if s.get('name', '').startswith('1 - Estoque')), None)
        if sheet is None:
            raise ValueError('Não encontrei a aba 1 - Estoque. Selecione a planilha Criar Códigos.')
        rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.get('Target') for r in rels if r.get('Id') == rid)
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        records = []
        for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row', ns):
            if int(row.get('r')) == 1:
                continue
            cells = {}
            for c in row:
                col = re.sub(r'\d', '', c.get('r', ''))
                v = c.find('m:v', ns)
                text = v.text if v is not None else ''
                if c.get('t') == 's':
                    text = strings[int(text)] if text else ''
                elif c.get('t') == 'inlineStr':
                    text = ''.join(t.text or '' for t in c.findall('.//m:t', ns))
                cells[col] = text or ''
            if cells.get('A'):
                records.append(dict(zip(('codigo', 'produto', 'referencia', 'grupo'), (cells.get(k, '') for k in ('A', 'B', 'C', 'K')))))
        if not records or any(not r['referencia'] or not r['grupo'] for r in records):
            raise ValueError('A base está vazia ou contém registros sem referência/grupo.')
        return records


class Catalog:
    def __init__(self, records, database):
        self.records = records
        self.db = sqlite3.connect(database)
        self.db.execute('CREATE TABLE IF NOT EXISTS reservations (codigo TEXT PRIMARY KEY, produto TEXT NOT NULL, referencia TEXT NOT NULL, grupo TEXT NOT NULL, criado TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(referencia, grupo))')

    def all_records(self):
        local = [dict(zip(('codigo', 'produto', 'referencia', 'grupo'), r)) for r in self.db.execute('SELECT codigo,produto,referencia,grupo FROM reservations')]
        return self.records + local

    def analyze(self, raw, group='', suffix='', start=''):
        records = self.all_records()
        group = group.strip()
        prefix = group.split('-')[0]
        used = {normal(r['codigo']) for r in records}
        current = max((p[1] for r in records if (p := product_parts(r['produto']))), default=0)
        nextnum = int(start) if str(start).strip() else current + 1
        if nextnum <= current:
            raise ValueError(f'O número inicial deve ser maior que {current}, o último número da sequência geral.')
        batch_families, seen, result = {}, set(), []
        for line in raw.splitlines():
            if not line.strip():
                continue
            fields = line.split('\t')
            ref = normal(fields[0])
            tail = normal(fields[1]) if len(fields) > 1 else normal(suffix)
            item = dict(referencia=ref, grupo=group, produto='', codigo='', status='', detalhe='')
            exact = [r for r in records if normal(r['referencia']) == ref and (not group or r['grupo'] == group)]
            if not ref or len(fields) > 2:
                item.update(status='Formato inválido', detalhe='Cole uma ou duas colunas: referência e tamanho e cor.')
            elif ref in seen:
                item.update(status='Repetido no lote', detalhe='Mantenha apenas uma ocorrência.')
            elif exact:
                ids = {normal(r['codigo']) for r in exact}
                if len(ids) > 1:
                    item.update(status='Referência ambígua', detalhe='Códigos: ' + ', '.join(sorted(ids)))
                else:
                    item.update(status='Já cadastrado', codigo=exact[0]['codigo'], produto=exact[0]['produto'], grupo=exact[0]['grupo'])
            elif not group:
                item.update(status='Escolha o grupo', detalhe='O grupo evita misturar famílias com a mesma referência.')
            elif not tail:
                item.update(status='Informe tamanho e cor', detalhe='Preencha Tamanho e cor, como 18 W ou J W, ou cole esses dados na segunda coluna.')
            elif not re.fullmatch(r'[A-Z0-9]+(?: [A-Z0-9]+)*', tail):
                item.update(status='Tamanho e cor inválidos', detalhe='Use letras, números e espaços. Ex.: 18 CZ04.')
            else:
                relatives = [r for r in records if r['grupo'] == group and family(r['referencia']) == family(ref)]
                parts = [product_parts(r['produto']) for r in relatives]
                roots = {(p[0], p[2]) for p in parts if p}
                if relatives and (any(p is None or p[0] != prefix for p in parts) or len(roots) != 1):
                    item.update(status='Família ambígua', detalhe='Há numerações ou prefixos diferentes. Revise a base antes de gerar.')
                else:
                    if roots:
                        root = next(iter(roots))[1]
                    elif family(ref) in batch_families:
                        root = batch_families[family(ref)]
                    else:
                        root = str(nextnum).zfill(4)
                        batch_families[family(ref)] = root
                        nextnum += 1
                    product = f'{prefix}-{root} {tail}'
                    code = product.replace('-', '').replace(' ', '')
                    if code in used:
                        item.update(status='Código em uso', codigo=code, produto=product, detalhe='O código já existe. Confira tamanho, cor e referência.')
                    else:
                        item.update(status='Pronto para reservar', codigo=code, produto=product, detalhe='Variação existente' if roots else 'Novo modelo')
                        used.add(code)
            seen.add(ref)
            result.append(item)
        return result

    def reserve(self, rows):
        ready = [r for r in rows if r['status'] == 'Pronto para reservar']
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing = self.all_records()
            ids = {normal(r['codigo']) for r in existing}
            keys = {(normal(r['referencia']), r['grupo']) for r in existing}
            last = max((p[1] for r in existing if (p := product_parts(r['produto']))), default=0)
            for r in ready:
                key = (normal(r['referencia']), r['grupo'])
                if normal(r['codigo']) in ids or key in keys:
                    raise ValueError('A base mudou ou há duplicidade. Analise o lote novamente.')
                if r['detalhe'] == 'Novo modelo' and product_parts(r['produto'])[1] <= last:
                    raise ValueError('A sequência geral avançou desde a análise. Analise o lote novamente.')
                self.db.execute('INSERT INTO reservations(codigo,produto,referencia,grupo) VALUES(?,?,?,?)', tuple(r[k] for k in ('codigo', 'produto', 'referencia', 'grupo')))
                ids.add(normal(r['codigo']))
                keys.add(key)
        return len(ready)


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title('Criar Códigos • Cadastro de produtos')
    root.geometry('1180x760')
    root.minsize(960, 650)
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TLabel', font=('Segoe UI', 10))
    style.configure('TButton', padding=7, font=('Segoe UI', 10))
    style.configure('Treeview', rowheight=28, font=('Segoe UI', 10))
    style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Criar códigos de produtos', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='1. Escolha o grupo   2. Cole as referências   3. Confira o resultado   4. Reserve e exporte').pack(anchor='w', pady=(5, 12))
    catalog = Catalog(json.loads((HOME / 'base.json').read_text(encoding='utf-8')), HOME / 'reservas.sqlite3')
    status = tk.StringVar()
    controls = ttk.Frame(frame)
    controls.pack(fill='x')
    group = tk.StringVar()
    ttk.Label(controls, text='Grupo (GP)').grid(row=0, column=0, sticky='w')
    combo = ttk.Combobox(controls, textvariable=group, state='readonly', width=61)
    combo.grid(row=1, column=0, sticky='w', padx=(0, 15))
    suffix = tk.StringVar()
    ttk.Label(controls, text='Sufixo padrão: tamanho e cor').grid(row=0, column=1, sticky='w')
    ttk.Entry(controls, textvariable=suffix, width=20).grid(row=1, column=1, padx=(0, 15))
    start = tk.StringVar()
    ttk.Label(controls, text='Nº geral (vazio = próximo)').grid(row=0, column=2, sticky='w')
    ttk.Entry(controls, textvariable=start, width=18).grid(row=1, column=2)
    ttk.Label(frame, text='Uma referência por linha. Para sufixos diferentes, cole duas colunas do Excel: referência e sufixo (ex.: 18 W).').pack(anchor='w', pady=(16, 5))
    entry = tk.Text(frame, height=7, font=('Consolas', 11), wrap='none', undo=True)
    entry.pack(fill='x')
    buttons = ttk.Frame(frame)
    buttons.pack(fill='x', pady=10)
    columns = ('referencia', 'status', 'produto', 'codigo', 'detalhe')
    table_frame = ttk.Frame(frame)
    table_frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='extended')
    for col, title, width in zip(columns, ('Referência', 'Situação', 'Produto', 'Código do sistema', 'Observação'), (260, 175, 160, 170, 300)):
        tree.heading(col, text=title)
        tree.column(col, width=width, minwidth=100, stretch=True)
    sy = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    sx = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(row=0, column=0, sticky='nsew')
    sy.grid(row=0, column=1, sticky='ns')
    sx.grid(row=1, column=0, sticky='ew')
    table_frame.rowconfigure(0, weight=1)
    table_frame.columnconfigure(0, weight=1)
    tree.tag_configure('issue', foreground='#9A3412', background='#FFF7ED')
    tree.tag_configure('ready', foreground='#166534', background='#F0FDF4')
    result = []
    signature = None

    def refresh():
        combo['values'] = sorted({r['grupo'] for r in catalog.records if r['grupo']})
        count = len(catalog.records)
        reserved = catalog.db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
        status.set(f'Base: {count:,} registros   •   Reservas locais: {reserved}   •   A planilha original não é alterada.')

    def sig():
        return (entry.get('1.0', 'end-1c'), group.get(), suffix.get(), start.get())

    def show():
        tree.delete(*tree.get_children())
        for r in result:
            tag = 'ready' if r['status'] in ('Pronto para reservar', 'Reservado') else 'issue' if r['status'] != 'Já cadastrado' else ''
            tree.insert('', 'end', values=tuple(r[k] for k in columns), tags=(tag,))

    def analyze():
        nonlocal result, signature
        try:
            result = catalog.analyze(*sig())
            signature = sig()
            show()
            ready = sum(r['status'] == 'Pronto para reservar' for r in result)
            status.set(f'{len(result)} referências analisadas   •   {ready} prontas para reservar   •   Confira produto, tamanho e cor antes de reservar.')
        except Exception as exc:
            messagebox.showerror('Não foi possível analisar', str(exc))

    def reserve():
        if signature != sig():
            messagebox.showinfo('Analise novamente', 'Os dados foram alterados. Clique em Analisar lote.')
            return
        ready = [r for r in result if r['status'] == 'Pronto para reservar']
        if not ready:
            messagebox.showinfo('Sem códigos novos', 'Não há códigos prontos para reservar.')
            return
        if not messagebox.askyesno('Reservar códigos', f'Reservar os {len(ready)} códigos marcados como prontos?\n\nAs reservas ficam salvas neste computador e evitam reutilização. Elas não cadastram produtos no seu ERP.'):
            return
        try:
            catalog.reserve(result)
            for r in ready:
                r['status'] = 'Reservado'
            show()
            refresh()
        except Exception as exc:
            messagebox.showerror('Reserva não realizada', str(exc))

    def export():
        if signature != sig() or not result:
            messagebox.showinfo('Analise primeiro', 'Analise o lote atual antes de exportar.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='codigos.csv', filetypes=[('CSV para Excel', '*.csv')])
        if path:
            fields = ['referencia', 'grupo', 'produto', 'codigo', 'status', 'detalhe']
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Referência', 'Grupo', 'Produto', 'Código do sistema', 'Situação', 'Observação'])
                for row in result:
                    # Impede que texto colado seja interpretado como fórmula pelo Excel.
                    writer.writerow([("'" + str(row[k])) if str(row[k]).startswith(('=', '+', '-', '@')) else row[k] for k in fields])
            messagebox.showinfo('Exportado', 'CSV salvo. A coluna Situação distingue propostas, reservas e pendências.')

    def import_base():
        nonlocal result, signature
        path = filedialog.askopenfilename(filetypes=[('Planilha Criar Códigos', '*.xlsx')])
        if not path:
            return
        try:
            records = read_xlsx(path)
            temp = HOME / 'base.tmp'
            temp.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
            temp.replace(HOME / 'base.json')
            catalog.records = records
            result, signature = [], None
            show()
            refresh()
            messagebox.showinfo('Base atualizada', f'{len(records)} registros importados. As reservas locais foram mantidas.')
        except Exception as exc:
            messagebox.showerror('Base não atualizada', str(exc))

    def history():
        nonlocal result, signature
        result = [dict(zip(('codigo', 'produto', 'referencia', 'grupo'), r), status='Reservado', detalhe='Reserva local') for r in catalog.db.execute('SELECT codigo,produto,referencia,grupo FROM reservations ORDER BY criado,codigo')]
        signature = sig()
        show()
        status.set(f'{len(result)} reservas locais. Use Exportar CSV para salvar o histórico.')

    for label, action in [('Analisar lote', analyze), ('Reservar códigos prontos', reserve), ('Exportar CSV', export), ('Ver reservas', history), ('Atualizar base Excel', import_base)]:
        ttk.Button(buttons, text=label, command=action).pack(side='left', padx=(0, 8))
    ttk.Label(frame, textvariable=status, wraplength=1100).pack(anchor='w', pady=(12, 0))
    ttk.Label(frame, text='Sequência única para todos os grupos. Variações preservam o número da família (texto antes do primeiro espaço). Informe o sufixo.', wraplength=1100).pack(anchor='w', pady=(6, 0))
    refresh()
    root.mainloop()


if __name__ == '__main__':
    main()
