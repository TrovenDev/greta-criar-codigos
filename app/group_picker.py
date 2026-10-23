"""Seletor de grupo com busca digitável e opções filtradas."""
import unicodedata
import tkinter as tk
from tkinter import ttk
import troven_brand as brand


def search_key(value):
    text = unicodedata.normalize('NFKD', str(value)).casefold()
    return ''.join(c for c in text if not unicodedata.combining(c))


def matching_groups(options, query):
    words = search_key(query).split()
    return [g for g in options if all(word in search_key(g) for word in words)]


class GroupPicker(ttk.Combobox):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, state='normal', postcommand=self.before_dropdown, **kwargs)
        self.options = ()
        self.matches = []
        self.results = ttk.Frame(parent)
        self.notice = tk.StringVar()
        ttk.Label(self.results, textvariable=self.notice, style='Muted.TLabel', font=(brand.BODY, 9)).pack(anchor='w', pady=(4, 5))
        box = ttk.Frame(self.results)
        box.pack(fill='x')
        self.listbox = tk.Listbox(box, height=4, exportselection=False, activestyle='none', bg=brand.BRANCO, fg=brand.NOITE, selectbackground=brand.COBALTO, selectforeground=brand.BRANCO, font=(brand.BODY, 10), bd=0, highlightthickness=1, highlightbackground=brand.LINHA, highlightcolor=brand.COBALTO)
        scroll = ttk.Scrollbar(box, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side='left', fill='x', expand=True)
        scroll.pack(side='right', fill='y')
        self.bind('<KeyRelease>', self.filter_typed)
        self.bind('<<ComboboxSelected>>', lambda e: self.commit(self.get()))
        self.bind('<Down>', self.open_results)
        self.bind('<Return>', self.accept_unique)
        self.bind('<Escape>', lambda e: self.hide())
        self.bind('<FocusOut>', lambda e: self.after(120, self.hide_if_outside))
        self.listbox.bind('<ButtonRelease-1>', self.choose_result)
        self.listbox.bind('<Return>', self.choose_result)
        self.listbox.bind('<Escape>', lambda e: (self.hide(), self.focus_set()))
        self.listbox.bind('<FocusOut>', lambda e: self.after(120, self.hide_if_outside))

    def set_options(self, options):
        self.options = tuple(sorted(set(options)))
        self['values'] = self.options
        self.matches = list(self.options)
        self.hide()

    def before_dropdown(self):
        self.hide()
        self['values'] = self.options if self.get() in self.options else matching_groups(self.options, self.get())

    def filter_typed(self, event=None):
        if event is not None and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return
        self.matches = matching_groups(self.options, self.get())
        self['values'] = self.matches
        self.listbox.delete(0, 'end')
        for group in self.matches:
            self.listbox.insert('end', group)
        visible = 4 if self.winfo_toplevel().winfo_height() >= 850 else 2
        self.listbox.configure(height=min(visible, max(1, len(self.matches))))
        self.notice.set(f'Resultados: {len(self.matches)}. Clique numa opção ou use ↓ e Enter.' if self.matches else 'Nenhum grupo encontrado. Tente outro nome ou código.')
        self.results.grid(row=4, column=0, sticky='ew', padx=(0, 16), pady=(0, 4))

    def open_results(self, event=None):
        self.filter_typed()
        if self.matches:
            self.listbox.selection_clear(0, 'end')
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.listbox.focus_set()
        return 'break'

    def choose_result(self, event=None):
        selected = self.listbox.curselection()
        if selected:
            self.commit(self.listbox.get(selected[0]))
            self.focus_set()
            self.icursor('end')
        return 'break'

    def accept_unique(self, event=None):
        found = matching_groups(self.options, self.get())
        if len(found) == 1:
            self.commit(found[0])
        else:
            self.filter_typed()
        return 'break'

    def commit(self, value):
        self.set(value)
        self['values'] = self.options
        self.hide()

    def resolve(self):
        query = self.get().strip()
        if not query:
            return ''
        if query in self.options:
            return query
        prefixes = [g for g in self.options if search_key(g.split('-')[0]) == search_key(query)]
        found = prefixes or matching_groups(self.options, query)
        if len(found) == 1:
            self.commit(found[0])
            return found[0]
        if not found:
            raise ValueError(f'Nenhum grupo corresponde a “{query}”. Digite parte do nome ou do código e selecione uma opção.')
        raise ValueError(f'“{query}” corresponde a {len(found)} grupos. Escolha uma opção na lista filtrada.')

    def hide(self):
        self.results.grid_remove()

    def hide_if_outside(self):
        if self.winfo_exists() and self.focus_get() not in (self, self.listbox):
            self.hide()
