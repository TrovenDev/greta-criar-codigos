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

HOME = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


from workflow_core import Workflow


class App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        self.catalog = Workflow([], HOME / 'reservas.sqlite3')
        self.rows, self.source, self.loaded_sheet, self.signature = [], '', '', None
        self.source_stamp = None
        self.file_path = tk.StringVar()
        self.sheet = tk.StringVar()
        self.group = tk.StringVar()
        self.suffix = tk.StringVar()
        self.assignments, self.sizes = {}, {}
        self.import_items, self.new_source = {}, ''
        self.import_info = tk.StringVar(value='Selecione a planilha de códigos novos para importar as referências e os pesos.')
        self.apply_model = tk.BooleanVar(value=True)
        self.summary = tk.StringVar(value='Selecione o Excel de estoque para começar.')
        self.stock_info = tk.StringVar(value='Nenhum estoque carregado.')
        self.show_existing = tk.BooleanVar(value=False)
        self.product_filter = tk.StringVar(value='Todos')
        self.product_search = tk.StringVar()
        self.filter_info = tk.StringVar()
        self.tutorial = None
        self.stock_count = tk.StringVar(value='—')
        self.stock_last = tk.StringVar(value='—')
        self.stock_next = tk.StringVar(value='—')
        self.shell = brand.Shell(self, root)
        self.make_stock_page()
        self.make_codes_page()
        self.make_weights_page()
        self.product_filter.trace_add('write', lambda *a: self.show())
        self.product_search.trace_add('write', lambda *a: self.show())
        self.shell.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def open_tutorial(self):
        from tutorial import Tutorial
        if self.tutorial is not None and self.tutorial.window.winfo_exists():
            self.tutorial.window.lift()
            self.tutorial.window.focus_set()
            return
        self.tutorial = Tutorial(self)

    def message(self, title, text, error=False):
        from tkinter import messagebox
        (messagebox.showerror if error else messagebox.showinfo)(title, str(text), parent=self.root)

    def button(self, parent, title, fn):
        primary = title in ('Selecionar Excel de estoque', 'Selecionar planilha de códigos novos', 'Gerar e conferir códigos', 'Exportar Excel')
        widget = self.ttk.Button(parent, text=title, command=fn, style='Primary.TButton' if primary else 'TButton')
        widget.pack(side='left', padx=(0, 9))
        return widget

    def make_tree(self, parent, columns, titles, widths):
        wrapper = self.ttk.Frame(parent)
        wrapper.pack(fill='both', expand=True, pady=(10, 0))
        tree = self.ttk.Treeview(wrapper, columns=columns, show='headings', selectmode='extended')
        for key, title, width in zip(columns, titles, widths):
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=65, stretch=True, anchor='e' if key == 'peso' else 'w')
        y = self.ttk.Scrollbar(wrapper, orient='vertical', command=tree.yview)
        x = self.ttk.Scrollbar(wrapper, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        tree.tag_configure('issue', foreground='#9A3412', background='#FFF5E8')
        tree.tag_configure('ready', foreground=brand.NOITE, background=brand.BRANCO)
        return tree

    def make_stock_page(self):
        p = self.pages[0]
        self.ttk.Label(p, text='Comece pelo seu estoque.', style='PageTitle.TLabel').pack(anchor='w')
        self.ttk.Label(p, text='Carregue o relatório atualizado para encontrar a próxima sequência geral.', style='Muted.TLabel').pack(anchor='w', pady=(9, 18))
        metrics = self.tk.Frame(p, bg=brand.BRANCO)
        metrics.pack(fill='x', pady=(0, 18))
        for title, value, accent in [('PRODUTOS NO ESTOQUE', self.stock_count, False), ('ÚLTIMA SEQUÊNCIA', self.stock_last, False), ('PRÓXIMO NÚMERO GERAL', self.stock_next, True)]:
            card = self.tk.Frame(metrics, bg=brand.COBALTO if accent else brand.PAPEL, padx=16, pady=16)
            card.pack(side='left', fill='both', expand=True, padx=(0, 10))
            self.tk.Label(card, text=title, bg=brand.COBALTO if accent else brand.PAPEL, fg='#E6E7FF' if accent else brand.MUTED, font=(brand.STRONG, 9)).pack(anchor='w')
            self.tk.Label(card, textvariable=value, bg=brand.COBALTO if accent else brand.PAPEL, fg=brand.LIMA if accent else brand.NOITE, font=(brand.DISPLAY, 23)).pack(anchor='w', pady=(9, 0))
        bar = self.ttk.Frame(p)
        bar.pack(fill='x', pady=12)
        self.button(bar, 'Selecionar Excel de estoque', self.choose_stock)
        self.ttk.Entry(bar, textvariable=self.file_path, state='readonly').pack(side='left', fill='x', expand=True)
        bar = self.ttk.Frame(p)
        bar.pack(fill='x', pady=(0, 12))
        self.ttk.Label(bar, text='Aba do estoque:').pack(side='left', padx=(0, 8))
        self.sheet_combo = self.ttk.Combobox(bar, textvariable=self.sheet, state='readonly', width=35)
        self.sheet_combo.pack(side='left', padx=(0, 12))
        self.button(bar, 'Carregar estoque', self.load_stock)
        self.ttk.Label(p, textvariable=self.stock_info, wraplength=820, style='Muted.TLabel').pack(anchor='w', pady=10)
        brand.tip(p, 'Uma sequência para todos os grupos', 'O próximo número considera o estoque selecionado e as reservas locais. Os grupos definem o prefixo do código e compartilham a mesma sequência.')
        brand.tip(p, 'Seu Excel precisa destas colunas', 'Código do sistema, Produto, Referência e GP. O nome da aba e a ordem das colunas podem variar. Use o tutorial para experimentar com dados de exemplo.')
        bar = self.ttk.Frame(p)
        bar.pack(fill='x', pady=18)
        self.button(bar, 'Ir para códigos novos', lambda: self.tabs.select(1) if self.catalog.records else self.message('Carregue o estoque', 'Selecione e carregue o estoque primeiro.'))
        self.button(bar, 'Restaurar último lote', self.restore)

    def make_codes_page(self):
        p = self.pages[1]
        self.ttk.Label(p, text='Gere os códigos dos produtos.', style='PageTitle.TLabel').pack(anchor='w')
        self.ttk.Label(p, text='Importe a planilha de itens novos. Confira as categorias de cada produto.', style='Muted.TLabel', wraplength=820).pack(anchor='w', pady=(8, 10))
        source_bar = self.ttk.Frame(p)
        source_bar.pack(fill='x', pady=(0, 8))
        self.button(source_bar, 'Selecionar planilha de códigos novos', self.choose_new_items)
        self.ttk.Label(source_bar, textvariable=self.import_info, style='Muted.TLabel', wraplength=500).pack(side='left', fill='x', expand=True)
        bar = self.ttk.Frame(p)
        bar.pack(fill='x')
        self.ttk.Label(bar, text='Categoria das linhas selecionadas — digite para filtrar:').grid(row=0, column=0, sticky='w')
        self.gp_combo = GroupPicker(bar, textvariable=self.group, width=60)
        self.gp_combo.grid(row=1, column=0, padx=(0, 16))
        self.ttk.Button(bar, text='Aplicar categoria', command=self.apply_category).grid(row=1, column=1, sticky='w')
        self.ttk.Checkbutton(bar, text='Aplicar também às variações sem categoria do mesmo modelo', variable=self.apply_model).grid(row=2, column=0, columnspan=2, sticky='w', pady=(5, 0))
        self.manual_open = self.tk.BooleanVar(value=False)
        manual = self.ttk.Frame(p)
        self.ttk.Checkbutton(p, text='Colar referências manualmente (opcional)', variable=self.manual_open,
                             command=lambda: manual.pack(fill='x', before=actions) if self.manual_open.get() else manual.pack_forget()).pack(anchor='w', pady=(8, 0))
        self.ttk.Label(manual, text='Cole uma referência por linha. Colunas opcionais: referência, tamanho e cor, peso (g), GP.', wraplength=820, style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        self.text = self.tk.Text(manual, height=2, font=('Consolas', 11), undo=True, wrap='none', bg=brand.PAPEL, fg=brand.NOITE, insertbackground=brand.COBALTO, bd=0, highlightthickness=1, highlightbackground=brand.LINHA, highlightcolor=brand.COBALTO, padx=12, pady=10, selectbackground=brand.COBALTO, selectforeground=brand.BRANCO)
        self.text.pack(fill='x', pady=(8, 0))
        bar = self.ttk.Frame(p)
        actions = bar
        bar.pack(fill='x', pady=10)
        self.button(bar, 'Gerar e conferir códigos', self.analyze)
        self.button(bar, 'Ir para cadastro e peso', self.go_weights)
        self.button(bar, 'Regras de categoria', self.open_rules)
        self.make_product_filter(p)
        self.code_tree = self.make_tree(p, ('referencia', 'grupo', 'status', 'produto', 'codigo', 'detalhe'), ('Referência', 'Categoria (GP)', 'O que é este item?', 'Produto', 'Código', 'O que fazer agora'), (250, 235, 190, 160, 155, 350))
        self.code_tree.bind('<Double-1>', self.edit_item)

    def make_weights_page(self):
        p = self.pages[2]
        self.ttk.Label(p, text='Confira os pesos e as unidades.', style='PageTitle.TLabel').pack(anchor='w')
        self.ttk.Label(p, text='Com peso: G. Sem peso: valor 1 e PC para anéis/outros, PR para brincos. Dê dois cliques para editar.', style='Muted.TLabel', wraplength=820).pack(anchor='w', pady=(9, 16))
        bar = self.ttk.Frame(p)
        bar.pack(fill='x')
        self.batch_weight = self.tk.StringVar()
        self.ttk.Label(bar, text='Peso (vazio = unidade):').pack(side='left', padx=(0, 6))
        self.ttk.Entry(bar, textvariable=self.batch_weight, width=14).pack(side='left', padx=(0, 8))
        self.button(bar, 'Aplicar às selecionadas', self.apply_weight)
        self.button(bar, 'Colar pesos por referência', self.paste_weights)
        self.ttk.Checkbutton(p, text='Incluir produtos já cadastrados no estoque', variable=self.show_existing, command=self.include_existing).pack(anchor='w', pady=(10, 0))
        self.make_product_filter(p)
        self.weight_tree = self.make_tree(p, ('codigo', 'referencia', 'peso', 'unidade', 'grupo', 'status', 'exportar'), ('Código', 'Referência', 'Peso', 'Unidade', 'Categoria (GP)', 'Situação', 'Exportar'), (170, 280, 90, 80, 230, 180, 85))
        self.weight_tree.bind('<Double-1>', self.edit_weight)
        bar = self.ttk.Frame(p)
        bar.pack(fill='x', pady=(12, 0))
        self.button(bar, 'Marcar/desmarcar selecionadas', self.toggle_export)
        self.button(bar, 'Salvar lote', self.save)
        self.button(bar, 'Exportar Excel', self.export)
        self.button(bar, 'Exportar CSV', lambda: self.export(csv_output=True))

    def make_product_filter(self, parent):
        bar = self.ttk.Frame(parent)
        bar.pack(fill='x', pady=(6, 0))
        self.ttk.Label(bar, text='Mostrar:').pack(side='left', padx=(0, 6))
        self.ttk.Combobox(bar, textvariable=self.product_filter, values=FILTERS, state='readonly', width=32).pack(side='left')
        self.ttk.Label(bar, text='Buscar produto:').pack(side='left', padx=(12, 6))
        self.ttk.Entry(bar, textvariable=self.product_search, width=22).pack(side='left', fill='x', expand=True)
        self.ttk.Label(parent, textvariable=self.filter_info, style='Muted.TLabel', wraplength=920).pack(anchor='w', pady=(4, 0))

    def current_signature(self):
        return self.text.get('1.0', 'end-1c'), self.source, self.loaded_sheet, json.dumps(self.assignments, sort_keys=True), json.dumps(self.sizes, sort_keys=True), json.dumps(self.import_items, sort_keys=True)

    def open_rules(self):
        from category_rules import RulesDialog
        RulesDialog(self)

    def choose_new_items(self):
        from tkinter import filedialog
        from new_items import ImportDialog
        path = filedialog.askopenfilename(title='Selecione a planilha de códigos novos', filetypes=[('Excel', '*.xlsx *.xlsm')], parent=self.root)
        if path:
            try:
                ImportDialog(self, path, self.accept_new_items)
            except Exception as exc:
                self.message('Não foi possível abrir a planilha', exc, True)

    def accept_new_items(self, records, path, sheet, skipped=0):
        from tkinter import messagebox
        from uuid import uuid4
        if self.rows and not messagebox.askyesno('Importar novo lote', 'Substituir o lote atual pelos itens desta planilha?', parent=self.root):
            return
        context = uuid4().hex
        self.import_items, self.assignments, self.sizes = {}, {}, {}
        lines = []
        options = self.gp_combo.options
        for item in records:
            ref = normal(item['referencia'])
            meta = dict(item, context=context)
            self.import_items[ref] = meta
            raw_gp = normal(item.get('grupo', ''))
            gp = next((g for g in options if normal(g) == raw_gp), '')
            if not gp:
                matches = [g for g in options if normal(g.split('-')[0]) == raw_gp]
                gp = matches[0] if len(matches) == 1 else ''
            value = '' if item.get('peso') is None else str(item['peso'])
            lines.append('\t'.join((ref, normal(item.get('tamanho_cor', '')), value, gp)))
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(lines))
        self.new_source = str(path)
        self.import_info.set(f'{len(records)} produtos importados. Aba: {sheet}. {skipped} linhas vazias/totais ignoradas.')
        self.analyze()

    def category_targets(self, selected):
        models = {family(r['referencia']) for r in selected}
        return [r for r in self.rows if r in selected or (self.apply_model.get() and not r['grupo'] and family(r['referencia']) in models)]

    def apply_category(self):
        selected = [self.rows[int(i)] for i in self.code_tree.selection()]
        if not selected:
            return self.message('Selecione as linhas', 'Gere o lote e selecione na tabela os itens cuja categoria deseja definir.')
        try:
            gp = self.gp_combo.resolve()
            if not gp:
                raise ValueError('Digite e selecione a categoria que deseja aplicar às linhas.')
            targets = self.category_targets(selected)
            for row in targets:
                if not compatible(row['referencia'], gp, self.import_items.get(row['referencia'], {})):
                    raise ValueError(f"{row['referencia']}: este item é moissanite. Escolha um grupo de moissanite.")
            for row in targets:
                self.assignments[normal(row['referencia'])] = gp
            self.analyze()
        except Exception as exc:
            self.message('Categoria não aplicada', exc, True)

    def edit_item(self, event):
        iid = self.code_tree.identify_row(event.y)
        if not iid:
            return
        row = self.rows[int(iid)]
        dialog = self.tk.Toplevel(self.root)
        dialog.title('Troven • Categoria, tamanho e cor')
        dialog.geometry('880x530')
        dialog.transient(self.root)
        dialog.configure(bg=brand.BRANCO)
        content = self.ttk.Frame(dialog, padding=20)
        content.pack(fill='both', expand=True)
        self.ttk.Label(content, text=row['referencia'], style='PageTitle.TLabel', wraplength=820).pack(anchor='w', pady=(0, 14))
        bar = self.ttk.Frame(content)
        bar.pack(fill='x')
        self.ttk.Label(bar, text='Categoria (GP):').grid(row=0, column=0, sticky='w')
        selected = self.tk.StringVar(value=row['grupo'])
        picker = GroupPicker(bar, textvariable=selected, width=58)
        picker.set_options([g for g in self.gp_combo.options if compatible(row['referencia'], g, self.import_items.get(row['referencia'], {}))])
        picker.grid(row=1, column=0, sticky='w', padx=(0, 12))
        size = self.tk.StringVar(value=row.get('tamanho_cor', ''))
        self.ttk.Label(bar, text='Tamanho e cor:').grid(row=0, column=1, sticky='w')
        self.ttk.Entry(bar, textvariable=size, width=20).grid(row=1, column=1, sticky='w')
        self.ttk.Label(bar, text='Ex.: 14 W significa tamanho 14 e cor W. Esse valor altera apenas esta referência.', style='Muted.TLabel', wraplength=800).grid(row=2, column=0, columnspan=2, sticky='w', pady=(10, 0))
        candidates = row.get('categorias_possiveis', [])
        if candidates:
            self.ttk.Label(content, text='Categorias encontradas no estoque: ' + '; '.join(candidates), style='Muted.TLabel', wraplength=810).pack(anchor='w', pady=10)
        def apply():
            try:
                gp = picker.resolve()
                if not gp:
                    raise ValueError('Escolha a categoria do item.')
                if not compatible(row['referencia'], gp, self.import_items.get(row['referencia'], {})):
                    raise ValueError('Este item é moissanite. Escolha um grupo de moissanite.')
                for r in self.category_targets([row]):
                    self.assignments[normal(r['referencia'])] = gp
                if size.get().strip():
                    self.sizes[normal(row['referencia'])] = normal(size.get())
                else:
                    self.sizes.pop(normal(row['referencia']), None)
                dialog.destroy()
                self.analyze()
            except Exception as exc:
                self.message('Item não atualizado', exc, True)
        self.ttk.Button(content, text='Aplicar ao lote', style='Primary.TButton', command=apply).pack(anchor='w', pady=12)

    def choose_stock(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(title='Selecione o Excel de estoque', filetypes=[('Excel', '*.xlsx *.xlsm')], parent=self.root)
        if not path:
            return
        try:
            sheets = stock_sheets(path)
            if not sheets:
                raise ValueError('Não encontrei uma aba com Código do sistema, Produto, Referência e GP.')
            # Apenas a seleção não troca a fonte efetiva: a troca ocorre em Carregar estoque.
            self.file_path.set(path)
            self.sheet_combo['values'] = sheets
            self.sheet.set(sheets[0])
            if len(sheets) == 1:
                self.load_stock()
            else:
                self.message('Escolha a aba', 'Escolha a aba de estoque e clique em Carregar estoque.')
        except Exception as exc:
            self.message('Não foi possível ler o estoque', exc, True)

    def load_stock(self):
        from tkinter import messagebox
        if not self.file_path.get():
            return self.choose_stock()
        try:
            records = read_stock(self.file_path.get(), self.sheet.get())
            if self.rows and not messagebox.askyesno('Trocar estoque', 'Carregar este estoque inicia uma nova análise. O lote atual será salvo para restauração.', parent=self.root):
                return
            if self.rows:
                self.save(notify=False)
            self.catalog.records = records
            self.source, self.loaded_sheet = self.file_path.get(), self.sheet.get()
            self.source_stamp = (Path(self.source).stat().st_mtime_ns, Path(self.source).stat().st_size)
            self.rows, self.signature = [], None
            self.assignments, self.sizes = {}, {}
            self.import_items, self.new_source = {}, ''
            self.import_info.set('Selecione a planilha de códigos novos para importar as referências e os pesos.')
            self.gp_combo.set_options(r['grupo'] for r in records)
            if self.group.get() not in self.gp_combo.options:
                self.group.set('')
            last_stock, last_all = self.catalog.last_number(True), self.catalog.last_number()
            self.stock_info.set(f'Estoque carregado. Aba: {self.loaded_sheet}.')
            self.stock_count.set(f'{len(records):,}'.replace(',', '.'))
            self.stock_last.set(f'{last_stock:04d}')
            self.stock_next.set(f'{last_all + 1:04d}')
            self.summary.set('Estoque carregado. Abra a etapa 2 e cole as referências dos códigos novos.')
            self.tabs.tab(1, state='normal')
            self.tabs.tab(2, state='disabled')
            self.show()
        except Exception as exc:
            self.message('Estoque não carregado', exc, True)

    def analyze(self):
        from tkinter import messagebox
        try:
            new = self.catalog.prepare(self.text.get('1.0', 'end-1c'), assignments=self.assignments, sizes=self.sizes, items=self.import_items)
            if self.rows and self.signature == self.current_signature() and any(r['status'] == 'Reservado' for r in self.rows):
                for r in new:
                    old = next((s for s in self.rows if s['codigo'] == r['codigo'] and s['referencia'] == r['referencia']), None)
                    if old:
                        r['exportar'] = old.get('exportar', r['exportar'])
            self.rows = new
            self.signature = self.current_signature()
            self.tabs.tab(2, state='normal')
            self.show()
            self.save(notify=False)
        except Exception as exc:
            self.message('Não foi possível gerar', exc, True)

    def show(self):
        self.shell.refresh()
        for tree in (self.code_tree, self.weight_tree):
            tree.delete(*tree.get_children())
        for i, r in enumerate(self.rows):
            if not visible(r, self.product_filter.get(), self.product_search.get()):
                continue
            valid = r['status'] in ('Pronto para reservar', 'Reservado', 'Já cadastrado')
            tag = 'ready' if valid else 'issue'
            label, detail = situation(r)
            self.code_tree.insert('', 'end', iid=str(i), values=(r['referencia'], r['grupo'], label, r['produto'], r['codigo'], detail), tags=(tag,))
            display_weight = '' if r.get('peso') is None else format(r['peso'], '.6f').rstrip('0').rstrip('.').replace('.', ',')
            state = label if r.get('peso') is not None or not valid else 'Preencher peso'
            self.weight_tree.insert('', 'end', iid=str(i), values=(r['codigo'], r['referencia'], display_weight, r.get('unidade', 'G'), r['grupo'], state, 'Sim' if r.get('exportar') else 'Não'), tags=(tag if state != 'Preencher peso' else 'issue',))
        chosen = [r for r in self.rows if r.get('exportar')]
        count = len(self.code_tree.get_children())
        self.filter_info.set(f'{count} de {len(self.rows)} itens visíveis. A cadastrar inclui novos modelos e novas variações. O filtro só muda a visualização; confira a coluna Exportar.')
        missing = sum(r.get('peso') is None for r in chosen)
        if self.rows:
            attention = sum(r['status'] not in ('Pronto para reservar', 'Reservado', 'Já cadastrado') for r in self.rows)
            existing = sum(r['status'] == 'Já cadastrado' for r in self.rows)
            new = len(self.rows) - attention - existing
            self.summary.set(f'{new} a cadastrar · {existing} já no estoque · {attention} precisam de atenção · {len(chosen)} marcados para exportar · {missing} pesos pendentes')

    def go_weights(self):
        if self.signature != self.current_signature() or not self.rows:
            self.analyze()
        if self.rows and self.signature == self.current_signature():
            self.tabs.select(2)

    def apply_weight(self):
        selected = self.weight_tree.selection()
        if not selected:
            return self.message('Selecione as linhas', 'Selecione uma ou mais linhas na tabela de cadastro.')
        try:
            value = weight(self.batch_weight.get())
            for iid in selected:
                self.catalog.set_weight(self.rows[int(iid)], value)
            self.save(notify=False)
            self.show()
        except Exception as exc:
            self.message('Peso inválido', exc, True)

    def edit_weight(self, event):
        iid = self.weight_tree.identify_row(event.y)
        if not iid:
            return
        row = self.rows[int(iid)]
        if self.weight_tree.identify_column(event.x) == '#7':
            self.weight_tree.selection_set(iid)
            return self.toggle_export()
        dialog = self.tk.Toplevel(self.root)
        dialog.title('Troven • Peso e unidade')
        dialog.geometry('600x330')
        dialog.transient(self.root)
        page = self.ttk.Frame(dialog, padding=20)
        page.pack(fill='both', expand=True)
        self.ttk.Label(page, text=row['referencia'], style='PageTitle.TLabel', wraplength=550).pack(anchor='w')
        mode = self.tk.StringVar(value=row.get('venda_por', 'Peso'))
        value = self.tk.StringVar(value=str(row.get('peso', 1)).replace('.', ','))
        self.ttk.Radiobutton(page, text='Vendido por peso — unidade G', variable=mode, value='Peso').pack(anchor='w', pady=(16, 4))
        self.ttk.Entry(page, textvariable=value, width=20).pack(anchor='w')
        unit = piece_unit(row['referencia'], row['grupo'], row.get('tipo', ''))
        self.ttk.Radiobutton(page, text=f'Vendido por unidade — peso 1, unidade {unit}', variable=mode, value='Unidade').pack(anchor='w', pady=12)
        def apply():
            try:
                if mode.get() == 'Peso' and weight(value.get()) is None:
                    raise ValueError('Informe o peso em gramas ou selecione venda por unidade.')
                self.catalog.set_weight(row, value.get() if mode.get() == 'Peso' else None)
                self.save(notify=False)
                self.show()
                dialog.destroy()
            except Exception as exc:
                self.message('Peso inválido', exc, True)
        self.ttk.Button(page, text='Aplicar', style='Primary.TButton', command=apply).pack(anchor='w', pady=8)

    def paste_weights(self):
        dialog = self.tk.Toplevel(self.root)
        dialog.title('Troven • Colar pesos')
        dialog.geometry('660x390')
        dialog.transient(self.root)
        self.ttk.Label(dialog, text='Copie duas colunas do Excel: código ou referência | peso (g).', wraplength=620).pack(anchor='w', padx=15, pady=12)
        dialog.configure(bg=brand.BRANCO)
        text = self.tk.Text(dialog, font=('Consolas', 11), bg=brand.PAPEL, fg=brand.NOITE, insertbackground=brand.COBALTO, highlightcolor=brand.COBALTO, bd=0, padx=10, pady=10)
        text.pack(fill='both', expand=True, padx=15)

        def apply():
            try:
                changes = []
                for line in text.get('1.0', 'end-1c').splitlines():
                    if not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) != 2:
                        raise ValueError('Use duas colunas: referência ou código e peso.')
                    matched = [r for r in self.rows if normal(parts[0]) in (normal(r['referencia']), normal(r['codigo']))]
                    if len(matched) != 1:
                        raise ValueError(f'Identificação ausente ou ambígua no lote: {parts[0]}. Use o código.')
                    value = weight(parts[1])
                    changes.append((matched[0], value))
                if not changes:
                    raise ValueError('Cole pelo menos um peso.')
                for row, value in changes:
                    self.catalog.set_weight(row, value)
                self.save(notify=False)
                self.show()
                dialog.destroy()
            except Exception as exc:
                self.message('Pesos não aplicados', exc, True)
        self.ttk.Button(dialog, text='Aplicar pesos', command=apply).pack(pady=12)

    def include_existing(self):
        for r in self.rows:
            if r['status'] == 'Já cadastrado':
                r['exportar'] = self.show_existing.get()
        self.show()
        self.save(notify=False)

    def toggle_export(self):
        for iid in self.weight_tree.selection():
            r = self.rows[int(iid)]
            if r['status'] in ('Pronto para reservar', 'Reservado', 'Já cadastrado'):
                r['exportar'] = not r.get('exportar')
        self.show()
        self.save(notify=False)

    def save(self, notify=True):
        try:
            self.catalog.save_session(self.rows, self.source, self.loaded_sheet, self.text.get('1.0', 'end-1c'), assignments=self.assignments, sizes=self.sizes, items=self.import_items, new_source=self.new_source)
            if notify:
                self.message('Lote salvo', 'O lote e os pesos foram salvos. Use Restaurar último lote na etapa 1 para retomar depois.')
        except Exception as exc:
            self.message('Não foi possível salvar', exc, True)

    def restore(self):
        from tkinter import messagebox
        try:
            state = self.catalog.session()
            if not state.get('rows'):
                return self.message('Nenhum lote salvo', 'Não há um lote anterior para restaurar.')
            if self.rows and not messagebox.askyesno('Restaurar lote', 'Substituir o lote atual pelo último lote salvo?', parent=self.root):
                return
            path, sheet = state['source'], state['sheet']
            records = read_stock(path, sheet)
            self.catalog.records = records
            self.source, self.loaded_sheet = path, sheet
            self.source_stamp = (Path(path).stat().st_mtime_ns, Path(path).stat().st_size)
            self.file_path.set(path)
            self.sheet_combo['values'] = [sheet]
            self.sheet.set(sheet)
            self.gp_combo.set_options(r['grupo'] for r in records)
            self.group.set(state.get('group', ''))
            self.assignments, self.sizes = state.get('assignments', {}), state.get('sizes', {})
            self.import_items, self.new_source = state.get('items', {}), state.get('new_source', '')
            if self.new_source:
                self.import_info.set(f'Lote restaurado de {Path(self.new_source).name}.')
            self.text.delete('1.0', 'end')
            self.text.insert('1.0', state.get('text', ''))
            # Reanalisar contra o estoque atual evita restaurar propostas com sequência antiga.
            self.rows = self.catalog.prepare(state['text'], assignments=self.assignments, sizes=self.sizes, items=self.import_items)
            for r in self.rows:
                old = next((s for s in state['rows'] if s['referencia'] == r['referencia'] and s['grupo'] == r['grupo']), None)
                if old:
                    r['peso'] = old.get('peso')
                    r['venda_por'] = old.get('venda_por', 'Peso')
                    r['unidade'] = old.get('unidade', 'G')
                    r['exportar'] = old.get('exportar', r['exportar']) and r['status'] in ('Reservado', 'Pronto para reservar', 'Já cadastrado')
            self.signature = self.current_signature()
            self.stock_info.set(f'Lote restaurado. Estoque carregado da aba: {self.loaded_sheet}.')
            self.stock_count.set(f'{len(records):,}'.replace(',', '.'))
            self.stock_last.set(f'{self.catalog.last_number(True):04d}')
            self.stock_next.set(f'{self.catalog.last_number() + 1:04d}')
            for i in (1, 2):
                self.tabs.tab(i, state='normal')
            self.show()
            self.tabs.select(2)
        except Exception as exc:
            self.message('Não foi possível restaurar', str(exc) + '\nSelecione novamente o estoque se o arquivo foi movido.', True)

    def export(self, csv_output=False):
        from tkinter import filedialog
        try:
            if not self.catalog.records or self.signature != self.current_signature():
                raise ValueError('Volte à etapa 2 e gere novamente os códigos após alterar as referências ou o estoque.')
            source_stat = Path(self.source).stat()
            if self.source_stamp != (source_stat.st_mtime_ns, source_stat.st_size):
                raise ValueError('O Excel de estoque foi alterado desde a leitura. Carregue o estoque novamente e gere os códigos antes de exportar.')
            records = self.catalog.export_rows(self.rows)
            grade = grade_rows(records)
            ext = '.csv' if csv_output else '.xlsx'
            path = filedialog.asksaveasfilename(title='Salvar Grade Lançar', initialfile='Grade Lançar' + ext, defaultextension=ext, filetypes=[('CSV' if csv_output else 'Excel', '*' + ext)], parent=self.root)
            if not path:
                return
            if Path(path).resolve() == Path(self.source).resolve():
                raise ValueError('Escolha outro nome. O arquivo de estoque não pode ser sobrescrito.')
            chosen = [r for r in self.rows if r.get('exportar')]
            # A reserva precede a gravação. Se a gravação falhar, os mesmos códigos
            # permanecem no lote para repetir a exportação, sem consumir outros números.
            self.catalog.reserve(chosen)
            self.stock_next.set(f'{self.catalog.last_number() + 1:04d}')
            for r in chosen:
                if r['status'] == 'Pronto para reservar':
                    r['status'] = 'Reservado'
            self.save(notify=False)
            if csv_output:
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(GRADE_HEADERS)
                    for row in grade:
                        safe = lambda v: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v
                        writer.writerow([str(v).replace('.', ',') if isinstance(v, float) else safe(v) if v is not None else '' for v in row])
            else:
                export_xlsx(path, records, prepared=grade)
            self.show()
            self.message('Grade Lançar exportada', f'{len(records)} variações e {len(grade) - len(records)} pais exportados no formato de 19 colunas.\n\nOs pais ficam no final, com pesogramas 0, fatconv 50 e peso 0.')
        except Exception as exc:
            self.show()
            self.message('Cadastro não exportado', exc, True)

    def close(self):
        if self.tutorial is not None and self.tutorial.window.winfo_exists():
            self.tutorial.close()
        if self.rows:
            self.save(notify=False)
        self.catalog.db.close()
        self.root.destroy()


def main():
    import tkinter as tk
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
