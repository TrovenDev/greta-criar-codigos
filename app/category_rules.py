"""Padrões de categoria: regras explícitas e evidências únicas do estoque."""
import fnmatch
import re
from collections import defaultdict
from group_picker import search_key


def matches(rule, reference, source_category=''):
    return (fnmatch.fnmatchcase(search_key(reference), search_key(rule['pattern']))
            and (not rule.get('source') or fnmatch.fnmatchcase(search_key(source_category), search_key(rule['source']))))


def stock_patterns(records):
    evidence = defaultdict(lambda: {'groups': set(), 'models': set(), 'count': 0})
    for row in records:
        model = row['referencia'].upper().split()[0]
        prefix = re.match(r'[A-Z]+', model)
        if not prefix:
            continue
        patterns = {prefix[0] + '*'}
        supplier = re.search(r'-F(\d+)$', model)
        kind = re.search(r'-([A-Z]+)\d', model)
        if supplier:
            patterns.add(f'{prefix[0]}*-F{supplier[1]}*')
            if kind and kind[1] != 'F':
                patterns.add(f'{prefix[0]}*-{kind[1]}*-F{supplier[1]}*')
        for pattern in patterns:
            item = evidence[pattern]
            item['groups'].add(row['grupo'])
            item['models'].add(model)
            item['count'] += 1
    result = []
    for pattern, item in evidence.items():
        result.append(dict(pattern=pattern, source='', groups=sorted(item['groups']), models=len(item['models']), count=item['count'],
                           category=next(iter(item['groups'])) if len(item['groups']) == 1 and len(item['models']) >= 2 else ''))
    return sorted(result, key=lambda r: (-r['models'], r['pattern']))


class RuleStore:
    def __init__(self, connection):
        self.db = connection
        self.db.execute('CREATE TABLE IF NOT EXISTS category_rules (id INTEGER PRIMARY KEY, pattern TEXT NOT NULL, source TEXT NOT NULL DEFAULT \'\', category TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, UNIQUE(pattern,source,category))')
        self.db.execute('CREATE TABLE IF NOT EXISTS rule_settings (id INTEGER PRIMARY KEY CHECK(id=1), learn INTEGER NOT NULL DEFAULT 1)')
        self.db.execute('INSERT OR IGNORE INTO rule_settings(id,learn) VALUES(1,1)')
        self.db.commit()

    def all(self):
        return [dict(zip(('id','pattern','source','category','enabled'), r)) for r in self.db.execute('SELECT id,pattern,source,category,enabled FROM category_rules ORDER BY id')]

    def save(self, pattern, source, category):
        pattern, source = pattern.strip().upper(), source.strip().upper()
        if not pattern or not category:
            raise ValueError('Informe o padrão da referência e a categoria.')
        with self.db:
            self.db.execute('INSERT INTO category_rules(pattern,source,category,enabled) VALUES(?,?,?,1) ON CONFLICT(pattern,source,category) DO UPDATE SET enabled=1', (pattern, source, category))

    def remove(self, ids):
        with self.db:
            self.db.executemany('DELETE FROM category_rules WHERE id=?', [(i,) for i in ids])

    def learning(self, value=None):
        if value is not None:
            with self.db:
                self.db.execute('UPDATE rule_settings SET learn=? WHERE id=1', (int(value),))
        return bool(self.db.execute('SELECT learn FROM rule_settings WHERE id=1').fetchone()[0])

    def resolve(self, reference, source_category, learned, saved=None):
        saved = saved if saved is not None else self.all()
        applicable = [r for r in saved if r['enabled'] and matches(r, reference, source_category)]
        origin = 'Regra salva'
        if not applicable and self.learning():
            applicable = [r for r in learned if r['category'] and matches(r, reference)]
            origin = 'Padrão único do estoque'
        categories = sorted({r['category'] for r in applicable})
        if len(categories) == 1:
            return categories[0], categories, origin + ': ' + ', '.join(r['pattern'] for r in applicable)
        if len(categories) > 1:
            return '', categories, 'Conflito entre padrões: ajuste as regras ou informe a categoria da linha.'
        return '', [], ''


class RulesDialog:
    def __init__(self, app):
        import tkinter as tk
        from tkinter import ttk
        import troven_brand as brand
        from group_picker import GroupPicker
        self.app, self.store = app, app.catalog.rules
        self.window = tk.Toplevel(app.root)
        self.window.title('Troven • Regras de categoria')
        self.window.geometry(f'{min(1100, app.root.winfo_screenwidth()-80)}x{min(820, app.root.winfo_screenheight()-90)}')
        self.window.transient(app.root)
        page = ttk.Frame(self.window, padding=20)
        page.pack(fill='both', expand=True)
        ttk.Label(page, text='Regras de categoria para todo o lote', style='PageTitle.TLabel').pack(anchor='w')
        ttk.Label(page, text='* significa qualquer trecho. Exemplos: AR* ou AR*-MRS*-F83*. As regras ficam salvas para os próximos lotes.', style='Muted.TLabel', wraplength=1020).pack(anchor='w', pady=10)
        fields = ttk.Frame(page)
        fields.pack(fill='x')
        self.pattern, self.source, self.category = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(fields, text='Padrão da referência:').grid(row=0, column=0, sticky='w')
        ttk.Entry(fields, textvariable=self.pattern, width=38).grid(row=1, column=0, padx=(0,16), sticky='w')
        ttk.Label(fields, text='Categoria na planilha de origem (opcional):').grid(row=0, column=1, sticky='w')
        ttk.Entry(fields, textvariable=self.source, width=35).grid(row=1, column=1, sticky='w')
        selector = ttk.Frame(page)
        selector.pack(fill='x', pady=10)
        ttk.Label(selector, text='Aplicar esta categoria (GP):').grid(row=0, column=0, sticky='w')
        self.picker = GroupPicker(selector, textvariable=self.category, width=60)
        self.picker.set_options(app.gp_combo.options)
        self.picker.grid(row=1, column=0, padx=(0,12), sticky='w')
        ttk.Button(selector, text='Salvar e aplicar regra', style='Primary.TButton', command=self.save).grid(row=1, column=1)
        self.info = tk.StringVar(value='Para categorias iguais em referências idênticas, combine o padrão com uma informação da planilha de origem.')
        ttk.Label(page, textvariable=self.info, style='Muted.TLabel', wraplength=1000).pack(anchor='w')
        ttk.Label(page, text='Regras salvas', font=(brand.STRONG, 11)).pack(anchor='w', pady=(12,0))
        self.saved = app.make_tree(page, ('pattern','source','category'), ('Referência','Origem (opcional)','Categoria aplicada'), (300,250,410))
        self.saved.configure(height=3)
        ttk.Button(page, text='Remover regras selecionadas', command=self.remove).pack(anchor='w', pady=7)
        self.learn = tk.BooleanVar(value=self.store.learning())
        ttk.Checkbutton(page, text='Reconhecer automaticamente padrões que apontam para uma única categoria no estoque', variable=self.learn, command=self.toggle).pack(anchor='w')
        self.suggestions = app.make_tree(page, ('pattern','category','models','count'), ('Padrão do estoque','Categoria / situação','Modelos','Itens'), (310,410,90,90))
        self.suggestions.configure(height=4)
        self.suggestions.bind('<<TreeviewSelect>>', self.fill_suggestion)
        self.pattern.trace_add('write', lambda *a: self.preview())
        self.source.trace_add('write', lambda *a: self.preview())
        ttk.Button(page, text='Fechar', command=self.window.destroy).pack(anchor='e', pady=(8,0))
        self.refresh()

    def preview(self):
        if not self.pattern.get().strip():
            return
        rule = dict(pattern=self.pattern.get(), source=self.source.get())
        count = sum(matches(rule, r['referencia'], self.app.import_items.get(r['referencia'], {}).get('grupo','')) for r in self.app.rows)
        self.info.set(f'{count} itens do lote correspondem a este padrão. A regra resolve itens sem categoria única no estoque; escolhas manuais têm prioridade.')

    def refresh(self):
        self.saved.delete(*self.saved.get_children())
        for r in self.store.all():
            self.saved.insert('', 'end', iid=str(r['id']), values=(r['pattern'],r['source'],r['category']))
        self.learned = stock_patterns(self.app.catalog.records)
        self.suggestions.delete(*self.suggestions.get_children())
        for i, r in enumerate(self.learned):
            label = r['category'] or f'{len(r["groups"])} categorias: defina uma regra'
            self.suggestions.insert('', 'end', iid=str(i), values=(r['pattern'], label, r['models'],r['count']))

    def fill_suggestion(self, event=None):
        selected = self.suggestions.selection()
        if selected:
            r = self.learned[int(selected[0])]
            self.pattern.set(r['pattern'])
            self.category.set(r['category'])

    def reanalyze(self):
        if self.app.rows:
            self.app.analyze()

    def save(self):
        try:
            category = self.picker.resolve()
            self.store.save(self.pattern.get(),self.source.get(),category)
            self.refresh()
            self.reanalyze()
            self.preview()
        except Exception as exc:
            self.app.message('Regra não salva', exc, True)

    def remove(self):
        self.store.remove([int(i) for i in self.saved.selection()])
        self.refresh()
        self.reanalyze()

    def toggle(self):
        self.store.learning(self.learn.get())
        self.reanalyze()
